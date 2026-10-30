"""Adaptiver-Sekretär-Proxy zum nativen Kalender (kalender:8085).

Bringt die adaptive Schicht des nativen Kalenders ins Saganta-Frontend:
Morgen-Check-in, Tageskapazität, gerankte Vorschläge („Was jetzt?"),
Wochenfortschritt und das angereicherte Tagesbild (`/today`). Der native
Kalender bleibt Engine/Datenquelle; dieser BFF ist Auth-Bridge + Validierung.
"""
from fastapi import APIRouter, HTTPException, Query
import httpx
from pydantic import BaseModel, Field
from typing import Literal

from .auth import CurrentUser, Me
from .upstream import authed_kalender_client

router = APIRouter()

_DATE = r"^\d{4}-\d{2}-\d{2}$"


async def _upstream(method: str, path: str, *, params: dict | None = None, json: dict | None = None) -> httpx.Response:
    async with authed_kalender_client() as client:
        try:
            r = await client.request(method, path, params=params, json=json)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    return r


@router.get("/api/assistant/today")
async def today(me: Me = CurrentUser, date: str | None = Query(None, pattern=_DATE)) -> dict:
    """Angereichertes Tagesbild: Briefing + Kapazität + Check-in + Top-Vorschläge."""
    params = {"date": date} if date else None
    r = await _upstream("GET", "/api/assistant/today", params=params)
    return r.json() if r.content else {}


@router.get("/api/assistant/capacity")
async def capacity(me: Me = CurrentUser, date: str | None = Query(None, pattern=_DATE)) -> dict:
    params = {"date": date} if date else None
    r = await _upstream("GET", "/api/assistant/capacity", params=params)
    return r.json() if r.content else {}


@router.get("/api/assistant/suggestions")
async def suggestions(me: Me = CurrentUser, date: str | None = Query(None, pattern=_DATE)) -> dict:
    """Gerankte Vorschläge + optionale Entscheidungsfrage."""
    params = {"date": date} if date else None
    r = await _upstream("GET", "/api/assistant/suggestions", params=params)
    return r.json() if r.content else {}


@router.get("/api/assistant/progress")
async def progress(me: Me = CurrentUser, week_start: str | None = Query(None, pattern=_DATE)) -> dict:
    params = {"week_start": week_start} if week_start else None
    r = await _upstream("GET", "/api/assistant/progress", params=params)
    return r.json() if r.content else {}


@router.get("/api/assistant/checkin")
async def read_checkin(me: Me = CurrentUser, date: str | None = Query(None, pattern=_DATE)) -> dict:
    params = {"date": date} if date else None
    r = await _upstream("GET", "/api/assistant/checkin", params=params)
    return r.json() if r.content else {}


class CheckInIn(BaseModel):
    date: str | None = Field(default=None, pattern=_DATE)
    sleep_quality: Literal["gut", "mittel", "schlecht"] | None = None
    energy: Literal["hoch", "mittel", "niedrig"] | None = None
    mood: Literal["gut", "neutral", "mies"] | None = None
    physical_ready: bool | None = None
    note: str | None = Field(default=None, max_length=1000)


@router.post("/api/assistant/checkin")
async def submit_checkin(data: CheckInIn, me: Me = CurrentUser) -> dict:
    """Morgen-Check-in setzen → Planung + Vorschläge passen sich sofort an."""
    r = await _upstream("POST", "/api/assistant/checkin", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


class PlanDayIn(BaseModel):
    date: str = Field(..., pattern=_DATE)
    commit: bool = False


@router.post("/api/assistant/plan-day")
async def plan_day(data: PlanDayIn, me: Me = CurrentUser) -> dict:
    """„Plane meinen Tag": präferenz-bewusste Pool-Todo-Planung in freie Slots.

    `commit=false` = Vorschau (Slots + Begründung je Aufgabe, plant nichts), `commit=true` =
    verbindlich einplanen. Nutzt den nativen `/api/schedule`-Planer mit `prefer_time` (gelernte
    Tageszeit-Passung). Read-only-Vorschau ist gefahrlos; Commit ist reversibel (Pool-Todos).
    """
    if data.commit:
        r = await _upstream(
            "POST", "/api/schedule/auto-plan",
            params={"date": data.date, "commit": "true", "prefer_time": "true"},
        )
    else:
        r = await _upstream(
            "GET", "/api/schedule/day",
            params={"date": data.date, "prefer_time": "true"},
        )
    return r.json() if r.content else {}
