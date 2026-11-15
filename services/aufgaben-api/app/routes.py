"""Die Routen des Aufgaben-Dienstes.

Jede Abfrage an `aufgaben` filtert auf ``owner_sub``. Es gibt keinen Pfad ohne
diesen Filter; eine fremde Kennung ergibt 404, nicht 403, damit sich ihr
Vorhandensein nicht erraten laesst.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from . import belegung, kalender
from .auth import Me, verify_jwt
from .db import get_db
from .models import Aufgabe, Liste, ListenAngelegt, neue_id
from .schemas import (
    BERLIN,
    AufgabeAenderung,
    AufgabeAus,
    AufgabeNeu,
    Kapazitaet,
    ListeAenderung,
    ListeAus,
    ListeNeu,
    TAGESZEITEN,
    Plan,
    PlanAnfrage,
    PlanVorschlag,
    PlanZurueck,
    TagAus,
    Verschieben,
    Ziel,
    ZielAenderung,
    ZielNeu,
    berlin_naiv,
)

router = APIRouter()

#: So viele Erledigte liefert eine Abfrage hoechstens, die juengsten zuerst.
MAX_ERLEDIGTE = 100

#: Der Planer rechnet Energie englisch (Todo-Schema des Kalenders).
_ENERGIE_ENGLISCH = {"niedrig": "low", "mittel": "medium", "hoch": "high"}


def _berlin_jetzt() -> datetime:
    return datetime.now(BERLIN).replace(tzinfo=None)


#: Die Bereiche neben den Projekten (Entscheid K3/K36, 13.11.; loest die
#: sieben Startlisten vom 04.11. ab, die fuer kein Konto je angelegt waren).
#: Name und ob sie nach aussen neutral bleibt (K20).
STARTLISTEN = (
    ("Privat", False),
    ("Haushalt", False),
    ("Gesundheit", True),
)


def _unzulaessig(text: str) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, text)


def _bezug_pruefen(db: Session, me: Me, aufgabe: Aufgabe) -> None:
    """Was ueber das einzelne Feld hinausgeht, nach dem Setzen aller Felder.

    Erst danach, weil ein PUT Projekt leeren und Liste setzen in einem
    Aufruf darf; Feld fuer Feld geprueft waere das ein Fehler.
    """
    if aufgabe.projekt and aufgabe.liste_id:
        raise _unzulaessig("Eine Aufgabe gehoert zu einem Projekt oder einer Liste, nicht zu beiden")
    if aufgabe.liste_id and db.execute(
        select(Liste.id).where(Liste.id == aufgabe.liste_id, Liste.owner_sub == me.sub)
    ).first() is None:
        raise _unzulaessig("Liste nicht gefunden")
    if aufgabe.wartet_auf_id:
        if aufgabe.wartet_auf_id == aufgabe.id:
            raise _unzulaessig("Eine Aufgabe kann nicht auf sich selbst warten")
        if db.execute(
            select(Aufgabe.id).where(Aufgabe.id == aufgabe.wartet_auf_id, Aufgabe.owner_sub == me.sub)
        ).first() is None:
            raise _unzulaessig("Aufgabe, auf die gewartet wird, nicht gefunden")
    if aufgabe.wo != "ort":
        aufgabe.ort_name = None
    elif not aufgabe.ort_name:
        raise _unzulaessig("Ein bestimmter Ort braucht einen Namen")
    if aufgabe.start and aufgabe.ende and aufgabe.ende <= aufgabe.start:
        raise _unzulaessig("Ende liegt nicht nach dem Start")


def _wartende(db: Session, me: Me, aufgaben: list[Aufgabe], stichtag: date) -> set[str]:
    """Kennungen der Aufgaben, die am Stichtag noch warten.

    Ein Datum gewinnt: bis dahin wartet sie, danach nicht mehr, auch wenn ein
    Grund dabei steht (der erklaert dann nur). Ohne Datum wartet sie, solange
    die genannte Aufgabe offen ist; ist die geloescht, wartet sie nicht. Ein
    Grund allein wartet, bis jemand ihn leert (so kommen die blockierten
    Punkte aus dem ProjectDeck an).
    """
    auf = {a.wartet_auf_id for a in aufgaben if a.wartet_auf_id and not a.wartet_bis}
    offen_auf = set(db.execute(
        select(Aufgabe.id).where(
            Aufgabe.owner_sub == me.sub, Aufgabe.id.in_(auf), Aufgabe.erledigt.is_(False))
    ).scalars()) if auf else set()
    wartend = set()
    for a in aufgaben:
        if a.wartet_bis:
            if a.wartet_bis > stichtag:
                wartend.add(a.id)
        elif a.wartet_auf_id:
            if a.wartet_auf_id in offen_auf:
                wartend.add(a.id)
        elif a.wartet_grund:
            wartend.add(a.id)
    return wartend


def _mit_wartet(db: Session, me: Me, aufgaben: list[Aufgabe]) -> list[Aufgabe]:
    wartend = _wartende(db, me, aufgaben, _berlin_jetzt().date())
    for a in aufgaben:
        a.wartet = a.id in wartend
    return aufgaben


def _hole(db: Session, me: Me, aufgabe_id: str) -> Aufgabe:
    aufgabe = db.execute(
        select(Aufgabe).where(Aufgabe.id == aufgabe_id, Aufgabe.owner_sub == me.sub)
    ).scalar_one_or_none()
    if aufgabe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aufgabe nicht gefunden")
    return aufgabe


# --- Aufgaben ------------------------------------------------------------


@router.get("/aufgaben", response_model=list[AufgabeAus])
def liste(
    erledigte: bool = Query(False, description="statt der offenen die zuletzt erledigten"),
    projekt: str | None = Query(None, max_length=120, description="nur die eines Projekts (Slug)"),
    liste_id: str | None = Query(None, max_length=36, description="nur die einer Liste"),
    herkunft: str | None = Query(
        None, max_length=64, description="genau diese Herkunft, offen oder erledigt (fuer den Umzug)"),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[Aufgabe]:
    abfrage = select(Aufgabe).where(Aufgabe.owner_sub == me.sub)
    if herkunft is not None:
        abfrage = abfrage.where(Aufgabe.herkunft == herkunft)
        return _mit_wartet(db, me, list(db.execute(abfrage).scalars()))
    abfrage = abfrage.where(Aufgabe.erledigt == erledigte)
    if projekt is not None:
        abfrage = abfrage.where(Aufgabe.projekt == projekt)
    if liste_id is not None:
        abfrage = abfrage.where(Aufgabe.liste_id == liste_id)
    if erledigte:
        abfrage = abfrage.order_by(Aufgabe.erledigt_am.desc()).limit(MAX_ERLEDIGTE)
    else:
        abfrage = abfrage.order_by(Aufgabe.erstellt_am)
    return _mit_wartet(db, me, list(db.execute(abfrage).scalars()))


#: So viele Tage umfasst eine Zeitraum-Abfrage hoechstens: das Bootstrap-Fenster der
#: Kalender-App (bis 120 Tage, `kalender-bff` routes_mobile) passt hinein.
MAX_ZEITRAUM_TAGE = 121


@router.get("/aufgaben/zeitraum", response_model=list[AufgabeAus])
def zeitraum(
    von: date = Query(..., description="erster Tag"),
    bis: date = Query(..., description="letzter Tag, eingeschlossen"),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[Aufgabe]:
    """Offene Aufgaben, die in diesem Zeitraum liegen, fuer den Kalender.

    Zwei Arten: mit geplanter Zeit (``start`` im Zeitraum) und mit Plantag
    ohne Zeit (``tag`` im Zeitraum). Eine Frist allein ist kein Plan und
    kommt nicht mit, sonst stuende jede Mahnung als Termin im Kalender.
    """
    if bis < von:
        raise _unzulaessig("bis liegt vor von")
    if (bis - von).days >= MAX_ZEITRAUM_TAGE:
        raise _unzulaessig(f"hoechstens {MAX_ZEITRAUM_TAGE} Tage")
    anfang = datetime.combine(von, datetime.min.time())
    schluss = datetime.combine(bis + timedelta(days=1), datetime.min.time())
    abfrage = select(Aufgabe).where(
        Aufgabe.owner_sub == me.sub,
        Aufgabe.erledigt.is_(False),
        ((Aufgabe.start >= anfang) & (Aufgabe.start < schluss))
        | (Aufgabe.start.is_(None) & (Aufgabe.tag >= von) & (Aufgabe.tag <= bis)),
    ).order_by(Aufgabe.start, Aufgabe.tag, Aufgabe.erstellt_am)
    return _mit_wartet(db, me, list(db.execute(abfrage).scalars()))


@router.get("/projekte/zaehlung")
def projekte_zaehlung(me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> dict[str, dict[str, int]]:
    """Stand je Projekt-Slug, fuer die Uebersicht im ProjectDeck.

    ``offen`` und ``erledigt`` zaehlen alle, ``hoch`` die offenen mit Prioritaet
    hoch (die Projektliste sortiert danach), ``ueberfaellig`` die offenen mit
    Frist vor heute, ``erledigt_7`` die in den letzten sieben Tagen erledigten.
    Die beiden letzten sagen, ob ein Projekt lebt oder liegt (ZIELBILD 108).
    """
    heute = _berlin_jetzt().date()
    seit = _berlin_jetzt() - timedelta(days=7)
    zeilen = db.execute(
        select(Aufgabe.projekt, Aufgabe.erledigt, Aufgabe.prioritaet, Aufgabe.faellig, Aufgabe.erledigt_am)
        .where(Aufgabe.owner_sub == me.sub, Aufgabe.projekt.is_not(None))
    ).all()
    ergebnis: dict[str, dict[str, int]] = {}
    for slug, erledigt, prioritaet, faellig, erledigt_am in zeilen:
        eintrag = ergebnis.setdefault(
            slug, {"offen": 0, "erledigt": 0, "hoch": 0, "ueberfaellig": 0, "erledigt_7": 0})
        if erledigt:
            eintrag["erledigt"] += 1
            if erledigt_am is not None and erledigt_am >= seit:
                eintrag["erledigt_7"] += 1
            continue
        eintrag["offen"] += 1
        if prioritaet == "hoch":
            eintrag["hoch"] += 1
        if faellig is not None and faellig < heute:
            eintrag["ueberfaellig"] += 1
    return ergebnis


@router.post("/projekte/{slug}/loesen")
def projekt_loesen(slug: str, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> dict[str, int]:
    """Das Projekt wird geloescht: seine Aufgaben stehen danach unter „Nicht zugeordnet".

    Aufgerufen vom ProjectDeck VOR dem Loeschen. Ein frei gewordener Slug
    wird wieder vergeben, und ohne diesen Schritt erbte ein neues Projekt
    gleichen Namens die Aufgaben des alten. Geloescht wird hier nichts.
    """
    ergebnis = db.execute(
        update(Aufgabe)
        .where(Aufgabe.owner_sub == me.sub, Aufgabe.projekt == slug)
        .values(projekt=None)
    )
    db.commit()
    return {"geloest": ergebnis.rowcount}


@router.post("/aufgaben", response_model=AufgabeAus, status_code=status.HTTP_201_CREATED)
def anlegen(
    daten: AufgabeNeu,
    hintergrund: BackgroundTasks,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Aufgabe:
    felder = daten.model_dump(exclude={"zeitfenster", "unteraufgaben"})
    if daten.zeitfenster is not None:
        felder["zeitfenster"] = [f.model_dump() for f in daten.zeitfenster]
    if daten.unteraufgaben is not None:
        felder["unteraufgaben"] = [u.model_dump() for u in daten.unteraufgaben]
    if felder["erledigt_am"] is not None:
        felder["erledigt"] = True
        felder["erledigt_am"] = berlin_naiv(felder["erledigt_am"])
    if daten.herkunft and db.execute(
        select(Aufgabe.id).where(Aufgabe.owner_sub == me.sub, Aufgabe.herkunft == daten.herkunft)
    ).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Aufgabe mit dieser Herkunft gibt es schon")
    aufgabe = Aufgabe(owner_sub=me.sub, **felder)
    aufgabe.id = aufgabe.id or neue_id()
    _bezug_pruefen(db, me, aufgabe)
    db.add(aufgabe)
    db.commit()
    db.refresh(aufgabe)
    if aufgabe.start is not None:
        belegung.vormerken(hintergrund, db, me)
    return _mit_wartet(db, me, [aufgabe])[0]


@router.get("/aufgaben/{aufgabe_id}", response_model=AufgabeAus)
def eine(aufgabe_id: str, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> Aufgabe:
    return _mit_wartet(db, me, [_hole(db, me, aufgabe_id)])[0]


@router.put("/aufgaben/{aufgabe_id}", response_model=AufgabeAus)
def aendern(
    aufgabe_id: str,
    daten: AufgabeAenderung,
    hintergrund: BackgroundTasks,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Aufgabe:
    """Nur, was geschickt wurde. ``null`` leert ein Feld, Weglassen laesst es stehen."""
    aufgabe = _hole(db, me, aufgabe_id)
    hatte_zeit = aufgabe.start is not None
    for feld in daten.model_fields_set:
        wert = getattr(daten, feld)
        if feld == "titel" and wert is None:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Titel darf nicht leer sein")
        if feld == "prioritaet" and wert is None:
            wert = "mittel"
        if feld in ("start", "ende"):
            wert = berlin_naiv(wert)
        if feld == "zeitfenster" and wert is not None:
            wert = [f.model_dump() for f in daten.zeitfenster]
        if feld == "unteraufgaben" and wert is not None:
            wert = [u.model_dump() for u in daten.unteraufgaben]
        setattr(aufgabe, feld, wert)
    # Wer nur das eine setzt, meint „dorthin verschieben": die Android-App
    # schickt beim Sammel-Setzen allein `projekt`. Ohne das antwortete eine
    # Aufgabe aus einer Liste mit 422, und der Offline-Puffer der App bliebe
    # daran haengen. Beide zugleich geschickt bleibt ein Fehler.
    gesetzt = daten.model_fields_set
    if aufgabe.projekt and "projekt" in gesetzt and "liste_id" not in gesetzt:
        aufgabe.liste_id = None
    if aufgabe.liste_id and "liste_id" in gesetzt and "projekt" not in gesetzt:
        aufgabe.projekt = None
    _bezug_pruefen(db, me, aufgabe)
    db.commit()
    db.refresh(aufgabe)
    if hatte_zeit or aufgabe.start is not None:
        belegung.vormerken(hintergrund, db, me)
    return _mit_wartet(db, me, [aufgabe])[0]


def _folge_herkunft(aufgabe: Aufgabe) -> str:
    return f"turnus:{aufgabe.id}"


def _folgeaufgabe(db: Session, me: Me, aufgabe: Aufgabe) -> None:
    """Turnus ab Erledigung: die naechste Runde, faellig ``turnus_tage`` nach heute.

    Mitgenommen wird, was die Sache beschreibt (Titel, Ort, Zuordnung, Dauer);
    nicht, was zur alten Runde gehoerte (Tag, Termin, geplante Zeit, Warten,
    Verschiebezaehler). Die Checkliste beginnt wieder unabgehakt. Die
    Herkunft ``turnus:<id>`` traegt den eindeutigen Index: ein zweites Abhaken
    nach „wieder offen" legt keine zweite Folgeaufgabe an, wenn die erste
    schon bearbeitet wurde und deshalb stehen blieb.
    """
    if not aufgabe.turnus_tage:
        return
    herkunft = _folge_herkunft(aufgabe)
    if db.execute(
        select(Aufgabe.id).where(Aufgabe.owner_sub == me.sub, Aufgabe.herkunft == herkunft)
    ).first() is not None:
        return
    unter = aufgabe.unteraufgaben
    db.add(Aufgabe(
        owner_sub=me.sub,
        titel=aufgabe.titel,
        notiz=aufgabe.notiz,
        prioritaet=aufgabe.prioritaet,
        faellig=aufgabe.erledigt_am.date() + timedelta(days=aufgabe.turnus_tage),
        dauer_min=aufgabe.dauer_min,
        energie=aufgabe.energie,
        projekt=aufgabe.projekt,
        liste_id=aufgabe.liste_id,
        wo=aufgabe.wo,
        ort_name=aufgabe.ort_name,
        zeitfenster=aufgabe.zeitfenster,
        unteraufgaben=[{**u, "erledigt": False} for u in unter] if unter else unter,
        tageszeit=aufgabe.tageszeit,
        turnus_tage=aufgabe.turnus_tage,
        herkunft=herkunft,
    ))


def _folgeaufgabe_zuruecknehmen(db: Session, me: Me, aufgabe: Aufgabe) -> None:
    """„Wieder offen" nimmt die Folgeaufgabe zurueck, solange niemand sie anfasste.

    Unberuehrt heisst: offen und seit dem Anlegen nicht geaendert. Eine
    bearbeitete Folgeaufgabe bleibt stehen, sonst ginge eine Eingabe verloren.
    """
    folge = db.execute(
        select(Aufgabe).where(Aufgabe.owner_sub == me.sub, Aufgabe.herkunft == _folge_herkunft(aufgabe))
    ).scalar_one_or_none()
    if folge is None or folge.erledigt:
        return
    angelegt, geaendert = folge.erstellt_am, folge.geaendert_am
    if angelegt is not None and geaendert is not None:
        if angelegt.tzinfo is None or geaendert.tzinfo is None:
            angelegt, geaendert = angelegt.replace(tzinfo=None), geaendert.replace(tzinfo=None)
        if abs((geaendert - angelegt).total_seconds()) > 2:
            return
    db.delete(folge)


@router.post("/aufgaben/{aufgabe_id}/erledigt", response_model=AufgabeAus)
def abhaken(
    aufgabe_id: str,
    hintergrund: BackgroundTasks,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Aufgabe:
    aufgabe = _hole(db, me, aufgabe_id)
    # Ein zweites Abhaken (Warteschlange nach Netzabriss) laesst den Zeitpunkt stehen.
    if not aufgabe.erledigt:
        aufgabe.erledigt = True
        aufgabe.erledigt_am = _berlin_jetzt()
        _folgeaufgabe(db, me, aufgabe)
        db.commit()
        db.refresh(aufgabe)
        if aufgabe.start is not None:
            belegung.vormerken(hintergrund, db, me)
    return _mit_wartet(db, me, [aufgabe])[0]


@router.post("/aufgaben/{aufgabe_id}/offen", response_model=AufgabeAus)
def aufmachen(
    aufgabe_id: str,
    hintergrund: BackgroundTasks,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Aufgabe:
    aufgabe = _hole(db, me, aufgabe_id)
    if aufgabe.erledigt:
        _folgeaufgabe_zuruecknehmen(db, me, aufgabe)
    aufgabe.erledigt = False
    aufgabe.erledigt_am = None
    db.commit()
    db.refresh(aufgabe)
    if aufgabe.start is not None:
        belegung.vormerken(hintergrund, db, me)
    return _mit_wartet(db, me, [aufgabe])[0]


@router.post("/aufgaben/{aufgabe_id}/verschieben", response_model=AufgabeAus)
def verschieben(
    aufgabe_id: str,
    daten: Verschieben,
    hintergrund: BackgroundTasks,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Aufgabe:
    """An einen anderen Tag oder zurueck in den Vorrat, und der Zaehler waechst.

    Die geplante Zeit faellt dabei weg: sie galt fuer den alten Tag. Die Frist
    bleibt, sie ist ein Versprechen nach aussen und kein Arbeitsplan.
    """
    aufgabe = _hole(db, me, aufgabe_id)
    hatte_zeit = aufgabe.start is not None
    aufgabe.tag = daten.tag
    aufgabe.start = None
    aufgabe.ende = None
    aufgabe.verschoben = (aufgabe.verschoben or 0) + 1
    db.commit()
    db.refresh(aufgabe)
    if hatte_zeit:
        belegung.vormerken(hintergrund, db, me)
    return _mit_wartet(db, me, [aufgabe])[0]


@router.delete("/aufgaben/{aufgabe_id}", status_code=status.HTTP_204_NO_CONTENT)
def loeschen(
    aufgabe_id: str,
    hintergrund: BackgroundTasks,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Response:
    aufgabe = _hole(db, me, aufgabe_id)
    hatte_zeit = aufgabe.start is not None
    db.delete(aufgabe)
    # Wer auf sie wartete, wartet auf nichts mehr; ohne das stuende eine
    # Kennung im Feld, die keine Oberflaeche aufloesen kann.
    db.execute(
        update(Aufgabe)
        .where(Aufgabe.owner_sub == me.sub, Aufgabe.wartet_auf_id == aufgabe_id)
        .values(wartet_auf_id=None)
    )
    db.commit()
    if hatte_zeit:
        belegung.vormerken(hintergrund, db, me)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Listen ---------------------------------------------------------------


def _startlisten(db: Session, me: Me) -> None:
    """Beim ersten Abruf je Konto die Startlisten, danach nie wieder."""
    if db.get(ListenAngelegt, me.sub) is not None:
        return
    for i, (name, vertraulich) in enumerate(STARTLISTEN):
        db.add(Liste(owner_sub=me.sub, name=name, position=i, vertraulich=vertraulich))
    db.add(ListenAngelegt(owner_sub=me.sub))
    db.commit()


def _hole_liste(db: Session, me: Me, liste_id: str) -> Liste:
    liste_ = db.execute(
        select(Liste).where(Liste.id == liste_id, Liste.owner_sub == me.sub)
    ).scalar_one_or_none()
    if liste_ is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liste nicht gefunden")
    return liste_


def _listen_aus(db: Session, me: Me, listen: list[Liste]) -> list[ListeAus]:
    offen = dict(db.execute(
        select(Aufgabe.liste_id, func.count())
        .where(Aufgabe.owner_sub == me.sub, Aufgabe.erledigt.is_(False), Aufgabe.liste_id.is_not(None))
        .group_by(Aufgabe.liste_id)
    ).all())
    return [
        ListeAus(id=l.id, name=l.name, position=l.position, vertraulich=bool(l.vertraulich),
                 offen=offen.get(l.id, 0))
        for l in listen
    ]


@router.get("/listen", response_model=list[ListeAus])
def listen(me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> list[ListeAus]:
    _startlisten(db, me)
    alle = list(db.execute(
        select(Liste).where(Liste.owner_sub == me.sub).order_by(Liste.position, Liste.erstellt_am)
    ).scalars())
    return _listen_aus(db, me, alle)


@router.post("/listen", response_model=ListeAus, status_code=status.HTTP_201_CREATED)
def liste_anlegen(daten: ListeNeu, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> ListeAus:
    _startlisten(db, me)
    hoechste = db.execute(
        select(func.max(Liste.position)).where(Liste.owner_sub == me.sub)
    ).scalar()
    neu = Liste(owner_sub=me.sub, name=daten.name, position=(hoechste or 0) + 1,
                vertraulich=daten.vertraulich)
    db.add(neu)
    db.commit()
    db.refresh(neu)
    return _listen_aus(db, me, [neu])[0]


@router.put("/listen/{liste_id}", response_model=ListeAus)
def liste_aendern(
    liste_id: str, daten: ListeAenderung, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)
) -> ListeAus:
    liste_ = _hole_liste(db, me, liste_id)
    if daten.name is not None:
        if not daten.name.strip():
            raise _unzulaessig("Name ist leer")
        liste_.name = daten.name.strip()
    if daten.position is not None:
        liste_.position = daten.position
    if daten.vertraulich is not None:
        liste_.vertraulich = daten.vertraulich
    db.commit()
    db.refresh(liste_)
    return _listen_aus(db, me, [liste_])[0]


@router.delete("/listen/{liste_id}", status_code=status.HTTP_204_NO_CONTENT)
def liste_aufloesen(liste_id: str, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> Response:
    """Die Liste geht, ihre Aufgaben bleiben und stehen unter „Nicht zugeordnet"."""
    db.delete(_hole_liste(db, me, liste_id))
    db.execute(
        update(Aufgabe)
        .where(Aufgabe.owner_sub == me.sub, Aufgabe.liste_id == liste_id)
        .values(liste_id=None)
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- Tag planen -----------------------------------------------------------


def _parse(wert: str) -> datetime:
    return berlin_naiv(datetime.fromisoformat(wert.replace("Z", "+00:00")))


def _minuten(uhrzeit: str) -> int:
    stunde, minute = uhrzeit.split(":")
    return int(stunde) * 60 + int(minute)


def _uhrzeit(minuten: int) -> str:
    return f"{minuten // 60:02d}:{minuten % 60:02d}"


def _fenster_am_tag(aufgabe: Aufgabe, tag: date) -> list[dict] | None:
    """Wann die Aufgabe an diesem Tag liegen darf; ``None`` heisst jederzeit.

    Zeitfenster des Wochentags, geschnitten mit der Tageszeit, wenn beides
    gesetzt ist. Eine leere Liste heisst: an diesem Tag gar nicht. Geht als
    ``fenster`` an den Planer des Kalenders, damit er im Fenster sucht, statt
    dass ``_passt_nicht`` seinen Vorschlag hinterher verwirft.
    """
    raeume: list[tuple[int, int]] | None = None
    if aufgabe.zeitfenster:
        raeume = [
            (_minuten(f["von"]), _minuten(f["bis"]))
            for f in aufgabe.zeitfenster
            if tag.weekday() in f["tage"]
        ]
    if aufgabe.tageszeit:
        tz_von, tz_bis = TAGESZEITEN[aufgabe.tageszeit]
        if raeume is None:
            raeume = [(tz_von, tz_bis)]
        else:
            raeume = [
                (max(v, tz_von), min(b, tz_bis)) for v, b in raeume if max(v, tz_von) < min(b, tz_bis)
            ]
    if raeume is None:
        return None
    return [{"von": _uhrzeit(v), "bis": _uhrzeit(b)} for v, b in raeume]


def _passt_nicht(aufgabe: Aufgabe, start: datetime, ende: datetime) -> str | None:
    """``zeitfenster`` oder ``tageszeit``, wenn der Vorschlag ausserhalb liegt."""
    von = start.hour * 60 + start.minute
    bis = von + int((ende - start).total_seconds() // 60)
    if aufgabe.zeitfenster:
        tag = start.weekday()
        if not any(
            tag in f["tage"] and _minuten(f["von"]) <= von and bis <= _minuten(f["bis"])
            for f in aufgabe.zeitfenster
        ):
            return "zeitfenster"
    if aufgabe.tageszeit:
        grenze_von, grenze_bis = TAGESZEITEN[aufgabe.tageszeit]
        if not (grenze_von <= von < grenze_bis):
            return "tageszeit"
    return None


@router.post("/planen", response_model=Plan)
def planen(
    daten: PlanAnfrage,
    hintergrund: BackgroundTasks,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Plan:
    """Erst rechnen, dann fragen: ``festlegen=false`` aendert nichts.

    Kandidaten sind offene Aufgaben ohne Zeit, die entweder im Vorrat liegen
    oder an genau diesen Tag geheftet sind; Projektaufgaben nur geheftet oder
    faellig. Was an diesem Tag schon eine Zeit
    hat, geht als belegt mit, denn der Kalender kennt es nicht als Termin.
    """
    offen = list(db.execute(
        select(Aufgabe).where(Aufgabe.owner_sub == me.sub, Aufgabe.erledigt.is_(False))
    ).scalars())
    wartend = _wartende(db, me, offen, daten.datum)
    kandidaten = []
    fenster: dict[str, list[dict] | None] = {}
    nicht_an_dem_tag: list[PlanZurueck] = []
    for a in offen:
        if a.start is not None or a.termin_id is not None:
            continue
        if a.tag is not None and a.tag > daten.datum:
            continue
        if a.id in wartend:
            continue
        # Unterwegs und an einem bestimmten Ort legt man selbst fest (05.11.).
        if a.wo in ("unterwegs", "ort"):
            continue
        # Projektaufgaben nur, wenn sie an diesen Tag geheftet oder faellig sind
        # (ZIELBILD 108). Sonst fuellt der Planer den Tag mit dem ganzen
        # Entwicklungsvorrat, und die eigenen Aufgaben gehen darin unter.
        if a.projekt and a.tag is None and (a.faellig is None or a.faellig > daten.datum):
            continue
        fenster[a.id] = _fenster_am_tag(a, daten.datum)
        if fenster[a.id] == []:
            grund = "zeitfenster" if a.zeitfenster else "tageszeit"
            nicht_an_dem_tag.append(PlanZurueck(aufgabe_id=a.id, titel=a.titel, grund=grund))
            continue
        kandidaten.append(a)
    belegt = [
        {"start": a.start.isoformat(), "end": a.ende.isoformat()}
        for a in offen
        if a.start and a.ende and a.start.date() == daten.datum
    ]
    anfrage = {
        "date": daten.datum.isoformat(),
        "aufgaben": [
            {
                "id": a.id,
                "title": a.titel,
                "priority": a.prioritaet,
                **({"estimated_minutes": a.dauer_min} if a.dauer_min else {}),
                **({"energy_required": _ENERGIE_ENGLISCH[a.energie]} if a.energie else {}),
                **({"due_date": a.faellig.isoformat()} if a.faellig else {}),
                **({"fenster": fenster[a.id]} if fenster[a.id] else {}),
            }
            for a in kandidaten
        ],
        "belegt": belegt,
    }
    try:
        antwort = kalender.aufruf(me, "POST", "/api/assistant/vorschlag", json=anfrage) or {}
    except kalender.KalenderNichtErreichbar as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Kalender nicht erreichbar") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Kalender lehnte ab: {exc.response.status_code}") from exc

    nach_id = {a.id: a for a in kandidaten}
    vorschlaege = []
    zurueck = list(nicht_an_dem_tag)
    for v in antwort.get("suggestions", []):
        aufgabe = nach_id.get(v.get("todo_id"))
        if aufgabe is None:
            continue
        vorschlag = PlanVorschlag(
            aufgabe_id=aufgabe.id,
            titel=v.get("title", ""),
            start=_parse(v["start"]),
            ende=_parse(v["end"]),
            minuten=int(v.get("minutes") or 0),
            grund=v.get("reason"),
        )
        # Der Planer sucht seit 2026-11-11 im mitgeschickten ``fenster``.
        # Die Pruefung bleibt als Riegel: ein Kalender ohne diese Faehigkeit
        # (aelteres Image) schlaegt sonst eine Zeit vor, zu der es nicht geht.
        abweichung = _passt_nicht(aufgabe, vorschlag.start, vorschlag.ende)
        if abweichung:
            zurueck.append(PlanZurueck(aufgabe_id=aufgabe.id, titel=aufgabe.titel, grund=abweichung))
        else:
            vorschlaege.append(vorschlag)
    zurueck += [
        PlanZurueck(aufgabe_id=d["todo_id"], titel=d.get("title", ""), grund=d.get("reason") or "")
        for d in antwort.get("deferred", [])
        if d.get("todo_id") in nach_id
    ]
    genannt = {v.aufgabe_id for v in vorschlaege} | {z.aufgabe_id for z in zurueck}
    ohne_fenster = [a.titel for a in kandidaten if a.id not in genannt]

    if daten.festlegen:
        for v in vorschlaege:
            aufgabe = nach_id[v.aufgabe_id]
            aufgabe.tag = daten.datum
            aufgabe.start = v.start
            aufgabe.ende = v.ende
        db.commit()
        if vorschlaege:
            belegung.vormerken(hintergrund, db, me)

    return Plan(
        datum=daten.datum,
        festgelegt=daten.festlegen,
        minuten=sum(v.minuten for v in vorschlaege),
        vorschlaege=vorschlaege,
        zurueck=zurueck,
        ohne_fenster=ohne_fenster,
    )


# --- Was der Kalender zum Tag beitraegt -----------------------------------


@router.get("/tag", response_model=TagAus)
def tag(datum: date = Query(...), me: Me = Depends(verify_jwt)) -> TagAus:
    """Kapazitaet, freie Zeit und Tagesziele aus dem Kalender.

    Fail-soft: ohne Kalender bleibt die Aufgabenliste voll benutzbar, hier
    steht dann nur ``kalender_erreichbar: false``. Die Aufgaben selbst haengen
    nicht an diesem Aufruf.
    """
    try:
        ziele_roh = kalender.aufruf(me, "GET", "/api/goals", params={"date": datum.isoformat()}) or []
        heute = datetime.now(BERLIN).date()
        bild = kalender.aufruf(me, "GET", "/api/assistant/today") if datum == heute else None
    except (kalender.KalenderNichtErreichbar, httpx.HTTPStatusError):
        return TagAus(datum=datum, kalender_erreichbar=False)
    kap = (bild or {}).get("capacity") or None
    return TagAus(
        datum=datum,
        kalender_erreichbar=True,
        kapazitaet=Kapazitaet(
            stufe=kap.get("level"), grund=kap.get("reason"), deckel_min=kap.get("cap_minutes")
        ) if kap else None,
        frei_min=(bild or {}).get("free_minutes"),
        ziele=[
            Ziel(id=z["id"], titel=z.get("title", ""), prioritaet=z.get("priority", "B"),
                 status=z.get("status", "planned"))
            for z in ziele_roh
            if isinstance(z, dict) and z.get("id")
        ],
    )


# --- Tagesziele: sie bleiben im Kalender, hier nur der Durchgang ----------


def _kalender_schreiben(me: Me, methode: str, pfad: str, **kw) -> dict | None:
    try:
        return kalender.aufruf(me, methode, pfad, **kw)
    except kalender.KalenderNichtErreichbar as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Kalender nicht erreichbar") from exc
    except httpx.HTTPStatusError as exc:
        # 404 bleibt 404: die Warteschlange der App wertet ein schon geloeschtes Ziel als erledigt.
        code = exc.response.status_code
        raise HTTPException(code if 400 <= code < 500 else 502, "Kalender lehnte ab") from exc


def _ziel(z: dict | None) -> Ziel:
    z = z or {}
    return Ziel(id=z.get("id", ""), titel=z.get("title", ""), prioritaet=z.get("priority", "B"),
                status=z.get("status", "planned"))


@router.post("/ziele", response_model=Ziel, status_code=status.HTTP_201_CREATED)
def ziel_anlegen(daten: ZielNeu, me: Me = Depends(verify_jwt)) -> Ziel:
    return _ziel(_kalender_schreiben(me, "POST", "/api/goals", json={
        "title": daten.titel, "date": daten.datum.isoformat(), "priority": daten.prioritaet,
    }))


@router.put("/ziele/{ziel_id}", response_model=Ziel)
def ziel_aendern(ziel_id: str, daten: ZielAenderung, me: Me = Depends(verify_jwt)) -> Ziel:
    namen = {"titel": "title", "prioritaet": "priority", "status": "status"}
    koerper = {namen[f]: getattr(daten, f) for f in daten.model_fields_set if getattr(daten, f) is not None}
    return _ziel(_kalender_schreiben(me, "PUT", f"/api/goals/{ziel_id}", json=koerper))


@router.delete("/ziele/{ziel_id}", status_code=status.HTTP_204_NO_CONTENT)
def ziel_loeschen(ziel_id: str, me: Me = Depends(verify_jwt)) -> Response:
    _kalender_schreiben(me, "DELETE", f"/api/goals/{ziel_id}")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
