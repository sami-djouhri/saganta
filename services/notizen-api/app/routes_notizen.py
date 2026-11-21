import json
from datetime import UTC, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import ablage
from .auth import Me, verify_jwt
from .config import settings
from .db import get_db
from .helfer import anhang_aus, notiz_aus, notiz_holen, notizen_kurz, verknuepfung_aus
from .models import (
    VERKNUEPFUNGS_TYPEN,
    Anhang,
    Freigabe,
    Notiz,
    Notizbuch,
    NotizStand,
    NotizVerweis,
    Papierkorb,
    Verknuepfung,
)
from .schemas import (
    AnhangAus,
    NotizAn,
    NotizAus,
    NotizKurzAus,
    NotizPatch,
    PapierkorbAus,
    StandAus,
    StandKurzAus,
    VerknuepfungAn,
    VerknuepfungAus,
)
from .routes_netz import verbinden_paare, verbundene_ids
from .suche import suchen
from .util import dateiname_saeubern, jetzt, tags_lesen, tags_normalisieren

router = APIRouter()


def _notizbuch_pruefen(db: Session, owner_sub: str, buch_id: int | None) -> None:
    """Fremde Notizbuch-IDs abweisen.

    Ohne diese Pruefung koennte man die eigene Notiz in ein fremdes Notizbuch
    haengen, die Notiz bliebe zwar unsichtbar (Listen filtern auf owner_sub),
    aber die Zaehler des anderen Kontos wuerden sich bewegen. Ein stiller Kanal
    nach draussen ist immer noch ein Kanal.
    """
    if buch_id is None:
        return
    treffer = db.scalar(
        select(Notizbuch.id).where(Notizbuch.id == buch_id, Notizbuch.owner_sub == owner_sub)
    )
    if treffer is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unbekanntes Notizbuch")


# --- Notizen -------------------------------------------------------------


# Was der Filter „hat …" kennt. Je Wort eine Bedingung, mehrere gelten
# zusammen (UND), wie bei den Tags.
HAT_FILTER = {"aufgabe", "termin", "projekt", "kontakt", "anhang", "freigabe", "verweis", "angeheftet"}
SORTIERUNGEN = {"geaendert", "erstellt", "titel"}


def _liste_aus(roh: str | None) -> list[str]:
    return [t.strip().lower() for t in (roh or "").split(",") if t.strip()]


def _filter_bedingungen(
    me: Me,
    *,
    notizbuch_id: int | None,
    ohne_notizbuch: bool,
    tags: list[str],
    hat: list[str],
    verknuepft: str | None,
    archivierte: bool,
) -> list:
    """Alle Filter der Liste als SQL-Bedingungen.

    Eine Stelle fuer beide Wege: bis 2026-11-21 galten Tag und Verknuepfung
    nur ohne Suchwort, mit Suchwort fielen sie still weg und die Liste zeigte
    Treffer, die der gewaehlte Tag ausschloss.
    """
    unbekannt = set(hat) - HAT_FILTER
    if unbekannt:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unbekannter Filter: {', '.join(sorted(unbekannt))}")
    wo: list = [Notiz.owner_sub == me.sub]
    if not archivierte:
        wo.append(Notiz.archiviert.is_(False))
    if ohne_notizbuch:
        wo.append(Notiz.notizbuch_id.is_(None))
    elif notizbuch_id is not None:
        wo.append(Notiz.notizbuch_id == notizbuch_id)
    for tag in tags:
        # Tags liegen als kommagetrennte Liste, mit den Kommas an beiden Enden
        # trifft LIKE genau ein ganzes Tag und nicht dessen Anfang ("haus" darf
        # "hausrat" nicht mitnehmen). % und _ im Tag zaehlen woertlich.
        muster = tag.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        wo.append(func.lower("," + Notiz.tags + ",").like(f"%,{muster},%", escape="\\"))
    for art in hat:
        if art in VERKNUEPFUNGS_TYPEN:
            wo.append(Notiz.id.in_(
                select(Verknuepfung.notiz_id).where(Verknuepfung.owner_sub == me.sub, Verknuepfung.typ == art)
            ))
        elif art == "anhang":
            wo.append(Notiz.id.in_(select(Anhang.notiz_id).where(Anhang.owner_sub == me.sub)))
        elif art == "freigabe":
            wo.append(Notiz.id.in_(
                select(Freigabe.notiz_id).where(Freigabe.owner_sub == me.sub, Freigabe.widerrufen_am.is_(None))
            ))
        elif art == "verweis":
            # Von Hand verbunden oder ein [[Titel]] im Text.
            wo.append(or_(
                Notiz.id.in_(select(NotizVerweis.a_id).where(NotizVerweis.owner_sub == me.sub)),
                Notiz.id.in_(select(NotizVerweis.b_id).where(NotizVerweis.owner_sub == me.sub)),
                Notiz.inhalt.contains("[["),
            ))
        elif art == "angeheftet":
            wo.append(Notiz.angeheftet.is_(True))
    if verknuepft:
        typ, _, ref = verknuepft.partition(":")
        if not typ or not ref:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "verknuepft erwartet 'typ:kennung'")
        wo.append(Notiz.id.in_(
            select(Verknuepfung.notiz_id).where(
                Verknuepfung.owner_sub == me.sub,
                Verknuepfung.typ == typ,
                Verknuepfung.ref == ref,
            )
        ))
    return wo


