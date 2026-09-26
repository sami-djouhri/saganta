"""Weekly Focus Planner: max. 3 Hauptprojekte pro Woche.

Bewusster Schutz gegen Überplanung. Maintenance-Projekte dürfen zusätzlich kleine
Wartungsblöcke bekommen (separate Liste, nicht auf das 3er-Limit angerechnet).
"""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import WeeklyFocus
from .util import week_iso

MAX_FOCUS_PROJECTS = 3


def get_or_create(db: Session, owner: str, week: str | None = None) -> WeeklyFocus:
    wk = week or week_iso()
    wf = (
        db.query(WeeklyFocus)
        .filter(WeeklyFocus.owner == owner, WeeklyFocus.week_iso == wk)
        .one_or_none()
    )
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
