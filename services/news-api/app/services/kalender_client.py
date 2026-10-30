"""Read-only Kalender-Kopplung für die „Dein Tag"-Sektion des Briefings.

Ruft die öffentlichen feed_token-Endpunkte des nativen kalender:8085 (genau wie HA):
Tagestyp + Termine + Tagesziele + geplante Habit-/Lern-Sessions, dazu ein knapper
Ausblick auf morgen. Alles best-effort/Soft-Fail: ist der Kalender aus/leer/
unerreichbar, gibt `fetch_day_context` None zurück und die „Dein Tag"-Sektion
entfällt, das News-Briefing bleibt gültig.

**Zeitbudget statt N×Timeout.** Der Kontext braucht sechs Abrufe. Mit einem
Timeout *je* Abruf wäre der schlechteste Fall die Summe (6 × `kalender_timeout`),
und der träfe genau dann ein, wenn der Kalender ohnehin klemmt. `_Budget` deckelt
die Gesamtdauer: was nach Ablauf noch offen ist, wird übersprungen statt erneut
erwartet. Ein langsamer Kalender kostet dann das Budget, nicht ein Vielfaches.
Der Ausblick auf morgen steht bewusst am Ende der Reihenfolge, er ist die
Zugabe, die als erstes fallen darf.

Multiuser: der optionale `X-Saganta-Sub`-Header scoped pro User (der Owner ist im
Kalender `DEFAULT_OWNER_SUB` → auch ohne Header korrekt). Der Tagestyp liegt aktuell
in globalen System-Kalendern (owner_sub NULL), für Fremd-User daher (noch) der
Owner-Tagestyp; für den Owner-PoC exakt richtig.
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import httpx
import structlog

from ..config import settings
from .tenant_sig import tenant_headers

log = structlog.get_logger()

# Wie viel Gesamtzeit der ganze Tageskontext höchstens kosten darf, ein Vielfaches
# des Einzel-Timeouts, aber eben ein *begrenztes*.
_TOTAL_BUDGET_FACTOR = 2.5


def available() -> bool:
    return bool(settings.kalender_url and settings.kalender_feed_token)


class _Budget:
    """Restlaufzeit-Wächter für eine Folge von Abrufen."""

    def __init__(self, seconds: float) -> None:
        self._deadline = time.monotonic() + seconds

    def left(self) -> float:
        return self._deadline - time.monotonic()

    def spent(self) -> bool:
        return self.left() <= 0.25  # unter 250 ms lohnt kein Abruf mehr


def _get(client: httpx.Client, url: str, params: dict, budget: _Budget) -> dict | None:
    """Ein Abruf innerhalb des Restbudgets. None = übersprungen oder fehlgeschlagen."""
    if budget.spent():
        return None
    try:
        r = client.get(url, params=params, timeout=min(settings.kalender_timeout, budget.left()))
    except Exception as exc:
        log.warning("kalender.fetch.error", url=url[-40:], error=str(exc)[:200])
        return None
    if r.status_code != 200:
        log.warning("kalender.fetch.status", url=url[-40:], status=r.status_code)
        return None
    try:
        return r.json() or {}
    except ValueError:
        return None


def fetch_day_context(sub: str, for_date: date) -> dict | None:
    """Tagestyp + Termine + Ziele + Lern-Sessions für (sub, Datum), plus Ausblick
    auf den Folgetag. None = nichts Brauchbares zu holen."""
    if not available():
        return None
    base = settings.kalender_url.rstrip("/")
    params_today = {"date": for_date.isoformat(), "token": settings.kalender_feed_token}
    budget = _Budget(settings.kalender_timeout * _TOTAL_BUDGET_FACTOR)
    out: dict = {"day_type": None, "events": [], "goals": [], "sessions": [], "tomorrow": None}

    with httpx.Client(headers=tenant_headers(sub)) as c:
        dt = _get(c, f"{base}/api/day-type", params_today, budget)
        if dt:
            out["day_type"] = dt.get("type")
        for key, path in (
            ("events", "/api/day-type/events"),
            ("sessions", "/api/day-type/sessions"),
            ("goals", "/api/day-type/goals"),
        ):
            data = _get(c, f"{base}{path}", params_today, budget)
            if data:
                out[key] = data.get(key, []) or []
        out["tomorrow"] = _fetch_tomorrow(c, base, for_date + timedelta(days=1), budget)

    if not any((out["day_type"], out["events"], out["goals"], out["sessions"], out["tomorrow"])):
        return None
    return out


def _fetch_tomorrow(
    client: httpx.Client, base: str, day: date, budget: _Budget
) -> dict | None:
    """Knapper Ausblick: Tagestyp + Termine des Folgetags.

    Das ist der Teil, der ein Morgen-Briefing von einer Tagesanzeige unterscheidet:
    „morgen ist Arbeitstag, erster Termin 8:00" ist abends wie morgens die Information,
    nach der man sonst selbst schaut. Ziele/Sessions bleiben bewusst draußen: der
    Habit-Scheduler plant sie erst am Tag selbst, ein Vorgriff wäre geraten.
    """
    params = {"date": day.isoformat(), "token": settings.kalender_feed_token}
    dt = _get(client, f"{base}/api/day-type", params, budget)
    ev = _get(client, f"{base}/api/day-type/events", params, budget)
    day_type = (dt or {}).get("type")
    events = (ev or {}).get("events", []) or []
    if not day_type and not events:
        return None
    return {"date": day.isoformat(), "day_type": day_type, "events": events}