def _reihenfolge(sortierung: str):
    if sortierung == "erstellt":
        return (Notiz.angeheftet.desc(), Notiz.erstellt_am.desc())
    if sortierung == "titel":
        # Ohne Titel ans Ende, sonst stuenden sie alle vorn.
        return (Notiz.angeheftet.desc(), (Notiz.titel == "").asc(), func.lower(Notiz.titel).asc())
    return (Notiz.angeheftet.desc(), Notiz.geaendert_am.desc())


@router.get("", response_model=list[NotizKurzAus])
def liste(
    q: str | None = Query(default=None, description="Volltextsuche ueber Titel, Text und Tags"),
    notizbuch_id: int | None = None,
    ohne_notizbuch: bool = Query(default=False, description="Nur Notizen ohne Notizbuch"),
    tag: str | None = Query(default=None, description="Ein Tag oder mehrere, kommagetrennt; alle muessen passen"),
    hat: str | None = Query(
        default=None,
        description="Kommagetrennt aus aufgabe, termin, projekt, kontakt, anhang, freigabe, verweis, angeheftet",
    ),
    sortierung: str | None = Query(
        default=None,
        description="geaendert (Vorgabe), erstellt oder titel; mit Suchwort ohne Angabe nach Relevanz",
    ),
    verknuepft: str | None = Query(
        default=None,
        description=(
            "Rueckwaerts-Suche als 'typ:kennung', z. B. 'termin:5f3c…'. Damit findet "
            "die Gegenseite (Kalender, ProjectDeck, Post) die Notizen zu ihrem Objekt."
        ),
    ),
    archivierte: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[NotizKurzAus]:
    if sortierung is not None and sortierung not in SORTIERUNGEN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unbekannte Sortierung: {sortierung}")
    wo = _filter_bedingungen(
        me,
        notizbuch_id=notizbuch_id,
        ohne_notizbuch=ohne_notizbuch,
        tags=_liste_aus(tag),
        hat=_liste_aus(hat),
        verknuepft=verknuepft,
        archivierte=archivierte,
    )
    if q:
        # Die Volltextsuche liefert nach Relevanz; die Filter greifen danach.
        # Deshalb mit weitem Deckel suchen, sonst schnitte er Treffer ab, die
        # der Filter behalten haette.
        treffer = suchen(
            db,
            me.sub,
            q,
            notizbuch_id=None if ohne_notizbuch else notizbuch_id,
            archivierte=archivierte,
            limit=max(limit, 500),
        )
        if not treffer:
            return []
        rang = {nid: i for i, (nid, _) in enumerate(treffer)}
        ausschnitte = dict(treffer)
        anfrage = select(Notiz).where(*wo, Notiz.id.in_(rang.keys()))
        if sortierung:
            notizen = list(db.scalars(anfrage.order_by(*_reihenfolge(sortierung)).limit(limit)).all())
        else:
            notizen = sorted(db.scalars(anfrage).all(), key=lambda n: rang[n.id])[:limit]
        return notizen_kurz(db, notizen, ausschnitte)

    anfrage = select(Notiz).where(*wo).order_by(*_reihenfolge(sortierung or "geaendert")).limit(limit)
    return notizen_kurz(db, list(db.scalars(anfrage).all()))


@router.get("/tags", response_model=list[str])
def tag_liste(
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[str]:
    """Alle vergebenen Tags, fuer Filterleiste und Eingabe-Vorschlaege."""
    alle: set[str] = set()
    for (roh,) in db.execute(
        select(Notiz.tags).where(Notiz.owner_sub == me.sub, Notiz.tags != "")
    ):
        alle.update(tags_lesen(roh))
    return sorted(alle)


@router.get("/verknuepft", response_model=dict[str, list[NotizKurzAus]])
def verknuepft_sammel(
    typ: str = Query(description="Verknuepfungstyp, z. B. 'aufgabe'"),
    refs: str = Query(
        description="Kennungen des Gegenstuecks, kommagetrennt. Hoechstens 200.",
        max_length=8000,
    ),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> dict[str, list[NotizKurzAus]]:
    """Notizen zu **mehreren** Gegenstuecken auf einmal.

    Der Grund fuer diese Route ist die Anzahl der Anfragen, nicht Bequemlichkeit.
    Die Gegenseite (Aufgabenliste, Projektansicht) zeigt Dutzende Zeilen und will
    je Zeile wissen, ob eine Notiz daranhaengt. Mit ``?verknuepft=typ:kennung``
    waere das eine Anfrage je Zeile; bei sechzig offenen Aufgaben also sechzig.
    Genau so ist am 2026-09-13 schon einmal eine App-Kette in den Anfragedeckel
    des Gegenuebers gelaufen, und weil dort jeder Fehler zu einer Null wurde, sah
    das Ergebnis vollstaendig aus, obwohl es leer war.

    Unbekannte Kennungen erscheinen **nicht** im Ergebnis. Der Aufrufer soll
    „keine Notiz" am fehlenden Schluessel erkennen und nicht an einer leeren
    Liste, die auch ein verschluckter Fehler sein koennte.
    """
    if typ not in VERKNUEPFUNGS_TYPEN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unbekannter Verknuepfungstyp: {typ}")
    kennungen = [r.strip() for r in refs.split(",") if r.strip()]
    if not kennungen:
        return {}
    if len(kennungen) > 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Hoechstens 200 Kennungen je Anfrage")

    paare = db.execute(
        select(Verknuepfung.ref, Verknuepfung.notiz_id).where(
            Verknuepfung.owner_sub == me.sub,
            Verknuepfung.typ == typ,
            Verknuepfung.ref.in_(kennungen),
        )
    ).all()
    if not paare:
        return {}

    notizen = db.scalars(
        select(Notiz).where(
            Notiz.owner_sub == me.sub,
            Notiz.archiviert.is_(False),
            Notiz.id.in_({nid for _, nid in paare}),
        )
    ).all()
    # Eine Sammelabfrage fuer die Zaehler, danach nur noch zuordnen.
    kurz = {k.id: k for k in notizen_kurz(db, list(notizen))}

    ergebnis: dict[str, list[NotizKurzAus]] = {}
    for ref, notiz_id in paare:
        eintrag = kurz.get(notiz_id)
        if eintrag is None:
            continue  # archiviert oder inzwischen geloescht
        ergebnis.setdefault(ref, []).append(eintrag)
    return ergebnis


@router.delete("/verknuepft", response_model=dict[str, int])
def verknuepft_entfernen(
    typ: str = Query(description="Verknuepfungstyp, z. B. 'aufgabe'"),
    ref: str = Query(min_length=1, max_length=200, description="Kennung des Gegenstuecks"),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    """Alle Verknuepfungen des Kontos auf ein Gegenstueck entfernen.

    Fuer die Gegenseite, wenn sie ihr Objekt loescht (der Aufgaben-Dienst ruft
    das beim Loeschen einer Aufgabe). Vorher blieb die Verknuepfung stehen und
    zeigte mit ihrer kopierten Beschriftung auf etwas, das es nicht mehr gibt.
    Kein Treffer ist kein Fehler: die Antwort nennt die Anzahl.
    """
    if typ not in VERKNUEPFUNGS_TYPEN:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unbekannter Verknuepfungstyp: {typ}")
    ergebnis = db.execute(
        delete(Verknuepfung).where(
            Verknuepfung.owner_sub == me.sub,
            Verknuepfung.typ == typ,
            Verknuepfung.ref == ref.strip(),
        )
    )
    entfernt = ergebnis.rowcount or 0
    # Auch aus dem Papierkorb, sonst braechte das Zurueckholen einer Notiz
    # die Verknuepfung auf das geloeschte Gegenstueck wieder mit.
    for eintrag in db.scalars(
        select(Papierkorb).where(Papierkorb.owner_sub == me.sub, Papierkorb.daten.contains(ref.strip()))
    ):
        d = json.loads(eintrag.daten)
        vorher = d.get("verknuepfungen", [])
        nachher = [v for v in vorher if not (v.get("typ") == typ and v.get("ref") == ref.strip())]
        if len(nachher) != len(vorher):
            d["verknuepfungen"] = nachher
            eintrag.daten = json.dumps(d, ensure_ascii=False)
            entfernt += len(vorher) - len(nachher)
    db.commit()
    return {"entfernt": entfernt}


@router.post("", response_model=NotizAus, status_code=status.HTTP_201_CREATED)
def anlegen(
    daten: NotizAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> NotizAus:
    """Notiz anlegen, auf Wunsch samt ihrer Verknuepfung.

    Mit ``verknuepfung`` im Rumpf ist das der Weg fuer den Knopf „Notiz
    dazu" in Kalender, Aufgaben und ProjectDeck: die Notiz entsteht **dort**,
    wo man gerade arbeitet, und ist im selben Augenblick verknuepft. Beides
    liegt in **einer** Transaktion, es gibt also keinen Zustand, in dem die
    Notiz schon existiert und ihr Bezug noch nicht (siehe ``NotizAn``).
    """
    _notizbuch_pruefen(db, me.sub, daten.notizbuch_id)
    notiz = Notiz(
        owner_sub=me.sub,
        titel=daten.titel.strip(),
        inhalt=daten.inhalt,
        notizbuch_id=daten.notizbuch_id,
        tags=tags_normalisieren(daten.tags),
        angeheftet=daten.angeheftet,
        archiviert=daten.archiviert,
    )
    db.add(notiz)
    if daten.verknuepfung is not None:
        # Das ``flush`` vergibt die Kennung der Notiz, ohne die Transaktion zu
        # schliessen. Erst danach kann die Verknuepfung darauf zeigen, und der
        # gemeinsame ``commit`` unten macht aus beidem einen Schritt.
        db.flush()
        db.add(
            Verknuepfung(
                owner_sub=me.sub,
                notiz_id=notiz.id,
                typ=daten.verknuepfung.typ,
                ref=daten.verknuepfung.ref.strip(),
                label=daten.verknuepfung.label.strip(),
            )
        )
    db.commit()
    db.refresh(notiz)
    return notiz_aus(notiz)


@router.get("/{notiz_id}", response_model=NotizAus)
def einzeln(
    notiz_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> NotizAus:
    return notiz_aus(notiz_holen(db, me.sub, notiz_id))


@router.patch("/{notiz_id}", response_model=NotizAus)
def aendern(
    notiz_id: int,
    daten: NotizPatch,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> NotizAus:
    notiz = notiz_holen(db, me.sub, notiz_id)
    if daten.basis_geaendert_am is not None:
        basis = daten.basis_geaendert_am
        # Der Bestand liegt als naives UTC; ein Client darf den Stempel auch
        # mit Zeitzone zurueckgeben (die Android-App etwa haengt ein Z an).
        if basis.tzinfo is not None:
            basis = basis.astimezone(UTC).replace(tzinfo=None)
        if basis != notiz.geaendert_am:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "Die Notiz wurde inzwischen in einem anderen Fenster oder auf "
                "einem anderen Geraet gespeichert. Diese Fassung wurde nicht "
                "uebernommen: Text kopieren, Seite neu laden, zusammenfuehren.",
            )
    if (
        (daten.titel is not None and daten.titel.strip() != notiz.titel)
        or (daten.inhalt is not None and daten.inhalt != notiz.inhalt)
        or (daten.tags is not None and tags_normalisieren(daten.tags) != notiz.tags)
    ):
        stand_ablegen(db, notiz)
    if daten.titel is not None:
        notiz.titel = daten.titel.strip()
    if daten.inhalt is not None:
        notiz.inhalt = daten.inhalt
    if daten.notizbuch_loesen:
        notiz.notizbuch_id = None
    elif daten.notizbuch_id is not None:
        _notizbuch_pruefen(db, me.sub, daten.notizbuch_id)
        notiz.notizbuch_id = daten.notizbuch_id
    if daten.tags is not None:
        notiz.tags = tags_normalisieren(daten.tags)
    if daten.angeheftet is not None:
        notiz.angeheftet = daten.angeheftet
    if daten.archiviert is not None:
        notiz.archiviert = daten.archiviert
    db.commit()
    db.refresh(notiz)
    return notiz_aus(notiz)


# --- Fruehere Staende ----------------------------------------------------

STAENDE_JE_NOTIZ = 5
STAND_RUHE_MINUTEN = 10


def stand_ablegen(db: Session, notiz: Notiz, erzwingen: bool = False) -> None:
    """Den jetzigen Stand ablegen, bevor er ueberschrieben wird.

    Ohne ``erzwingen`` nur, wenn er seit ``STAND_RUHE_MINUTEN`` ruht (Begruendung
    am Modell ``NotizStand``). Das Wiederherstellen erzwingt: so laesst sich auch
    ein Zurueckholen wieder zuruecknehmen.
    """
    if not erzwingen and notiz.geaendert_am > jetzt() - timedelta(minutes=STAND_RUHE_MINUTEN):
        return
    db.add(NotizStand(
        owner_sub=notiz.owner_sub, notiz_id=notiz.id, titel=notiz.titel,
        inhalt=notiz.inhalt, tags=notiz.tags, stand_vom=notiz.geaendert_am,
    ))
    db.flush()
    alte = db.scalars(
        select(NotizStand.id)
        .where(NotizStand.notiz_id == notiz.id, NotizStand.owner_sub == notiz.owner_sub)
        .order_by(NotizStand.id.desc())
        .offset(STAENDE_JE_NOTIZ)
    ).all()
    if alte:
        db.execute(delete(NotizStand).where(NotizStand.id.in_(alte)))


def _stand_holen(db: Session, sub: str, notiz_id: int, stand_id: int) -> NotizStand:
    stand = db.scalar(select(NotizStand).where(
        NotizStand.id == stand_id, NotizStand.notiz_id == notiz_id, NotizStand.owner_sub == sub
    ))
    if stand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Stand nicht gefunden")
    return stand


@router.get("/{notiz_id}/staende", response_model=list[StandKurzAus])
def staende(notiz_id: int, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> list[StandKurzAus]:
    """Fruehere Staende, juengster zuerst, ohne Text (der kommt einzeln)."""
    notiz_holen(db, me.sub, notiz_id)
    zeilen = db.scalars(
        select(NotizStand)
        .where(NotizStand.notiz_id == notiz_id, NotizStand.owner_sub == me.sub)
        .order_by(NotizStand.id.desc())
    ).all()
    return [StandKurzAus(id=z.id, titel=z.titel, stand_vom=z.stand_vom, zeichen=len(z.inhalt)) for z in zeilen]


@router.get("/{notiz_id}/staende/{stand_id}", response_model=StandAus)
def stand(notiz_id: int, stand_id: int, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> StandAus:
    z = _stand_holen(db, me.sub, notiz_id, stand_id)
    return StandAus(id=z.id, titel=z.titel, inhalt=z.inhalt, tags=tags_lesen(z.tags), stand_vom=z.stand_vom)


@router.post("/{notiz_id}/staende/{stand_id}/wiederherstellen", response_model=NotizAus)
def stand_wiederherstellen(
    notiz_id: int, stand_id: int, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)
) -> NotizAus:
    """Titel, Text und Tags aus dem Stand uebernehmen; der jetzige wird vorher abgelegt.

    Notizbuch, Anheften und Archiv bleiben, wie sie sind: ein Stand ist der Text,
    nicht der Ort der Notiz.
    """
    notiz = notiz_holen(db, me.sub, notiz_id)
    z = _stand_holen(db, me.sub, notiz_id, stand_id)
    titel, inhalt, tags = z.titel, z.inhalt, z.tags
    stand_ablegen(db, notiz, erzwingen=True)
    notiz.titel, notiz.inhalt, notiz.tags = titel, inhalt, tags
    db.commit()
    db.refresh(notiz)
    return notiz_aus(notiz)


@router.delete("/{notiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def loeschen(
    notiz_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> None:
    """Notiz endgueltig entfernen: samt Anhaengen auf der Platte.

    Offene Freigaben laufen danach ins Leere und melden das (410).
    Verschluesselte Schnappschuesse bleiben bestehen: ihr Inhalt liegt in der
    Freigabe selbst, nicht in der Notiz, und ein bereits verteilter Link soll
    nicht dadurch brechen, dass man im eigenen Bestand aufraeumt.
    """
    notiz = notiz_holen(db, me.sub, notiz_id)
    ablagen = [a.ablage for a in notiz.anhaenge]
    # In den Papierkorb (seit 2026-11-07): 30 Tage wiederherstellbar, ohne Anhaenge.
    db.add(Papierkorb(
        owner_sub=me.sub, alte_id=notiz.id, titel=notiz.titel,
        daten=json.dumps({
            "titel": notiz.titel, "inhalt": notiz.inhalt, "tags": notiz.tags,
            "notizbuch_id": notiz.notizbuch_id, "angeheftet": notiz.angeheftet,
            "archiviert": notiz.archiviert,
            "erstellt_am": notiz.erstellt_am.isoformat() if notiz.erstellt_am else None,
            "anhaenge": len(ablagen),
            "verknuepfungen": [{"typ": v.typ, "ref": v.ref, "label": v.label} for v in notiz.verknuepfungen],
            # Kennungen der verbundenen Notizen; beim Zurueckholen nur die, die es noch gibt.
            "verbunden": verbundene_ids(db, me.sub, notiz.id),
        }, ensure_ascii=False),
    ))
    db.delete(notiz)
    db.commit()
    for name in ablagen:
        ablage.loeschen(name)


PAPIERKORB_TAGE = 30


def _papierkorb_leeren(db: Session, sub: str) -> None:
    grenze = jetzt() - timedelta(days=PAPIERKORB_TAGE)
    db.execute(delete(Papierkorb).where(Papierkorb.owner_sub == sub, Papierkorb.geloescht_am < grenze))


@router.get("/papierkorb/liste", response_model=list[PapierkorbAus])
def papierkorb(me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> list[PapierkorbAus]:
    """Geloeschte Notizen der letzten 30 Tage, juengste zuerst."""
    _papierkorb_leeren(db, me.sub)
    db.commit()
    zeilen = db.scalars(
        select(Papierkorb).where(Papierkorb.owner_sub == me.sub).order_by(Papierkorb.geloescht_am.desc())
    ).all()
    return [PapierkorbAus(id=z.id, titel=z.titel, geloescht_am=z.geloescht_am,
                          anhaenge=json.loads(z.daten).get("anhaenge", 0)) for z in zeilen]


@router.post("/papierkorb/{eintrag_id}/wiederherstellen", response_model=NotizAus)
def wiederherstellen(eintrag_id: int, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> NotizAus:
    z = db.scalars(select(Papierkorb).where(Papierkorb.id == eintrag_id, Papierkorb.owner_sub == me.sub)).first()
    if z is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Nicht im Papierkorb")
    d = json.loads(z.daten)
    buch = d.get("notizbuch_id")
    if buch is not None and db.scalars(
        select(Notizbuch.id).where(Notizbuch.id == buch, Notizbuch.owner_sub == me.sub)
    ).first() is None:
        buch = None  # Notizbuch inzwischen geloescht: ohne Notizbuch zurueck
    notiz = Notiz(owner_sub=me.sub, notizbuch_id=buch, titel=d.get("titel", ""),
                  inhalt=d.get("inhalt", ""), tags=d.get("tags", ""),
                  angeheftet=bool(d.get("angeheftet")), archiviert=bool(d.get("archiviert")))
    db.add(notiz)
    db.flush()
    for v in d.get("verknuepfungen", []):
        db.add(Verknuepfung(owner_sub=me.sub, notiz_id=notiz.id, typ=v["typ"], ref=v["ref"], label=v.get("label", "")))
    verbunden = {i for i in d.get("verbunden", []) if isinstance(i, int)}
    if verbunden:
        noch_da = set(db.scalars(select(Notiz.id).where(Notiz.owner_sub == me.sub, Notiz.id.in_(verbunden))))
        for andere in noch_da:
            verbinden_paare(db, me.sub, [notiz.id, andere])
    db.delete(z)
    db.commit()
    return notiz_aus(notiz_holen(db, me.sub, notiz.id))


# --- Verknuepfungen ------------------------------------------------------


@router.post(
    "/{notiz_id}/verknuepfungen",
    response_model=VerknuepfungAus,
    status_code=status.HTTP_201_CREATED,
)
def verknuepfen(
    notiz_id: int,
    daten: VerknuepfungAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> VerknuepfungAus:
    notiz = notiz_holen(db, me.sub, notiz_id)
    v = Verknuepfung(
        owner_sub=me.sub,
        notiz_id=notiz.id,
        typ=daten.typ,
        ref=daten.ref.strip(),
        label=daten.label.strip(),
    )
    db.add(v)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        vorhanden = db.scalar(
            select(Verknuepfung).where(
                Verknuepfung.notiz_id == notiz.id,
                Verknuepfung.typ == daten.typ,
                Verknuepfung.ref == daten.ref.strip(),
            )
        )
        if vorhanden is None:
            raise
        return verknuepfung_aus(vorhanden)
    db.refresh(v)
    return verknuepfung_aus(v)


@router.delete(
    "/{notiz_id}/verknuepfungen/{verknuepfung_id}", status_code=status.HTTP_204_NO_CONTENT
)
def entknuepfen(
    notiz_id: int,
    verknuepfung_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> None:
    v = db.scalar(
        select(Verknuepfung).where(
            Verknuepfung.id == verknuepfung_id,
            Verknuepfung.notiz_id == notiz_id,
            Verknuepfung.owner_sub == me.sub,
        )
    )
    if v is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verknuepfung nicht gefunden")
    db.delete(v)
    db.commit()


# --- Anhaenge ------------------------------------------------------------


def _belegt(db: Session, owner_sub: str) -> int:
    return db.scalar(
        select(func.coalesce(func.sum(Anhang.groesse), 0)).where(Anhang.owner_sub == owner_sub)
    ) or 0


@router.get("/{notiz_id}/anhaenge", response_model=list[AnhangAus])
def anhang_liste(
    notiz_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[AnhangAus]:
    return [anhang_aus(a) for a in notiz_holen(db, me.sub, notiz_id).anhaenge]


@router.post(
    "/{notiz_id}/anhaenge", response_model=AnhangAus, status_code=status.HTTP_201_CREATED
)
async def anhang_hochladen(
    notiz_id: int,
    datei: UploadFile,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> AnhangAus:
    notiz = notiz_holen(db, me.sub, notiz_id)
    frei_konto = settings.anhang_quote_bytes - _belegt(db, me.sub)
    # Auch der Platte einen Puffer lassen: eine vollgelaufene Partition trifft
    # nicht nur diesen Dienst, sondern alles auf demselben Volume.
    frei = min(frei_konto, max(ablage.platte_frei() - 200 * 1024 * 1024, 0))
    name, mime, groesse, pruefsumme = await ablage.speichern(datei, frei)
    anhang = Anhang(
        owner_sub=me.sub,
        notiz_id=notiz.id,
        dateiname=dateiname_saeubern(datei.filename or "datei"),
        mime=mime,
        groesse=groesse,
        ablage=name,
        pruefsumme=pruefsumme,
    )
    db.add(anhang)
    try:
        db.commit()
    except Exception:
        db.rollback()
        ablage.loeschen(name)
        raise
    db.refresh(anhang)
    return anhang_aus(anhang)


@router.get("/{notiz_id}/anhaenge/{anhang_id}")
def anhang_holen(
    notiz_id: int,
    anhang_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Response:
    anhang = db.scalar(
        select(Anhang).where(
            Anhang.id == anhang_id, Anhang.notiz_id == notiz_id, Anhang.owner_sub == me.sub
        )
    )
    if anhang is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anhang nicht gefunden")
    return datei_antwort(anhang)


@router.delete("/{notiz_id}/anhaenge/{anhang_id}", status_code=status.HTTP_204_NO_CONTENT)
def anhang_loeschen(
    notiz_id: int,
    anhang_id: int,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> None:
    anhang = db.scalar(
        select(Anhang).where(
            Anhang.id == anhang_id, Anhang.notiz_id == notiz_id, Anhang.owner_sub == me.sub
        )
    )
    if anhang is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anhang nicht gefunden")
    name = anhang.ablage
    db.delete(anhang)
    db.commit()
    ablage.loeschen(name)


def datei_antwort(anhang: Anhang) -> FileResponse:
    """Anhang ausliefern, nie zur Anzeige im eigenen Ursprung.

    ``Content-Disposition: attachment`` plus ``nosniff`` plus eine
    Content-Security-Policy, die alles verbietet: selbst wenn eine Datei durch
    die Typpruefung schluepfte und HTML enthielte, wuerde der Browser sie
    herunterladen statt sie als Seite im Ursprung der Anwendung auszufuehren.
    Bilder zeigt die Oberflaeche als Vorschau ueber ``blob:``-Adressen, die
    keinen Zugriff auf Cookies oder Sitzung haben; alles andere bleibt Download.
    """
    pfad = ablage.pfad(anhang.ablage)
    if not pfad.is_file():
        raise HTTPException(status.HTTP_410_GONE, "Anhang-Datei fehlt in der Ablage")
    return FileResponse(
        pfad,
        media_type=anhang.mime,
        filename=anhang.dateiname,
        content_disposition_type="attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, max-age=300",
        },
    )
