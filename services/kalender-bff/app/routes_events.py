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
    #: iCal-RRULE. Fehlte hier bis zum 2026-11-03, und Pydantic verwirft
    #: unbekannte Felder still: die Wiederholung, die man in der Android-App
    #: waehlt, kam nie beim Kalender an. Der Termin entstand als Einzeltermin,
    #: mit Erfolgsmeldung.
    recurrence_rule: str | None = Field(default=None, max_length=500)


class EventPatch(BaseModel):
    calendar_id: str | None = Field(default=None, min_length=1)
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=500)
    start: str | None = Field(default=None, min_length=10, max_length=32)
    end: str | None = Field(default=None, min_length=10, max_length=32)
    all_day: bool | None = None
    reminder_minutes: int | None = Field(default=None, ge=0, le=10080)
    #: Leerer Text heisst „keine Wiederholung mehr". Ein ``null`` taugt dafuer
    #: nicht: ``exclude_none`` unten macht daraus „unveraendert", und Gson in
    #: der App laesst Nullwerte ohnehin weg.
    recurrence_rule: str | None = Field(default=None, max_length=500)
    #: Nur mit diesem Schalter wird ``recurrence_rule`` beim Aendern
    #: uebernommen. Die Android-App bis 0.8.4 schickt bei JEDEM Speichern eine
    #: Vorlage mit („FREQ=WEEKLY"), auch wenn die Serie eine eigene Regel hat
    #: (``BYDAY=MO,WE;UNTIL=…``). Solange dieses Schema das Feld nicht kannte,
    #: fiel das still weg; ohne den Schalter loeschte jetzt jedes Speichern
    #: Wochentage und Enddatum der Serie.
    wiederholung_aendern: bool = False


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
    rumpf = data.model_dump(exclude_none=True)
    if not rumpf.get("recurrence_rule"):
        rumpf.pop("recurrence_rule", None)
    r = await _events_upstream("POST", "/api/events", json=rumpf)
    return r.json() if r.content else {}


def _zeitpunkt(text: str) -> datetime:
    try:
        return datetime.fromisoformat(text)
    except ValueError as e:
        raise HTTPException(422, f"Keine gueltige Zeitangabe: {text}") from e


def _auf_anker_umrechnen(
    basis: dict, vorkommen: str, rumpf: dict
) -> dict:
    """Rechnet Start/Ende eines Vorkommens auf den Anker der Serie um.

    Ohne diesen Schritt verschob „ganze Serie bearbeiten" die Serie: die
    Clients schicken Start und Ende des Vorkommens, das man gerade ansieht
    (``basis::2026-11-10``), der native Dienst loest die Kennung auf die Basis
    auf und setzt deren Start auf den 10.11. Alle Termine davor waren weg, ohne
    Rueckfrage. Das betraf das Saganta-Web (``eventUpdate``) und die App.

    Uebernommen wird, was man am Vorkommen geaendert hat: die Uhrzeit, die
    Dauer und eine Verschiebung um ganze Tage. Der Anker behaelt sein Datum.
    """
    alt_tag = _zeitpunkt(vorkommen + "T00:00:00").date()
    basis_start = _zeitpunkt(str(basis["start"]))
    basis_ende = _zeitpunkt(str(basis["end"]))
    neu_start = _zeitpunkt(rumpf["start"]) if rumpf.get("start") else None
    neu_ende = _zeitpunkt(rumpf["end"]) if rumpf.get("end") else None
    if neu_start is None:
        # Nur das Ende geaendert: die Dauer zaehlt ab dem Start des Vorkommens.
        neu_start = datetime.combine(alt_tag, basis_start.time())
    if neu_ende is None:
        neu_ende = neu_start + (basis_ende - basis_start)
    tage = (neu_start.date() - alt_tag).days
    anker = datetime.combine(basis_start.date() + timedelta(days=tage), neu_start.time())
    rumpf = dict(rumpf)
    rumpf["start"] = anker.isoformat()
    rumpf["end"] = (anker + (neu_ende - neu_start)).isoformat()
    return rumpf


@router.put("/{event_id}")
async def update_event(event_id: str, data: EventPatch, me: Me = CurrentUser) -> dict:
    # exclude_none = echtes Partial-Update.
    rumpf = data.model_dump(exclude_none=True)
    if rumpf.pop("wiederholung_aendern", False):
        rumpf["recurrence_rule"] = rumpf.get("recurrence_rule") or None
    else:
        rumpf.pop("recurrence_rule", None)
    basis_id, _, vorkommen = event_id.partition("::")
    if vorkommen and ("start" in rumpf or "end" in rumpf):
        vorkommen = vorkommen[:10]
        if len(vorkommen) != 10:
            raise HTTPException(422, f"Unbekannte Instanz-Kennung: {event_id}")
        basis = (await _events_upstream("GET", f"/api/events/{basis_id}")).json()
        if basis.get("recurrence_rule"):
            rumpf = _auf_anker_umrechnen(basis, vorkommen, rumpf)
        event_id = basis_id
    r = await _events_upstream("PUT", f"/api/events/{event_id}", json=rumpf)
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
