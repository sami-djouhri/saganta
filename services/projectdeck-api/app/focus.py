"""Weekly Focus Planner: max. 3 Hauptprojekte pro Woche.

Bewusster Schutz gegen Überplanung. Maintenance-Projekte dürfen zusätzlich kleine
Wartungsblöcke bekommen (separate Liste, nicht auf das 3er-Limit angerechnet).
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import WeeklyFocus
from .util import week_iso

MAX_FOCUS_PROJECTS = 3


def _suche(db: Session, owner: str, wk: str) -> WeeklyFocus | None:
    return (
        db.query(WeeklyFocus)
        .filter(WeeklyFocus.owner == owner, WeeklyFocus.week_iso == wk)
        .one_or_none()
    )


def lesen(db: Session, owner: str, week: str | None = None) -> WeeklyFocus:
    """Der Fokus dieser Woche, **ohne** ihn anzulegen.

    Hier rief ``GET /api/focus`` bis zum 2026-10-16 ``get_or_create``, und
    damit schrieb ein reiner Lesezugriff. Gemessen: ein Konto, das nur die Seite
    geoeffnet hatte, meldete danach ``summe: 1`` in seiner eigenen
    Loeschvorschau. Das ist kein Schoenheitsfehler, sondern eine falsche Antwort
    auf die Frage "was ist ueber mich gespeichert" -- und die Frage ist der Grund,
    aus dem es den Loeschweg gibt.

    Zurueck kommt ein **nicht gespeichertes** Objekt, wenn es die Zeile nicht
    gibt. Es ist absichtlich nicht in der Session: ein ``db.add`` ohne
    ``commit`` wuerde beim naechsten Flush derselben Session doch geschrieben,
    und zwar an einer Stelle, an der niemand damit rechnet. ``id`` ist dann
    ``None``, weshalb ``WeeklyFocusOut.id`` optional ist.
    """
    wk = week or week_iso()
    gefunden = _suche(db, owner, wk)
    if gefunden:
        return gefunden
    return WeeklyFocus(owner=owner, week_iso=wk, project_ids=[], maintenance_project_ids=[])


def get_or_create(db: Session, owner: str, week: str | None = None) -> WeeklyFocus:
    """Anlegen ist erlaubt, aber nur auf einem schreibenden Weg (``PUT``)."""
    wk = week or week_iso()
    wf = _suche(db, owner, wk)
    if not wf:
        wf = WeeklyFocus(owner=owner, week_iso=wk, project_ids=[], maintenance_project_ids=[])
        db.add(wf)
        db.commit()
        db.refresh(wf)
    return wf


def set_focus(
    db: Session,
    owner: str,
    project_ids: list[int],
    maintenance_project_ids: list[int],
    week: str | None = None,
) -> WeeklyFocus:
    if len(set(project_ids)) > MAX_FOCUS_PROJECTS:
        raise HTTPException(
            422,
            f"Maximal {MAX_FOCUS_PROJECTS} Hauptfokus-Projekte pro Woche "
            "(bewusster Schutz gegen Überplanung).",
        )
    wf = get_or_create(db, owner, week)
    wf.project_ids = list(dict.fromkeys(project_ids))
    wf.maintenance_project_ids = list(dict.fromkeys(maintenance_project_ids))
    db.commit()
    db.refresh(wf)
    return wf
