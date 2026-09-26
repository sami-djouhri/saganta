"""Weekly Focus, Kalender-Planung, WorkLog und KI-Endpoints."""

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import ai, kalender_client
from .auth import CurrentUser, Me
from .db import get_db
from .enums import NO_AUTO_SCHEDULE_STATUSES
from .focus import set_focus
from .models import Project, ProjectTask, ProjectTimeBlock
from .schemas import (
    AISuggestOut,
    PlanResult,
    TimeBlockOut,
    WeeklyFocusIn,
    WeeklyFocusOut,
    WorkCandidateOut,
    WorkLogIn,
)

router = APIRouter()


def _owned(db: Session, me: Me, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p or p.owner != me.sub:
        raise HTTPException(404, "project not found")
    return p


# ---------- Weekly Focus ----------
@router.get("/focus", response_model=WeeklyFocusOut)
def get_focus(week: str | None = None, me: Me = CurrentUser, db: Session = Depends(get_db)) -> WeeklyFocusOut:
    from .focus import get_or_create

    return WeeklyFocusOut.model_validate(get_or_create(db, me.sub, week))


@router.put("/focus", response_model=WeeklyFocusOut)
def put_focus(payload: WeeklyFocusIn, me: Me = CurrentUser, db: Session = Depends(get_db)) -> WeeklyFocusOut:
    # nur eigene Projekte zulassen
    for pid in payload.project_ids + payload.maintenance_project_ids:
        _owned(db, me, pid)
    wf = set_focus(
        db, me.sub, payload.project_ids, payload.maintenance_project_ids, payload.week_iso
    )
    return WeeklyFocusOut.model_validate(wf)


# ---------- Work Candidates (Kalender-Schnittstelle) ----------
@router.get("/projects/{project_id}/work-candidates", response_model=list[WorkCandidateOut])
def work_candidates(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[WorkCandidateOut]:
    p = _owned(db, me, project_id)
    return kalender_client.build_work_candidates(p)


@router.post("/projects/{project_id}/plan", response_model=PlanResult)
async def plan_project(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> PlanResult:
    """Aktive Auto-Planung: push → auto-plan → readback. Frozen/Shutdown blockiert."""
    p = _owned(db, me, project_id)
    if p.status in NO_AUTO_SCHEDULE_STATUSES or not p.can_auto_schedule:
        raise HTTPException(
            409,
            f"Projekt '{p.slug}' ist nicht auto-planbar (status={p.status}, "
            f"can_auto_schedule={p.can_auto_schedule}).",
        )
    candidates = kalender_client.build_work_candidates(p)
    if not candidates:
        return PlanResult(
            project_id=p.id, pushed=0, scheduled_blocks=0, auto_plan_triggered=False,
            detail="Keine planbaren Tasks vorhanden.",
        )
    try:
        async with kalender_client.authed_client() as client:
            kal_id = await kalender_client.resolve_project_id(client, p)
            if not kal_id:
                raise HTTPException(502, "kalender: Projekt konnte nicht angelegt/aufgelöst werden.")
            mapping = await kalender_client.push_work_candidates(client, candidates, kal_id)
            planned = await kalender_client.trigger_auto_plan(client)
            blocks = await kalender_client.pull_scheduled_blocks(client, kal_id)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"kalender unreachable: {e}") from e

    # task -> scheduled_event_id eintragen
    for task_id, ev_id in mapping.items():
        t = db.get(ProjectTask, task_id)
        if t and t.project_id == p.id:
            t.scheduled_event_id = ev_id

    # ProjectTimeBlock aus Readback (idempotent über calendar_event_id).
    written = 0
    for b in blocks:
        ev_id = str(b.get("id") or b.get("todo_id") or "")
        existing = (
            db.query(ProjectTimeBlock)
            .filter(
                ProjectTimeBlock.project_id == p.id,
                ProjectTimeBlock.calendar_event_id == ev_id,
            )
            .one_or_none()
        )
        tb = existing or ProjectTimeBlock(project_id=p.id, calendar_event_id=ev_id)
        tb.planned_start = _parse_dt(b.get("scheduled_start"))
        tb.planned_end = _parse_dt(b.get("scheduled_end"))
        tb.status = "planned"
        if not existing:
            db.add(tb)
        written += 1
    db.commit()
    return PlanResult(
        project_id=p.id,
        pushed=len(candidates),
        scheduled_blocks=written,
        auto_plan_triggered=planned,
        detail=f"{len(candidates)} Kandidaten gepusht, {written} Blöcke zurückgelesen.",
    )


@router.get("/projects/{project_id}/time-blocks", response_model=list[TimeBlockOut])
def time_blocks(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectTimeBlock]:
    _owned(db, me, project_id)
    return db.query(ProjectTimeBlock).filter(ProjectTimeBlock.project_id == project_id).all()


@router.post("/projects/{project_id}/worklog", status_code=201)
def add_worklog(
    project_id: int, payload: WorkLogIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> dict:
    """Rückmeldung nach getaner Arbeit: actual_minutes verbuchen."""
    p = _owned(db, me, project_id)
    tb = None
    if payload.calendar_event_id:
        tb = (
            db.query(ProjectTimeBlock)
            .filter(
                ProjectTimeBlock.project_id == p.id,
                ProjectTimeBlock.calendar_event_id == payload.calendar_event_id,
            )
            .one_or_none()
        )
    if not tb:
        tb = ProjectTimeBlock(project_id=p.id, calendar_event_id=payload.calendar_event_id)
        db.add(tb)
    tb.actual_minutes = (tb.actual_minutes or 0) + payload.actual_minutes
    tb.status = "done" if payload.completed else "in_progress"

    if payload.task_id:
        t = db.get(ProjectTask, payload.task_id)
        if t and t.project_id == p.id:
            tb.task_id = t.id
            if t.remaining_minutes is not None:
                t.remaining_minutes = max(0, t.remaining_minutes - payload.actual_minutes)
            if payload.completed:
                t.status = "done"
                t.completed_at = datetime.now(timezone.utc)
                t.remaining_minutes = 0
    db.commit()
    return {"ok": True, "time_block_id": tb.id}


# ---------- AI ----------
@router.get("/projects/{project_id}/ai/shutdown", response_model=AISuggestOut)
async def ai_shutdown(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> AISuggestOut:
    return await ai.suggest_shutdown(_owned(db, me, project_id))


@router.get("/projects/{project_id}/ai/deadline-plan", response_model=AISuggestOut)
async def ai_deadline(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> AISuggestOut:
    return await ai.suggest_deadline_plan(_owned(db, me, project_id))


@router.get("/projects/{project_id}/ai/review", response_model=AISuggestOut)
async def ai_review(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> AISuggestOut:
    return await ai.review_summary(_owned(db, me, project_id))


def _parse_dt(value) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
