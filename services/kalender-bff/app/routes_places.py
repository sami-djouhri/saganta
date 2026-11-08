"""Orte-Proxy zum nativen Kalender (seit 2026-11-01).

Zuhause, Arbeit, Schule und Einkauf: aus ihnen rechnet der native Kalender
Arbeitsweg, Heimweg und die Wege zu Terminen. Bis hierher gab es Orte nur am
nativen ``/api/places`` und eine Oberflaeche nur im eigenstaendigen Frontend,
waehrend ``calendar.home.arpa`` seit dem 2026-10-25 diese Flaeche zeigt.
Gemessen am 2026-11-01: der Owner fand den Eintrag nicht.

Nach jeder Aenderung ruft die Oberflaeche ``/api/places/wege/planen``: erst das
legt die Wege der naechsten Tage neu an, auch die zu Terminen (Umzug).
"""
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import upstream

router = APIRouter()

_ART = r"^(zuhause|arbeit|schule|einkauf|sonstiges)$"


class PlaceIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    kind: str = Field(default="sonstiges", pattern=_ART)
    address: str | None = Field(default=None, max_length=300)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)


@router.get("/api/places")
async def list_places(me: Me = CurrentUser) -> list:
    r = await upstream("GET", "/api/places")
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/places", status_code=201)
async def create_place(data: PlaceIn, me: Me = CurrentUser) -> dict:
    r = await upstream("POST", "/api/places", json=data.model_dump())
    return r.json() if r.content else {}


@router.put("/api/places/{place_id}")
async def update_place(place_id: str, data: PlaceIn, me: Me = CurrentUser) -> dict:
    # Bewusst ohne exclude_none: eine geloeschte Adresse muss als null
    # ankommen, sonst behielte der Ort die alte Lage zur neuen Adresse.
    r = await upstream("PUT", f"/api/places/{place_id}", json=data.model_dump())
    return r.json() if r.content else {}


@router.delete("/api/places/{place_id}", status_code=204)
async def delete_place(place_id: str, me: Me = CurrentUser) -> None:
    await upstream("DELETE", f"/api/places/{place_id}")


@router.get("/api/places/adressen/suche")
async def search_address(q: str = Query(..., min_length=2, max_length=200),
                         me: Me = CurrentUser) -> dict:
    r = await upstream("GET", "/api/places/adressen/suche", params={"q": q})
    return r.json() if r.content else {"treffer": []}


@router.post("/api/places/wege/planen")
async def plan_routes(tage: int = Query(7, ge=1, le=31), me: Me = CurrentUser) -> dict:
    r = await upstream("POST", "/api/places/wege/planen", params={"tage": tage})
    return r.json() if r.content else {}
