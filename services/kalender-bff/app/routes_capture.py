"""Quick-Capture-Proxy: reicht Freitext-Erfassung an das native Kalender-Backend
durch. Ermöglicht den Cross-App-Intent „→ Kalender" (Post-Fristen, News-Items etc.):
andere Saganta-Apps schicken Text/Datum per URL an den Kalender, der Nutzer bestätigt
den erkannten Vorschlag, der Termin/die Aufgabe wird angelegt.

Zwei-Schritt (parsen → bestätigen) wie im nativen Backend: nichts wird ohne
Bestätigung verbindlich angelegt.
"""
from fastapi import APIRouter, HTTPException
import httpx
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import authed_kalender_client

router = APIRouter()


class CaptureParseIn(BaseModel):
    text: str = Field(..., min_length=1, max_length=1000)
    allow_llm: bool = True


class CaptureCommitIn(BaseModel):
    type: str = Field(..., pattern=r"^(event|todo)$")
    title: str = Field(..., min_length=1, max_length=500)
    date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")


@router.post("/api/capture")
async def parse(data: CaptureParseIn, me: Me = CurrentUser) -> dict:
    """Freitext parsen → Vorschlag (legt nichts an)."""
    async with authed_kalender_client() as client:
        try:
            r = await client.post("/api/capture", json=data.model_dump())
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    return r.json() if r.content else {}


@router.post("/api/capture/commit", status_code=201)
async def commit(data: CaptureCommitIn, me: Me = CurrentUser) -> dict:
    """Vorschlag verbindlich als Termin/Aufgabe anlegen."""
    async with authed_kalender_client() as client:
        try:
            r = await client.post(
                "/api/capture/commit", json=data.model_dump(exclude_none=True)
            )
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    return r.json() if r.content else {}
