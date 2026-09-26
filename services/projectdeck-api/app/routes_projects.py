from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from .auth import CurrentUser, Me
from .db import get_db
from .enums import PUBLIC_READINESS_ITEMS, SHUTDOWN_CHECKLIST_ITEMS, TaskStatus
from .models import (
    Project,
    ProjectAsset,
    ProjectMilestone,
    ProjectReview,
    ProjectTask,
    PublicReadiness,
    ShutdownChecklist,
)
from .schemas import (
    AssetIn,
    AssetOut,
    MilestoneIn,
    MilestoneOut,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
    ReadinessOut,
    ReadinessPatch,
    ReviewIn,
    ReviewOut,
    ShutdownOut,
    ShutdownPatch,
    TaskIn,
    TaskOut,
    TaskPatch,
)
from .util import slugify, today

router = APIRouter()


def _owned_project(db: Session, me: Me, project_id: int) -> Project:
    p = db.get(Project, project_id)
    if not p or p.owner != me.sub:
        raise HTTPException(404, "project not found")
    return p


def _unique_slug(db: Session, base: str) -> str:
    slug = base
    i = 2
    while db.query(Project).filter(Project.slug == slug).first():
        slug = f"{base}-{i}"
        i += 1
    return slug


# ---------- Projects ----------
@router.get("", response_model=list[ProjectOut])
def list_projects(
    me: Me = CurrentUser,
    type: str | None = Query(None),
    status: str | None = Query(None),
    client_id: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    q = db.query(Project).filter(Project.owner == me.sub)
    if type:
        q = q.filter(Project.type == type)
    if status:
        q = q.filter(Project.status == status)
    if client_id:
        q = q.filter(Project.client_id == client_id)
    projekte = q.order_by(Project.priority.asc(), Project.updated_at.desc()).all()

    # Offene Aufgaben in EINER Abfrage nachschlagen. Ueber `p.tasks` je Projekt
    # zu gehen waere bequemer und ergaebe eine Nachfrage je Kachel.
    offen: dict[int, int] = {}
    if projekte:
        offen = dict(
            db.query(ProjectTask.project_id, func.count(ProjectTask.id))
            .filter(
                ProjectTask.project_id.in_([p.id for p in projekte]),
                ProjectTask.status != TaskStatus.DONE,
            )
            .group_by(ProjectTask.project_id)
            .all()
        )
    return [
        ProjectOut.model_validate(p).model_copy(update={"open_tasks": offen.get(p.id, 0)})
        for p in projekte
    ]


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(
    payload: ProjectIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> Project:
    data = payload.model_dump()
    base_slug = slugify(data.pop("slug") or data["name"])
    p = Project(owner=me.sub, slug=_unique_slug(db, base_slug), **data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/by-slug/{slug}", response_model=ProjectOut)
def get_by_slug(slug: str, me: Me = CurrentUser, db: Session = Depends(get_db)) -> Project:
    p = db.query(Project).filter(Project.owner == me.sub, Project.slug == slug).one_or_none()
    if not p:
        raise HTTPException(404, "project not found")
    return p


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> Project:
    return _owned_project(db, me, project_id)


@router.patch("/{project_id}", response_model=ProjectOut)
def patch_project(
    project_id: int, payload: ProjectPatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> Project:
    p = _owned_project(db, me, project_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit()
    db.refresh(p)
    return p


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> None:
    p = _owned_project(db, me, project_id)
    db.delete(p)
    db.commit()


@router.post("/{project_id}/archive", response_model=ProjectOut)
def archive_project(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> Project:
    p = _owned_project(db, me, project_id)
    p.status = "archived"
    db.commit()
    db.refresh(p)
    return p


# ---------- Tasks ----------
@router.get("/{project_id}/tasks", response_model=list[TaskOut])
def list_tasks(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectTask]:
    _owned_project(db, me, project_id)
    return (
        db.query(ProjectTask)
        .filter(ProjectTask.project_id == project_id)
        .order_by(ProjectTask.priority.asc(), ProjectTask.created_at.asc())
        .all()
    )


@router.post("/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(
    project_id: int, payload: TaskIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProjectTask:
    _owned_project(db, me, project_id)
    t = ProjectTask(project_id=project_id, **payload.model_dump())
    if t.remaining_minutes is None:
        t.remaining_minutes = t.estimated_minutes
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.patch("/{project_id}/tasks/{task_id}", response_model=TaskOut)
def patch_task(
    project_id: int,
    task_id: int,
    payload: TaskPatch,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> ProjectTask:
    _owned_project(db, me, project_id)
    t = db.get(ProjectTask, task_id)
    if not t or t.project_id != project_id:
        raise HTTPException(404, "task not found")
    fields = payload.model_dump(exclude_unset=True)
    for k, v in fields.items():
        setattr(t, k, v)
    if fields.get("status") == "done" and not t.completed_at:
        t.completed_at = datetime.now(timezone.utc)
        t.remaining_minutes = 0
    db.commit()
    db.refresh(t)
    return t


@router.delete("/{project_id}/tasks/{task_id}", status_code=204)
def delete_task(
    project_id: int, task_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> None:
    _owned_project(db, me, project_id)
    t = db.get(ProjectTask, task_id)
    if not t or t.project_id != project_id:
        raise HTTPException(404, "task not found")
    db.delete(t)
    db.commit()


# ---------- Assets ----------
@router.get("/{project_id}/assets", response_model=list[AssetOut])
def list_assets(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectAsset]:
    _owned_project(db, me, project_id)
    return db.query(ProjectAsset).filter(ProjectAsset.project_id == project_id).all()


@router.post("/{project_id}/assets", response_model=AssetOut, status_code=201)
def create_asset(
    project_id: int, payload: AssetIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProjectAsset:
    _owned_project(db, me, project_id)
    a = ProjectAsset(project_id=project_id, **payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


@router.delete("/{project_id}/assets/{asset_id}", status_code=204)
def delete_asset(
    project_id: int, asset_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> None:
    _owned_project(db, me, project_id)
    a = db.get(ProjectAsset, asset_id)
    if not a or a.project_id != project_id:
        raise HTTPException(404, "asset not found")
    db.delete(a)
    db.commit()


# ---------- Milestones ----------
@router.get("/{project_id}/milestones", response_model=list[MilestoneOut])
def list_milestones(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectMilestone]:
    _owned_project(db, me, project_id)
    return (
        db.query(ProjectMilestone)
        .filter(ProjectMilestone.project_id == project_id)
        .order_by(ProjectMilestone.target_date.asc().nullslast())
        .all()
    )


@router.post("/{project_id}/milestones", response_model=MilestoneOut, status_code=201)
def create_milestone(
    project_id: int, payload: MilestoneIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProjectMilestone:
    _owned_project(db, me, project_id)
    m = ProjectMilestone(project_id=project_id, **payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{project_id}/milestones/{milestone_id}", status_code=204)
def delete_milestone(
    project_id: int, milestone_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> None:
    _owned_project(db, me, project_id)
    m = db.get(ProjectMilestone, milestone_id)
    if not m or m.project_id != project_id:
        raise HTTPException(404, "milestone not found")
    db.delete(m)
    db.commit()


# ---------- Reviews ----------
@router.get("/{project_id}/reviews", response_model=list[ReviewOut])
def list_reviews(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[ProjectReview]:
    _owned_project(db, me, project_id)
    return (
        db.query(ProjectReview)
        .filter(ProjectReview.project_id == project_id)
        .order_by(ProjectReview.review_date.desc())
        .all()
    )


@router.post("/{project_id}/reviews", response_model=ReviewOut, status_code=201)
def create_review(
    project_id: int, payload: ReviewIn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ProjectReview:
    p = _owned_project(db, me, project_id)
    data = payload.model_dump()
    data["review_date"] = data.get("review_date") or today()
    r = ProjectReview(project_id=project_id, **data)
    db.add(r)
    # Entscheidung auf das Projekt anwenden.
    if r.new_status:
        p.status = r.new_status
    if r.new_priority:
        p.priority = r.new_priority
    if r.new_weekly_budget_minutes is not None:
        p.weekly_time_budget_minutes = r.new_weekly_budget_minutes
    if r.next_action:
        p.next_action = r.next_action
    p.last_reviewed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(r)
    return r


# ---------- Public Readiness ----------
def _readiness_out(pr: PublicReadiness | None, project_id: int) -> ReadinessOut:
    items = dict(pr.items) if pr and pr.items else {}
    # alle bekannten Items sicherstellen
    for key in PUBLIC_READINESS_ITEMS:
        items.setdefault(key, {"done": False, "note": None})
    completed = sum(1 for v in items.values() if v.get("done"))
    return ReadinessOut(
        project_id=project_id, items=items, completed=completed, total=len(PUBLIC_READINESS_ITEMS)
    )


@router.get("/{project_id}/readiness", response_model=ReadinessOut)
def get_readiness(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> ReadinessOut:
    _owned_project(db, me, project_id)
    pr = db.query(PublicReadiness).filter(PublicReadiness.project_id == project_id).one_or_none()
    return _readiness_out(pr, project_id)


@router.put("/{project_id}/readiness", response_model=ReadinessOut)
def put_readiness(
    project_id: int, payload: ReadinessPatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ReadinessOut:
    _owned_project(db, me, project_id)
    pr = db.query(PublicReadiness).filter(PublicReadiness.project_id == project_id).one_or_none()
    if not pr:
        pr = PublicReadiness(project_id=project_id, items={})
        db.add(pr)
    merged = dict(pr.items or {})
    for key, item in payload.items.items():
        merged[key] = item.model_dump()
    pr.items = merged
    db.commit()
    db.refresh(pr)
    return _readiness_out(pr, project_id)


# ---------- Shutdown-Checkliste ----------
def _shutdown_out(sc: ShutdownChecklist | None, project_id: int) -> ShutdownOut:
    items = dict(sc.items) if sc and sc.items else {}
    for key in SHUTDOWN_CHECKLIST_ITEMS:
        items.setdefault(key, {"done": False, "note": None})
    completed = sum(1 for v in items.values() if v.get("done"))
    return ShutdownOut(
        project_id=project_id, items=items, completed=completed, total=len(SHUTDOWN_CHECKLIST_ITEMS)
    )


@router.get("/{project_id}/shutdown", response_model=ShutdownOut)
def get_shutdown(project_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> ShutdownOut:
    _owned_project(db, me, project_id)
    sc = db.query(ShutdownChecklist).filter(ShutdownChecklist.project_id == project_id).one_or_none()
    return _shutdown_out(sc, project_id)


@router.put("/{project_id}/shutdown", response_model=ShutdownOut)
def put_shutdown(
    project_id: int, payload: ShutdownPatch, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> ShutdownOut:
    _owned_project(db, me, project_id)
    sc = db.query(ShutdownChecklist).filter(ShutdownChecklist.project_id == project_id).one_or_none()
    if not sc:
        sc = ShutdownChecklist(project_id=project_id, items={})
        db.add(sc)
    merged = dict(sc.items or {})
    for key, item in payload.items.items():
        merged[key] = item.model_dump()
    sc.items = merged
    db.commit()
    db.refresh(sc)
    return _shutdown_out(sc, project_id)
