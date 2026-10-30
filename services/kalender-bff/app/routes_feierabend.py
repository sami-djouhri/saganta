"""„Feierabend heute": Tag abhaken ohne schlechtes Gewissen.

Ein Knopf im Saganta-Kalender: die heute noch offenen **Routine-Termine**
(wiederkehrende Lern-/Homelab-/Lese-/Pflanz-Blöcke) werden per EXDATE aus der
Reihe genommen (nur heute), der adaptive Sekretär auf „schonen" gestellt, und
das Abgesagte in freie Slots der nächsten Tage neu verplant (schlaf- und
mahlzeiten-bewusst). Echte Einzeltermine, Arbeit/Schule, Feiertage/Geburtstage
bleiben unangetastet.

Zeit-Referenzen (heutiges Datum + „jetzt" in Minuten) kommen vom Aufrufer
(SvelteKit-Server, der Europe/Berlin via Intl korrekt kennt), der BFF-Container
braucht so keine Zeitzonen-DB.
"""
from datetime import date as date_cls, datetime, timedelta

from fastapi import APIRouter, HTTPException
import httpx
from pydantic import BaseModel, Field

from .auth import CurrentUser, Me
from .upstream import authed_kalender_client

router = APIRouter()

# Wachfenster + Mahlzeiten-Puffer für Neu-Verplanung (Minuten seit Mitternacht).
WAKE_MIN = 8 * 60
BED_MIN = 21 * 60 + 30
MEALS = [(12 * 60 + 30, 13 * 60 + 15), (18 * 60 + 30, 19 * 60 + 15)]
HORIZON_DAYS = 7


def _is_routine(ev: dict) -> bool:
    """Absagbar = wiederkehrende Routine (Serie), kein System/Tagestyp.
    `recurrence_rule` fängt auch den DTSTART-Tag (Basis-Event, dort ist
    `is_recurring_instance` noch nicht gesetzt). Einzeltermine bleiben stehen;
    Arbeit/Schule sind daytype-Kalender und fliegen schon über den cid-Check raus."""
    cid = ev.get("calendar_id") or ""
    if cid.startswith("daytype-") or cid.startswith("system-geburtstage"):
        return False
    return bool(ev.get("is_recurring_instance") or ev.get("recurrence_rule"))


def _min_of(iso: object) -> int | None:
    """Naive Berlin-ISO ('YYYY-MM-DDTHH:MM:SS') → Minuten seit Mitternacht."""
    s = str(iso or "")
    if len(s) < 16:
        return None
    try:
        return int(s[11:13]) * 60 + int(s[14:16])
    except ValueError:
        return None


def _start(ev: dict) -> object:
    return ev.get("start_at") or ev.get("start")


def _end(ev: dict) -> object:
    return ev.get("end_at") or ev.get("end")


def _busy(events: list[dict]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for ev in events:
        if ev.get("all_day"):
            continue
        s = _min_of(_start(ev))
        e = _min_of(_end(ev))
        if s is None or e is None or e <= s:
            continue
        out.append((s, e))
    out.extend(MEALS)  # Mahlzeiten als belegt behandeln → Ess-Lücken bleiben frei
    return out


def _fits(start: int, dur: int, busy: list[tuple[int, int]]) -> bool:
    end = start + dur
    if start < WAKE_MIN or end > BED_MIN:
        return False
    return all(not (start < be and end > bs) for bs, be in busy)


def _find_slot(events: list[dict], dur: int, prefer: int | None) -> int | None:
    busy = _busy(events)
    candidates: list[int] = []
    if prefer is not None:
        candidates.append(prefer)
    t = WAKE_MIN
    while t + dur <= BED_MIN:
        candidates.append(t)
        t += 30
    for c in candidates:
        if _fits(c, dur, busy):
            return c
    return None


class FeierabendIn(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    now_minutes: int = Field(default=-1, ge=-1, le=1440)  # -1 = alles absagen
    replan: bool = True
    checkin: bool = True


async def _get_events(client: httpx.AsyncClient, day: str) -> list[dict]:
    r = await client.get("/api/events", params={"start": day, "end": day + "T23:59:59"})
    if r.status_code >= 400:
        return []
    data = r.json() if r.content else []
    return data if isinstance(data, list) else []


@router.post("/api/feierabend")
async def feierabend(data: FeierabendIn, me: Me = CurrentUser) -> dict:
    today = data.date
    cancelled: list[dict] = []
    planned: list[dict] = []

    async with authed_kalender_client() as client:
        try:
            evs = await _get_events(client, today)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e

        # Nur die heute noch NICHT abgeschlossene Routine (Ende ≥ jetzt) absagen.
        routine = []
        for ev in evs:
            if not _is_routine(ev):
                continue
            end_min = _min_of(_end(ev))
            if data.now_minutes >= 0 and end_min is not None and end_min < data.now_minutes:
                continue  # schon vorbei → in Ruhe lassen
            routine.append(ev)

        for ev in routine:
            base = str(ev.get("id") or "").split("::")[0]
            if not base:
                continue
            try:
                r = await client.delete(f"/api/events/{base}/instances/{today}")
            except httpx.HTTPError:
                continue
            if r.status_code < 400:
                cancelled.append(
                    {
                        "title": ev.get("title"),
                        "calendar_id": ev.get("calendar_id"),
                        "start": _start(ev),
                        "end": _end(ev),
                    }
                )

        # Sekretär auf „schonen", kein Aktivitäts-Nudge mehr heute.
        if data.checkin and cancelled:
            try:
                await client.post(
                    "/api/assistant/checkin",
                    json={"date": today, "energy": "niedrig", "mood": "neutral",
                          "note": "Feierabend – Tag gelaufen"},
                )
            except httpx.HTTPError:
                pass

        # Abgesagtes in freie Slots der Folgetage verschieben (einmalig, kein RRULE).
        if data.replan and cancelled:
            day_cache: dict[str, list[dict]] = {}
            try:
                base_day = date_cls.fromisoformat(today)
            except ValueError:
                base_day = None
            for item in cancelled:
                s = _min_of(item["start"])
                e = _min_of(item["end"])
                dur = (e - s) if (s is not None and e is not None and e > s) else None
                if not dur or base_day is None:
                    planned.append({"title": item["title"], "day": None})
                    continue
                placed = False
                for i in range(1, HORIZON_DAYS + 1):
                    d = (base_day + timedelta(days=i)).isoformat()
                    if d not in day_cache:
                        try:
                            day_cache[d] = await _get_events(client, d)
                        except httpx.HTTPError:
                            day_cache[d] = []
                    slot = _find_slot(day_cache[d], dur, s)
                    if slot is None:
                        continue
                    sh, sm = divmod(slot, 60)
                    eh, em = divmod(slot + dur, 60)
                    body = {
                        "calendar_id": item["calendar_id"],
                        "title": f"{item['title']} (verschoben)",
                        "start": f"{d}T{sh:02d}:{sm:02d}:00",
                        "end": f"{d}T{eh:02d}:{em:02d}:00",
                        "all_day": False,
                    }
                    try:
                        rr = await client.post("/api/events", json=body)
                    except httpx.HTTPError:
                        break
                    if rr.status_code < 400:
                        # In den Tages-Cache aufnehmen, damit der nächste Make-up ihn meidet.
                        day_cache[d].append(body)
                        planned.append({"title": item["title"], "day": d,
                                        "start": body["start"], "end": body["end"]})
                        placed = True
                    break
                if not placed:
                    planned.append({"title": item["title"], "day": None})

    return {"date": today, "cancelled": cancelled, "planned": planned}
