"""Geplante Zeit an den Kalender melden (Entscheid 2026-11-13).

Der Gewohnheits-Planer des Kalenders muss wissen, wann eine Aufgabe eingeplant
ist, sonst legt er Lernen oder Sport darauf. Dieser Dienst meldet deshalb nach
jeder Aenderung, die eine geplante Zeit beruehrt, die **ganze** Liste der
kuenftigen Aufgaben mit Uhrzeit an den kalender-bff
(`PUT /api/planung/belegungen/aufgaben`).

Ganze Liste statt Einzelmeldung: eine verlorene Meldung heilt die naechste.
Im Hintergrund und fail-soft: das Speichern einer Aufgabe haengt nicht am
Kalender, und der plant betroffene Wochen neu (Sekunden bei 0,25 CPU).
"""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import kalender
from .auth import Me
from .models import Aufgabe
from .schemas import BERLIN

log = structlog.get_logger()
PFAD = "/api/planung/belegungen/aufgaben"


def _ende(a: Aufgabe) -> datetime | None:
    if a.ende is not None:
        return a.ende
    if a.dauer_min:
        return a.start + timedelta(minutes=a.dauer_min)
    return None


def liste(db: Session, me: Me) -> list[dict]:
    """Offene Aufgaben mit Uhrzeit, die noch nicht vorbei sind (Berliner Wanduhr)."""
    jetzt = datetime.now(BERLIN).replace(tzinfo=None)
    zeilen = db.execute(
        select(Aufgabe).where(
            Aufgabe.owner_sub == me.sub,
            Aufgabe.erledigt.is_(False),
            Aufgabe.start.is_not(None),
        )
    ).scalars()
    eintraege = []
    for a in zeilen:
        ende = _ende(a)
        if ende is None or ende <= a.start or ende <= jetzt:
            continue
        eintraege.append({
            "id": a.id,
            "titel": (a.titel or "")[:300],
            "start": a.start.isoformat(),
            "ende": ende.isoformat(),
        })
    return eintraege


def _senden(me: Me, eintraege: list[dict]) -> None:
    try:
        antwort = kalender.aufruf(me, "PUT", PFAD, json={"eintraege": eintraege})
        log.info("belegung.gemeldet", anzahl=len(eintraege),
                 neu_geplant=(antwort or {}).get("wochen_neu_geplant"))
    except Exception as exc:  # noqa: BLE001 - fail-soft, die naechste Meldung heilt
        log.warning("belegung.nicht_gemeldet", fehler=repr(exc)[:200], anzahl=len(eintraege))


def vormerken(hintergrund: BackgroundTasks, db: Session, me: Me) -> None:
    """Liste jetzt lesen (die Sitzung endet mit der Anfrage), senden danach."""
    hintergrund.add_task(_senden, me, liste(db, me))
