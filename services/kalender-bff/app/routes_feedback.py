"""Aktivitäts-Feedback-Proxy zum nativen Kalender (kalender:8085).

Bringt die „Randnotiz nach der Aktivität" ins Saganta-Frontend: bewertbare Aktivitäten
des Tages (`reviewable`), einzelnes Feedback lesen, Feedback setzen. Der native Kalender
bleibt Engine/Datenquelle; dieser BFF ist Auth-Bridge + Validierung.
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


@router.get("/api/feedback/reviewable")
async def reviewable(
    me: Me = CurrentUser,
    date: str | None = Query(None, pattern=_DATE),
    lookback: int = Query(0, ge=0, le=14),
) -> dict:
    """Vorbei-gegangene Aktivitäten ohne Feedback (Haupt-Quelle fürs UI). `lookback` > 0
    nimmt die letzten N Tage mit → rückwirkendes Bewerten."""
    params: dict = {"lookback": lookback}
    if date:
        params["date"] = date
    r = await _upstream("GET", "/api/feedback/reviewable", params=params)
    return r.json() if r.content else {}


@router.get("/api/feedback/insights")
async def insights(me: Me = CurrentUser) -> dict:
    """Was Saganta über die Aktivitäts-Präferenzen gelernt hat."""
    r = await _upstream("GET", "/api/feedback/insights")
    return r.json() if r.content else {}


@router.get("/api/feedback/best-slot")
async def best_slot(
    me: Me = CurrentUser,
    activity_type: str = Query(..., pattern=r"^(lernen|sport|lesen|hobby|sonstige)$"),
    days: int = Query(7, ge=1, le=14),
    duration: int = Query(60, ge=15, le=240),
) -> dict:
    """Präferenz-bewusster Slot-Vorschlag: wann diese Aktivität am besten passt."""
    r = await _upstream(
        "GET", "/api/feedback/best-slot",
        params={"activity_type": activity_type, "days": days, "duration": duration},
    )
    return r.json() if r.content else {}


@router.get("/api/feedback")
async def get_feedback(
    me: Me = CurrentUser,
    event_id: str = Query(..., min_length=1),
    date: str | None = Query(None, pattern=_DATE),
) -> dict:
    """Einzelnes Feedback einer Aktivitäts-Instanz lesen (fürs EventModal)."""
    params: dict = {"event_id": event_id}
    if date:
        params["date"] = date
    r = await _upstream("GET", "/api/feedback", params=params)
    return r.json() if r.content else {}


class FeedbackIn(BaseModel):
    # event_id darf Basis-ID oder Instanz-ID ('{base}::{date}') sein.
    event_id: str = Field(..., min_length=1)
    occurrence_date: str | None = Field(default=None, pattern=_DATE)
    energy_after: Literal["energetisiert", "ok", "erschöpft"] | None = None
    satisfaction: Literal["gut", "mittel", "schlecht"] | None = None
    took_place: bool = True
    note: str | None = Field(default=None, max_length=2000)


@router.post("/api/feedback")
async def submit_feedback(data: FeedbackIn, me: Me = CurrentUser) -> dict:
    """Feedback für eine Aktivitäts-Instanz anlegen/aktualisieren."""
    r = await _upstream("POST", "/api/feedback", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}
