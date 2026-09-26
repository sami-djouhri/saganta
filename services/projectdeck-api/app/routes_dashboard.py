from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from .auth import CurrentUser, Me
from .db import get_db
from .deadline_risk import compute_risk
from .enums import (
    LIVE_STATUSES,
    ProjectStatus,
    ProjectType,
    Visibility,
)
from .models import Project, WeeklyFocus
from .rules import evaluate_all
from .schemas import DeadlineRiskOut, Finding, ProjectOut
from .util import today, week_iso

router = APIRouter()


def _projects(db: Session, me: Me) -> list[Project]:
    return db.query(Project).filter(Project.owner == me.sub).all()


@router.get("/dashboard")
def dashboard(me: Me = CurrentUser, db: Session = Depends(get_db)) -> dict:
    projects = _projects(db, me)
    by_id = {p.id: p for p in projects}

    wf = (
        db.query(WeeklyFocus)
        .filter(WeeklyFocus.owner == me.sub, WeeklyFocus.week_iso == week_iso())
        .one_or_none()
    )
    focus_ids = set(wf.project_ids) if wf else set()

    findings = evaluate_all(projects)
    bucket_ids: dict[str, set[int]] = {}
    for f in findings:
        bucket_ids.setdefault(f.bucket, set()).add(f.project_id)

    def tile(items: list[Project]) -> list[dict]:
        return [ProjectOut.model_validate(p).model_dump(mode="json") for p in items]

    def by_bucket(bucket: str) -> list[Project]:
        return [by_id[i] for i in bucket_ids.get(bucket, set()) if i in by_id]

    tiles = {
        "active_this_week": tile([by_id[i] for i in focus_ids if i in by_id]),
        "client_projects": tile([p for p in projects if p.type == ProjectType.CLIENT]),
        "public_projects": tile([p for p in projects if p.visibility == Visibility.PUBLIC]),
        "private_projects": tile([p for p in projects if p.visibility == Visibility.PRIVATE]),
        "public_candidates": tile(
            [
                p
                for p in projects
                if p.target_visibility in {Visibility.PUBLIC_PREVIEW, Visibility.PUBLIC}
                and p.visibility != Visibility.PUBLIC
            ]
        ),
        "deadline_risks": tile(by_bucket("deadline_risks")),
        "blocked": tile(by_bucket("blocked")),
        "maintenance_needed": tile(
            [p for p in projects if p.status == ProjectStatus.MAINTENANCE]
        ),
        "frozen": tile([p for p in projects if p.status == ProjectStatus.FROZEN]),
        "shutdown_check": tile(by_bucket("shutdown")),
        "without_next_action": tile(by_bucket("without_next_action")),
        "without_review": tile(by_bucket("without_review")),
    }
    counts = {k: len(v) for k, v in tiles.items()}
    return {
        "week_iso": week_iso(),
        "total_projects": len(projects),
        "live_projects": sum(1 for p in projects if p.status in LIVE_STATUSES),
        "counts": counts,
        "tiles": tiles,
        "findings": [f.model_dump() for f in findings],
    }


@router.get("/findings", response_model=list[Finding])
def findings(me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[Finding]:
    return evaluate_all(_projects(db, me))


@router.get("/deadline-center", response_model=list[DeadlineRiskOut])
def deadline_center(me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[DeadlineRiskOut]:
    """Projekte mit Deadline, sortiert nach Dringlichkeit; Client+Hard zuerst."""
    risks: list[tuple[int, DeadlineRiskOut, Project]] = []
    order = {
        "overdue": 0,
        "impossible": 1,
        "critical": 2,
        "tight": 3,
        "watch": 4,
        "relaxed": 5,
    }
    for p in _projects(db, me):
        if not p.deadline_date:
            continue
        risk = compute_risk(p)
        # Kundenprojekte mit harter Deadline werden hochpriorisiert.
        priority_boost = 0 if (p.type == ProjectType.CLIENT and p.deadline_type == "hard") else 1
        risks.append((order.get(risk.risk_level, 9) + priority_boost * 10, risk, p))
    risks.sort(key=lambda x: (x[0], x[2].deadline_date or today()))
    return [r for _, r, _ in risks]
