"""Zeit von Hand: Timer und Haken, durchgereicht an den nativen Kalender.

Gegenstueck zu `kalender/backend/routers/zeit.py` (2026-11-01). Ohne diese Routen
erreicht die Android-App den Timer nicht: sie spricht ausschliesslich diesen BFF.

Die Modelle spiegeln die des Dienstes, damit ein Tippfehler hier mit 422 endet
und nicht erst als 422 von dort, verpackt in einen 422-Text.
"""
from datetime import date

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import upstream

router = APIRouter()

_BEZUG = r"^(session|event|todo)$"


class TimerStart(BaseModel):
    titel: str = Field(..., min_length=1, max_length=300)
    art: str | None = None
    bezug_typ: str | None = Field(default=None, pattern=_BEZUG)
    bezug_id: str | None = Field(default=None, max_length=200)
    seit: str | None = None


class TimerStopp(BaseModel):
    ende: str | None = None


class Haken(BaseModel):
    titel: str = Field(..., min_length=1, max_length=300)
    start: str
    ende: str
    art: str | None = None
    bezug_typ: str | None = Field(default=None, pattern=_BEZUG)
    bezug_id: str | None = Field(default=None, max_length=200)


@router.get("/api/zeit/timer")
async def timer(me: Me = CurrentUser) -> dict:
    return (await upstream("GET", "/api/zeit/timer")).json()


@router.post("/api/zeit/timer/start")
async def timer_start(data: TimerStart, me: Me = CurrentUser) -> dict:
    r = await upstream("POST", "/api/zeit/timer/start", json=data.model_dump(exclude_none=True))
    return r.json()


@router.post("/api/zeit/timer/stopp")
async def timer_stopp(data: TimerStopp | None = None, me: Me = CurrentUser) -> dict:
    nutzlast = data.model_dump(exclude_none=True) if data else {}
    return (await upstream("POST", "/api/zeit/timer/stopp", json=nutzlast)).json()


@router.post("/api/zeit/haken", status_code=201)
async def haken(data: Haken, me: Me = CurrentUser) -> dict:
    r = await upstream("POST", "/api/zeit/haken", json=data.model_dump(exclude_none=True))
    return r.json()


@router.get("/api/zeit/belege")
async def belege(
    von: date = Query(...),
    bis: date = Query(...),
    me: Me = CurrentUser,
) -> dict:
    r = await upstream("GET", "/api/zeit/belege", params={"von": str(von), "bis": str(bis)})
    return r.json()
