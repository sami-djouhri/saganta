"""Aktive Zwei-Wege-Integration mit dem nativen Kalender (host:8085).

Auth-Flow wie services/kalender-bff/app/upstream.py: Feed-Token gegen
session_token-Cookie tauschen, Cookie-Jar trägt die Folge-Requests.

An die echte native API angepasst (verifiziert 2026-06-28):
- Kalender-Project.id ist eine server-vergebene uuid → wir lösen per Name auf
  (anlegen, falls fehlt) und nutzen diese uuid als Todo-project_id.
- Todo.scheduling_mode ∈ {pool, planned_day, fixed_slot}; wir legen Pool-Todos an.
- Auto-Plan ist pro Tag: POST /api/schedule/auto-plan?date=…&commit=true.
ProjectDeck bleibt Source-of-Truth: Einweg-Push + Readback, keine Rückschreibung.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

import httpx
import structlog

from .config import settings
from .enums import ProjectStatus, TaskStatus
from .tenant_sig import tenant_headers
from .models import Project
from .auth import current_owner_sub
from .schemas import WorkCandidateOut
from .util import today

log = structlog.get_logger()


@asynccontextmanager
async def authed_client() -> AsyncIterator[httpx.AsyncClient]:
    sub = current_owner_sub.get()
    headers = tenant_headers(sub) or None
    async with httpx.AsyncClient(
        base_url=settings.kalender_base_url,
        timeout=settings.kalender_timeout_seconds,
        headers=headers,
    ) as client:
        r = await client.get(
            "/api/auth/token-login", params={"token": settings.kalender_feed_token}
        )
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"kalender token-login fehlgeschlagen: {r.status_code}",
                request=r.request,
                response=r,
            )
        yield client


def build_work_candidates(project: Project) -> list[WorkCandidateOut]:
    """Planbare Arbeitspakete aus den Tasks eines Projekts ableiten."""
    out: list[WorkCandidateOut] = []
    for t in project.tasks:
        if t.status == TaskStatus.DONE or not t.can_schedule:
            continue
        mins = t.remaining_minutes if t.remaining_minutes is not None else t.estimated_minutes
        if not mins:
            continue
        out.append(
            WorkCandidateOut(
                project_id=project.id,
                task_id=t.id,
                slug=project.slug,
                title=f"[{project.slug}] {t.title}",
                estimated_minutes=mins,
                deadline=t.deadline or project.deadline_date,
                priority=t.priority,
                scheduling_mode=project.scheduling_mode,
                latest_finish=t.deadline or project.deadline_date,
                min_block_minutes=t.min_block_minutes,
                max_block_minutes=t.max_block_minutes,
                energy_required=project.energy_level_required,
                focus_required=project.focus_level_required,
                can_split=t.can_split,
                can_move=True,
            )
        )
    return out


def _map_kalender_status(status: str) -> str:
    # Kalender erlaubt nur active|paused|completed.
    if status == ProjectStatus.ACTIVE:
        return "active"
    if status in {ProjectStatus.ARCHIVED, ProjectStatus.SHUTDOWN}:
        return "completed"
    return "paused"


async def resolve_project_id(client: httpx.AsyncClient, project: Project) -> str | None:
    """Kalender-Project per Name auflösen (idempotent), sonst anlegen → uuid."""
    try:
        r = await client.get("/api/projects")
        if r.status_code < 400 and r.content:
            for kp in r.json():
                if kp.get("name") == project.name:
                    return kp.get("id")
        c = await client.post(
            "/api/projects",
            json={"name": project.name, "status": _map_kalender_status(project.status)},
        )
        if c.status_code < 400 and c.content:
            return c.json().get("id")
        log.warning("kalender.resolve_project.create_failed", slug=project.slug, code=c.status_code)
    except httpx.HTTPError as e:
        log.warning("kalender.resolve_project.failed", slug=project.slug, error=str(e))
    return None


async def push_work_candidates(
    client: httpx.AsyncClient,
    candidates: list[WorkCandidateOut],
    kal_project_id: str,
) -> dict[int, str]:
    """Erzeugt Pool-Todos. Liefert task_id -> kalender-todo-id."""
    mapping: dict[int, str] = {}
    for c in candidates:
        body: dict = {
            "title": c.title,
            "project_id": kal_project_id,
            "priority": _map_priority(c.priority),
            "estimated_minutes": min(max(c.estimated_minutes, 1), 1440),
            "scheduling_mode": "pool",
        }
        if c.deadline:
            body["due_date"] = c.deadline.isoformat()
        try:
            r = await client.post("/api/todos", json=body)
            if r.status_code < 400 and r.content:
                tid = str(r.json().get("id") or "")
                if c.task_id and tid:
                    mapping[c.task_id] = tid
            else:
                log.warning("kalender.push_todo.rejected", title=c.title, code=r.status_code)
        except httpx.HTTPError as e:
            log.warning("kalender.push_todo.failed", title=c.title, error=str(e))
    return mapping


async def trigger_auto_plan(client: httpx.AsyncClient, days: int = 7) -> bool:
    """Pool-Todos in freie Slots der nächsten `days` Tage verbindlich einplanen."""
    ok = False
    base = today()
    for offset in range(days):
        d = base + timedelta(days=offset)
        try:
            r = await client.post(
                "/api/schedule/auto-plan",
                params={"date": d.isoformat(), "commit": "true"},
            )
            ok = ok or r.status_code < 400
        except httpx.HTTPError as e:
            log.warning("kalender.auto_plan.failed", date=d.isoformat(), error=str(e))
    return ok


async def pull_scheduled_blocks(client: httpx.AsyncClient, kal_project_id: str) -> list[dict]:
    """Liest geplante (mit Zeitblock belegte) Todos des Projekts zurück."""
    try:
        r = await client.get(
            "/api/todos",
            params={"project_id": kal_project_id, "include_completed": "false"},
        )
        if r.status_code < 400 and r.content:
            items = r.json()
            return [it for it in items if it.get("scheduled_start")]
    except httpx.HTTPError as e:
        log.warning("kalender.pull_blocks.failed", project_id=kal_project_id, error=str(e))
    return []


def _map_priority(p: int) -> str:
    # ProjectDeck 1..5 -> kalender-Enum (niedrig|mittel|hoch|dringend)
    return {1: "dringend", 2: "hoch", 3: "mittel", 4: "niedrig", 5: "niedrig"}.get(p, "mittel")
