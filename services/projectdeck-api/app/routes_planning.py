"""Weekly Focus und KI-Endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from . import ai, aufgaben_dienst
from .auth import CurrentUser, Me
from .db import get_db
from .focus import set_focus
from .models import Project
from .schemas import AISuggestOut, WeeklyFocusIn, WeeklyFocusOut

router = APIRouter()


def _owned(db: Session, me: Me, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p or p.owner != me.sub:
        raise HTTPException(404, "project not found")
    return p


# ---------- Weekly Focus ----------
@router.get("/focus", response_model=WeeklyFocusOut)
def get_focus(week: str | None = None, me: Me = CurrentUser, db: Session = Depends(get_db)) -> WeeklyFocusOut:
    # `lesen` statt `get_or_create`: ein GET darf nichts anlegen. Siehe die
    # Begruendung in focus.py -- bis zum 2026-10-16 meldete ein Konto, das nur
    # geschaut hatte, eine Zeile in seiner eigenen Loeschvorschau.
    from .focus import lesen

    return WeeklyFocusOut.model_validate(lesen(db, me.sub, week))


@router.put("/focus", response_model=WeeklyFocusOut)
def put_focus(payload: WeeklyFocusIn, me: Me = CurrentUser, db: Session = Depends(get_db)) -> WeeklyFocusOut:
    # nur eigene Projekte zulassen
    for pid in payload.project_ids + payload.maintenance_project_ids:
        _owned(db, me, pid)
    wf = set_focus(
        db, me.sub, payload.project_ids, payload.maintenance_project_ids, payload.week_iso
    )
    return WeeklyFocusOut.model_validate(wf)


# Hier standen bis zum Umzug der Aufgaben (Nov. 2026) Work-Candidates,
# `POST /projects/{id}/plan`, `/worklog` und `/time-blocks`: der Kopierweg, der
# Aufgaben als Arbeitsbloecke in den Kalender schob (am 10.10. abgewaehlt,
# gemessen 0 Zeitbloecke). Eingeplant wird jetzt in Saganta Aufgaben („Tag
# planen") und ueber „Zeit einplanen" in der Projektansicht, das einen Termin
# im Kalender vorbefuellt. Die Tabelle `project_time_blocks` bleibt ungelesen
# stehen (Loeschplan in konto.py), wie `project_tasks`.


# ---------- AI ----------
@router.get("/projects/{project_id}/ai/shutdown", response_model=AISuggestOut)
async def ai_shutdown(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> AISuggestOut:
    p = _owned(db, me, project_id)
    aufgaben, unbekannt = await run_in_threadpool(aufgaben_dienst.quelle_projekt, me, p.slug)
    return await ai.suggest_shutdown(p, aufgaben, unbekannt)


@router.get("/projects/{project_id}/ai/deadline-plan", response_model=AISuggestOut)
async def ai_deadline(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> AISuggestOut:
    p = _owned(db, me, project_id)
    aufgaben, unbekannt = await run_in_threadpool(aufgaben_dienst.quelle_projekt, me, p.slug)
    return await ai.suggest_deadline_plan(p, aufgaben, unbekannt)


@router.get("/projects/{project_id}/ai/review", response_model=AISuggestOut)
async def ai_review(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> AISuggestOut:
    p = _owned(db, me, project_id)
    aufgaben, unbekannt = await run_in_threadpool(aufgaben_dienst.quelle_projekt, me, p.slug)
    return await ai.review_summary(p, aufgaben, unbekannt)
