"""Routen von Saganta Kontakte. Jede Abfrage filtert auf den ``sub`` des Tokens."""
from __future__ import annotations

from datetime import date, datetime, timedelta

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import abgleich, kalender
from .auth import Me, verify_jwt
from .config import settings
from .db import get_db
from .models import Kontakt, jetzt
from .schemas import (
    Anstehend,
    KontaktAenderung,
    KontaktAus,
    KontaktListe,
    KontaktNeu,
    UmzugErgebnis,
)
from .tage import naechster, tage_von

log = structlog.get_logger()
router = APIRouter()

#: Felder, deren Aenderung den Kalender betrifft. Nur dann wird abgeglichen.
_KALENDER_FELDER = {"name", "geburtstag", "jahrestage"}


def _json_felder(daten: dict) -> dict:
    """Pydantic-Objekte in JSON-Listen fuer die JSON-Spalten."""
    for feld in ("jahrestage", "termine"):
        if feld in daten and daten[feld] is not None:
            daten[feld] = [
                {k: (v.isoformat() if isinstance(v, date) else v) for k, v in eintrag.items()}
                for eintrag in daten[feld]
            ]
    return daten


def _eigener(db: Session, me: Me, kontakt_id: str, *, geloescht: bool = False) -> Kontakt:
    k = db.get(Kontakt, kontakt_id)
    if k is None or k.owner_sub != me.sub or (k.geloescht_am is not None) != geloescht:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kontakt nicht gefunden")
    return k


def _papierkorb_leeren(db: Session, me: Me) -> None:
    grenze = jetzt() - timedelta(days=settings.papierkorb_tage)
    db.execute(delete(Kontakt).where(
        Kontakt.owner_sub == me.sub, Kontakt.geloescht_am.is_not(None),
        Kontakt.geloescht_am < grenze,
    ))
    db.commit()


