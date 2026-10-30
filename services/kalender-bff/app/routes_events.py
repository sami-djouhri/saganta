from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Path, Query
import httpx
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import authed_kalender_client


router = APIRouter()


# Naive ISO-Zeiten (ohne Offset), der native Kalender behandelt sie als Berlin;
# so bleibt es konsistent zu den bereits gespeicherten Events. Keine UTC-Umrechnung.
class EventIn(BaseModel):
    calendar_id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=500)
    start: str = Field(..., min_length=10, max_length=32)
    end: str = Field(..., min_length=10, max_length=32)
    all_day: bool = False
    reminder_minutes: int | None = Field(default=None, ge=0, le=10080)


class EventPatch(BaseModel):
    calendar_id: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=500)
    start: str | None = Field(default=None, min_length=10, max_length=32)
    end: str | None = Field(default=None, min_length=10, max_length=32)
    all_day: bool | None = None
    reminder_minutes: int | None = Field(default=None, ge=0, le=10080)


def _start_epoch(ev: dict) -> float:
    """Chronologischer Sort-Key. Lexikografischer String-Vergleich ordnet
    gemischte Offset-Darstellungen falsch (…Z vs …+02:00) und damit auch die
    [:limit]-Truncation. fromisoformat deckt Datum-only (all-day), Offsets und (via
    Z→+00:00) UTC ab; naive Werte gelten als UTC. Unparsebares ans Ende.
    """
    raw = str(ev.get("start_at") or ev.get("start") or "")
    if not raw:
        return float("inf")
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return float("inf")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


@router.get("/upcoming")
async def upcoming(
    me: Me = CurrentUser,
    days: int = Query(14, ge=1, le=90),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, object]:
    """Aggregierte Sicht: nächste N Tage, sortiert nach Startzeit."""
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    async with authed_kalender_client() as client:
        try:
            r = await client.get(
                "/api/events",
                params={
                    # Der native list_events erwartet start/end (NICHT from/to). Nur
                    # mit gesetztem Fenster expandiert er wiederkehrende Termine und
                    # filtert den Zeitraum; ohne würde er ALLE Basis-Events roh
                    # liefern (inkl. Vergangenheit, Serien nur einmal).
                    "start": now.date().isoformat(),
                    "end": until.date().isoformat() + "T23:59:59",
                },
            )
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    items = r.json() if r.content else []
    if isinstance(items, list):
        items.sort(key=_start_epoch)
        items = items[:limit]
    return {"user": me.sub, "from": now.isoformat(), "to": until.isoformat(), "items": items}


@router.get("/range")
async def range_events(
    me: Me = CurrentUser,
    start: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    end: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
    limit: int = Query(1000, ge=1, le=2000),
) -> dict[str, object]:
    """Events in einem beliebigen Datumsbereich (für Wochen-/Monatsansicht).
    Gleiche native Fenster-Semantik wie upcoming (start/end → Recurrence-Expand)."""
    async with authed_kalender_client() as client:
        try:
            r = await client.get(
                "/api/events", params={"start": start, "end": end + "T23:59:59"}
            )
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    items = r.json() if r.content else []
    if isinstance(items, list):
        items.sort(key=_start_epoch)
        items = items[:limit]
    return {"start": start, "end": end, "items": items}


@router.get("/calendars")
async def calendars(me: Me = CurrentUser) -> list[dict]:
    async with authed_kalender_client() as client:
        try:
            r = await client.get("/api/calendars")
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    return r.json() if r.content else []


async def _events_upstream(
    method: str, path: str, *, json: dict | None = None
) -> httpx.Response:
    async with authed_kalender_client() as client:
        try:
            r = await client.request(method, path, json=json)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    return r


@router.post("", status_code=201)
async def create_event(data: EventIn, me: Me = CurrentUser) -> dict:
    r = await _events_upstream("POST", "/api/events", json=data.model_dump(exclude_none=True))
    return r.json() if r.content else {}


@router.put("/{event_id}")
async def update_event(event_id: str, data: EventPatch, me: Me = CurrentUser) -> dict:
    # Basis-Event bearbeiten (Reihen-ID); Instanz-IDs ('base::date') löst der native
    # Kalender selbst auf. exclude_none = echtes Partial-Update.
    r = await _events_upstream(
        "PUT", f"/api/events/{event_id}", json=data.model_dump(exclude_none=True)
    )
    return r.json() if r.content else {}


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: str, me: Me = CurrentUser) -> None:
    await _events_upstream("DELETE", f"/api/events/{event_id}")


# ── Serien: einzelnes Vorkommen und Abbruch ab Datum ──────────────────────
# Ohne diese zwei Routen kannte jeder Client nur „ganze Reihe löschen". Für
# einen einzelnen abgesagten Termin blieb dann nur, die komplette Serie zu
# entfernen und neu anzulegen, oder den Termin stehen zu lassen und ihn zu
# ignorieren. Beides falsch. Die Engine kann es seit jeher (EXDATE bzw. UNTIL),
# nur reichte der BFF es nicht durch.
_DATUM = r"^\d{4}-\d{2}-\d{2}$"


@router.delete("/{event_id}/instances/{occ_date}", status_code=204)
async def delete_instance(
    event_id: str,
    occ_date: str = Path(..., pattern=_DATUM),
    me: Me = CurrentUser,
) -> None:
    """„Nur dieser Termin", ein Vorkommen per EXDATE aus der Reihe nehmen.

    ``event_id`` darf die Reihen-ID **oder** eine Instanz-ID (``basis::datum``)
    sein; der native Dienst löst beides auf. Das Datum steht trotzdem separat im
    Pfad, weil die Instanz-ID nur eine Bequemlichkeit ist: welcher Tag entfällt,
    soll ausdrücklich dastehen und nicht aus einem zusammengesetzten Bezeichner
    gelesen werden müssen.
    """
    await _events_upstream("DELETE", f"/api/events/{event_id}/instances/{occ_date}")


@router.post("/{event_id}/truncate", status_code=204)
async def truncate_series(
    event_id: str,
    occ_date: str = Query(..., pattern=_DATUM),
    me: Me = CurrentUser,
) -> None:
    """„Diese und alle folgenden": Reihe per UNTIL vor diesem Tag beenden.

    ⚠️ Wirkt in die Zukunft und ist über die API nicht zurücknehmbar: das
    ursprüngliche Ende der Regel ist danach verloren. Clients sollten es
    entsprechend deutlich abfragen.
    """
    await _events_upstream(
        "POST", f"/api/events/{event_id}/truncate?occ_date={occ_date}"
    )
