from datetime import UTC

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import ablage
from .auth import Me, verify_jwt
from .config import settings
from .db import get_db
from .helfer import anhang_aus, notiz_aus, notiz_holen, notizen_kurz, verknuepfung_aus
from .models import VERKNUEPFUNGS_TYPEN, Anhang, Notiz, Notizbuch, Verknuepfung
from .schemas import (
    AnhangAus,
    NotizAn,
    NotizAus,
    NotizKurzAus,
    NotizPatch,
    VerknuepfungAn,
    VerknuepfungAus,
)
from .suche import suchen
from .util import dateiname_saeubern, tags_lesen, tags_normalisieren

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


@router.get("", response_model=list[NotizKurzAus])
def liste(
    q: str | None = Query(default=None, description="Volltextsuche ueber Titel, Text und Tags"),
    notizbuch_id: int | None = None,
    tag: str | None = None,
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
    if q:
        treffer = suchen(
            db,
            me.sub,
            q,
            notizbuch_id=notizbuch_id,
            archivierte=archivierte,
            limit=limit,
        )
        if not treffer:
            return []
        reihenfolge = {nid: i for i, (nid, _) in enumerate(treffer)}
        ausschnitte = dict(treffer)
        notizen = db.scalars(
            select(Notiz).where(Notiz.owner_sub == me.sub, Notiz.id.in_(reihenfolge.keys()))
        ).all()
        notizen = sorted(notizen, key=lambda n: reihenfolge[n.id])
        return notizen_kurz(db, list(notizen), ausschnitte)

    anfrage = select(Notiz).where(Notiz.owner_sub == me.sub)
    if not archivierte:
        anfrage = anfrage.where(Notiz.archiviert.is_(False))
    if notizbuch_id is not None:
        anfrage = anfrage.where(Notiz.notizbuch_id == notizbuch_id)
    if tag:
        # Tags liegen als kommagetrennte Liste, mit den Kommas an beiden Enden
        # trifft LIKE genau ein ganzes Tag und nicht dessen Anfang ("haus" darf
        # "hausrat" nicht mitnehmen).
        anfrage = anfrage.where(
            func.lower("," + Notiz.tags + ",").like(f"%,{tag.strip().lower()},%")
        )
    if verknuepft:
        typ, _, ref = verknuepft.partition(":")
        if not typ or not ref:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "verknuepft erwartet 'typ:kennung'")
        anfrage = anfrage.where(
            Notiz.id.in_(
                select(Verknuepfung.notiz_id).where(
                    Verknuepfung.owner_sub == me.sub,
                    Verknuepfung.typ == typ,
                    Verknuepfung.ref == ref,
                )
            )
        )
    anfrage = anfrage.order_by(Notiz.angeheftet.desc(), Notiz.geaendert_am.desc()).limit(limit)
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

    ★ Der Grund fuer diese Route ist die Anzahl der Anfragen, nicht Bequemlichkeit.
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


@router.post("", response_model=NotizAus, status_code=status.HTTP_201_CREATED)
def anlegen(
    daten: NotizAn,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> NotizAus:
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
    db.delete(notiz)
    db.commit()
    for name in ablagen:
        ablage.loeschen(name)


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