@router.get("/kontakte", response_model=KontaktListe)
def liste(
    suche: str | None = Query(default=None, max_length=100),
    gruppe: str | None = Query(default=None, max_length=60),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> KontaktListe:
    q = select(Kontakt).where(Kontakt.owner_sub == me.sub, Kontakt.geloescht_am.is_(None))
    if gruppe:
        q = q.where(Kontakt.gruppe == gruppe)
    if suche and suche.strip():
        muster = f"%{suche.strip().lower()}%"
        q = q.where(or_(
            func.lower(Kontakt.name).like(muster),
            func.lower(func.coalesce(Kontakt.email, "")).like(muster),
            func.coalesce(Kontakt.telefon, "").like(muster),
            func.lower(func.coalesce(Kontakt.adresse, "")).like(muster),
            func.lower(func.coalesce(Kontakt.gruppe, "")).like(muster),
        ))
    kontakte = db.scalars(q.order_by(func.lower(Kontakt.name))).all()
    return KontaktListe(
        kontakte=[KontaktAus.model_validate(k) for k in kontakte],
        kalender_aktuell=not abgleich.offen(db, me.sub),
    )


@router.post("/kontakte", response_model=KontaktAus, status_code=status.HTTP_201_CREATED)
def anlegen(daten: KontaktNeu, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> Kontakt:
    k = Kontakt(owner_sub=me.sub, **_json_felder(daten.model_dump()))
    db.add(k)
    db.commit()
    db.refresh(k)
    if k.geburtstag or k.jahrestage:
        abgleich.abgleichen(db, me)
    return k


@router.get("/kontakte/{kontakt_id}", response_model=KontaktAus)
def lesen(kontakt_id: str, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> Kontakt:
    return _eigener(db, me, kontakt_id)


@router.patch("/kontakte/{kontakt_id}", response_model=KontaktAus)
def aendern(
    kontakt_id: str,
    daten: KontaktAenderung,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> Kontakt:
    k = _eigener(db, me, kontakt_id)
    gesetzt = _json_felder(daten.model_dump(exclude_unset=True))
    if "name" in gesetzt and not gesetzt["name"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Name darf nicht leer sein")
    for feld, wert in gesetzt.items():
        setattr(k, feld, wert)
    db.commit()
    db.refresh(k)
    if _KALENDER_FELDER & gesetzt.keys():
        abgleich.abgleichen(db, me)
    return k


@router.delete("/kontakte/{kontakt_id}", status_code=status.HTTP_204_NO_CONTENT)
def loeschen(kontakt_id: str, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> Response:
    """Legt den Kontakt in den Papierkorb (30 Tage), wie in allen Saganta-Apps."""
    k = _eigener(db, me, kontakt_id)
    k.geloescht_am = jetzt()
    db.commit()
    if k.geburtstag or k.jahrestage:
        abgleich.abgleichen(db, me)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/papierkorb", response_model=list[KontaktAus])
def papierkorb(me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> list[Kontakt]:
    _papierkorb_leeren(db, me)
    return list(db.scalars(
        select(Kontakt)
        .where(Kontakt.owner_sub == me.sub, Kontakt.geloescht_am.is_not(None))
        .order_by(Kontakt.geloescht_am.desc())
    ).all())


@router.post("/papierkorb/{kontakt_id}/wiederherstellen", response_model=KontaktAus)
def wiederherstellen(
    kontakt_id: str, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)
) -> Kontakt:
    k = _eigener(db, me, kontakt_id, geloescht=True)
    k.geloescht_am = None
    db.commit()
    db.refresh(k)
    if k.geburtstag or k.jahrestage:
        abgleich.abgleichen(db, me)
    return k


@router.delete("/papierkorb/{kontakt_id}", status_code=status.HTTP_204_NO_CONTENT)
def endgueltig(kontakt_id: str, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> Response:
    k = _eigener(db, me, kontakt_id, geloescht=True)
    db.delete(k)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/gruppen", response_model=list[str])
def gruppen(me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> list[str]:
    return sorted(
        {g for (g,) in db.execute(
            select(Kontakt.gruppe).where(
                Kontakt.owner_sub == me.sub, Kontakt.geloescht_am.is_(None),
                Kontakt.gruppe.is_not(None),
            )
        )},
        key=str.lower,
    )


@router.get("/anstehend", response_model=list[Anstehend])
def anstehend(
    tage: int = Query(default=30, ge=1, le=366),
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[Anstehend]:
    """Geburtstage und Jahrestage der naechsten ``tage`` Tage, heute zuerst."""
    heute = datetime.now().date()
    ergebnis: list[Anstehend] = []
    for k in db.scalars(
        select(Kontakt).where(Kontakt.owner_sub == me.sub, Kontakt.geloescht_am.is_(None))
    ):
        for art, bezeichnung, tag in tage_von(k):
            datum = naechster(tag, heute)
            abstand = (datum - heute).days
            if abstand >= tage or datum.year < tag.year:
                continue
            ergebnis.append(Anstehend(
                kontakt_id=k.id, name=k.name, art=art, bezeichnung=bezeichnung,
                datum=datum, in_tagen=abstand, zahl=datum.year - tag.year,
            ))
    ergebnis.sort(key=lambda a: (a.in_tagen, a.name.lower()))
    return ergebnis


@router.post("/abgleich")
def abgleich_jetzt(me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> dict:
    """Schickt den Stand von Hand an den Kalender (Knopf bei einem Rueckstand)."""
    ok = abgleich.abgleichen(db, me)
    if not ok:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Kalender nicht erreichbar, wird nachgeholt")
    return {"ok": True}


@router.post("/umzug/kalender", response_model=UmzugErgebnis)
def umzug_aus_dem_kalender(me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> UmzugErgebnis:
    """Uebernimmt die Kontakte, die noch im Kalender liegen. Idempotent.

    Die Kennung bleibt dieselbe wie im Kalender: Verknuepfungen aus den
    Notizen (Typ ``kontakt``) zeigen auf diese Kennung und bleiben gueltig.
    Bereits uebernommene Kontakte (``herkunft = kalender:<id>``) werden nicht
    erneut angelegt, auch wenn sie hier inzwischen geaendert wurden.
    """
    try:
        alte = kalender.aufruf(me, "GET", "/api/contacts") or []
    except (kalender.KalenderNichtErreichbar, httpx.HTTPStatusError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Kalender nicht erreichbar: {exc}") from exc

    vorhanden = {h for (h,) in db.execute(
        select(Kontakt.herkunft).where(Kontakt.owner_sub == me.sub, Kontakt.herkunft.is_not(None))
    )}
    uebernommen = schon_da = 0
    for alt in alte:
        if alt.get("art") == "jahrestag":
            # Spiegelzeile eines frueheren Abgleichs, kein eigener Kontakt.
            continue
        herkunft = f"kalender:{alt['id']}"
        if herkunft in vorhanden or db.get(Kontakt, alt["id"]) is not None:
            schon_da += 1
            continue
        geburtstag = date.fromisoformat(alt["birthday"]) if alt.get("birthday") else None
        db.add(Kontakt(
            id=alt["id"], owner_sub=me.sub, name=alt["name"],
            telefon=alt.get("phone") or None, email=alt.get("email") or None,
            adresse=alt.get("address") or None, notiz=alt.get("notes") or None,
            geburtstag=geburtstag, herkunft=herkunft,
        ))
        uebernommen += 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Umzug lief gleichzeitig, bitte wiederholen") from exc
    if uebernommen:
        abgleich.abgleichen(db, me)
    log.info("kontakte.umzug", gefunden=len(alte), uebernommen=uebernommen, schon_da=schon_da)
    return UmzugErgebnis(gefunden=len(alte), uebernommen=uebernommen, schon_da=schon_da)
