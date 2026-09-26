"""Gewohnheiten-Proxy zum nativen Kalender (kalender:8085).

Gewohnheiten („Habits") sind wiederkehrende Vorhaben mit Wochenziel, aus denen der
native Scheduler selbständig Sitzungen in freie Zeitfenster legt. Sie fehlten im
BFF vollständig; die native App konnte sie verwalten, das Saganta-Frontend nicht.

★ **Die wichtigste Route hier ist ``/sessions/{id}/action``.** Sie ist kein CRUD,
sondern der Eingriff in den Scheduler: ``accepted`` bestätigt eine vorgeschlagene
Sitzung, ``dismissed`` verwirft sie: woraufhin der native Scheduler in derselben
Woche selbständig einen Ersatz-Slot sucht. Ohne diese Route kann ein Nutzer
Vorschläge weder annehmen noch ablehnen; die Sitzungen laufen dann stumm in den
Zustand ``dismissed``, sobald ihre Zeit verstreicht.

Das Anlegen/Ändern spiegelt ``HabitCreate``/``HabitUpdate`` des nativen Dienstes.
Die Defaults sind bewusst identisch: abweichende Vorgaben hier hiessen, dass eine
über Saganta angelegte Gewohnheit anders arbeitet als eine über die App angelegte.
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from typing import Literal

from .auth import CurrentUser, Me
from .upstream import upstream

router = APIRouter()

_HEXFARBE = r"^#[0-9a-fA-F]{6}$"
_UHRZEIT = r"^\d{2}:\d{2}$"
_KATEGORIE = r"^(lernen|lesen|sonstige)$"


class HabitIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    color: str = Field(default="#4a9eff", pattern=_HEXFARBE)
    project_id: str | None = None
    target_hours_per_week: float = Field(default=6.0, gt=0, le=80)
    session_duration_minutes: int = Field(default=90, ge=15, le=480)
    weekday_start: str = Field(default="17:00", pattern=_UHRZEIT)
    weekday_end: str = Field(default="20:00", pattern=_UHRZEIT)
    weekend_start: str = Field(default="10:00", pattern=_UHRZEIT)
    weekend_end: str = Field(default="18:00", pattern=_UHRZEIT)
    learning_mode: bool = False
    focus_block_minutes: int = Field(default=25, ge=5, le=120)
    break_minutes: int = Field(default=5, ge=1, le=30)
    category: str = Field(default="sonstige", pattern=_KATEGORIE)
    weekday_target_ratio: float = Field(default=0.3, ge=0.1, le=0.5)
    max_consecutive_days: int = Field(default=3, ge=1, le=7)
    max_session_minutes: int = Field(default=120, ge=15, le=480)


class HabitPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    color: str | None = Field(default=None, pattern=_HEXFARBE)
    project_id: str | None = None
    target_hours_per_week: float | None = Field(default=None, gt=0, le=80)
    session_duration_minutes: int | None = Field(default=None, ge=15, le=480)
    weekday_start: str | None = Field(default=None, pattern=_UHRZEIT)
    weekday_end: str | None = Field(default=None, pattern=_UHRZEIT)
    weekend_start: str | None = Field(default=None, pattern=_UHRZEIT)
    weekend_end: str | None = Field(default=None, pattern=_UHRZEIT)
    active: bool | None = None
    learning_mode: bool | None = None
    focus_block_minutes: int | None = Field(default=None, ge=5, le=120)
    break_minutes: int | None = Field(default=None, ge=1, le=30)
    category: str | None = Field(default=None, pattern=_KATEGORIE)
    weekday_target_ratio: float | None = Field(default=None, ge=0.1, le=0.5)
    max_consecutive_days: int | None = Field(default=None, ge=1, le=7)
    max_session_minutes: int | None = Field(default=None, ge=15, le=480)


class SessionAction(BaseModel):
    """Die vier Reaktionen auf einen Sitzungsvorschlag des Schedulers.

    ``Literal`` statt ``pattern``: eine unbekannte Aktion soll hier mit 422
    scheitern und nicht erst beim nativen Dienst, sonst steht im App-Log ein
    weitergereichter Upstream-Fehler, dessen Ursache im BFF liegt.
    """
    action: Literal["accepted", "dismissed", "cancelled", "start_early"]


@router.get("/api/habits")
async def list_habits(me: Me = CurrentUser) -> list:
    r = await upstream("GET", "/api/habits")
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/habits", status_code=201)
async def create_habit(data: HabitIn, me: Me = CurrentUser) -> dict:
    r = await upstream("POST", "/api/habits", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


@router.put("/api/habits/{habit_id}")
async def update_habit(habit_id: str, data: HabitPatch, me: Me = CurrentUser) -> dict:
    r = await upstream(
        "PUT", f"/api/habits/{habit_id}", json=data.model_dump(exclude_none=True)
    )
    return r.json() if r.content else {}


@router.delete("/api/habits/{habit_id}", status_code=204)
async def delete_habit(habit_id: str, me: Me = CurrentUser) -> None:
    await upstream("DELETE", f"/api/habits/{habit_id}")


# ── Sitzungen ────────────────────────────────────────────────────────────
# Der Scheduler legt selbständig Sitzungen in freie Fenster und schickt dazu
# ntfy-Nachrichten. Bis 2026-08-20 gab es dafür im BFF nichts: Saganta konnte
# weder anzeigen, was geplant ist, noch einen Vorschlag annehmen. Der Nutzer
# bekam also eine Push-Nachricht über einen Termin, den die Oberfläche nicht
# kannte: beantworten liess er sich nur in der nativen App.
@router.get("/api/habits/sessions/today")
async def sessions_today(me: Me = CurrentUser) -> list:
    r = await upstream("GET", "/api/habits/sessions/today")
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.get("/api/habits/sessions/upcoming")
async def sessions_upcoming(
    me: Me = CurrentUser,
    days: int = Query(7, ge=1, le=31),
) -> list:
    r = await upstream("GET", "/api/habits/sessions/upcoming", params={"days": days})
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.get("/api/habits/weekly-progress")
async def weekly_progress(me: Me = CurrentUser) -> list:
    """Soll/Ist je Gewohnheit für die laufende Woche."""
    r = await upstream("GET", "/api/habits/weekly-progress")
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/habits/sessions/{session_id}/action")
async def session_action(
    session_id: str, data: SessionAction, me: Me = CurrentUser
) -> dict:
    r = await upstream(
        "POST", f"/api/habits/sessions/{session_id}/action", json=data.model_dump()
    )
    return r.json() if r.content else {}
