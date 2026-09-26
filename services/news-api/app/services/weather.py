"""Wetter für das Briefing (Open-Meteo).

Bewusst ohne API-Key und ohne Homelab-Bezug: Saganta soll eigenständig sein, ein
Umweg über die Home-Assistant-Wetterentität wäre genau die Kopplung, die abgebaut
wird. Soft-Fail per Design wie llm_client/briefing_tts: `today()` gibt None
zurück, wenn etwas klemmt, und das Briefing bleibt gültig.

Tages-Cache im Prozess: der Scheduler erzeugt pro Nutzer einmal täglich; ohne
Cache würde ein erzwungenes Neu-Generieren (force=True) jedes Mal erneut abrufen.
"""
from __future__ import annotations

from datetime import date

import httpx
import structlog

from ..config import settings

log = structlog.get_logger()

# (lat, lon, iso-datum) -> Wetter-Dict. Klein und selbstbegrenzend, s.u.
_cache: dict[tuple[float, float, str], dict] = {}

# WMO-Wettercodes → deutscher Klartext. Open-Meteo liefert nur die Zahl.
_WMO = {
    0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bedeckt",
    45: "neblig", 48: "Nebel mit Reifablagerung",
    51: "leichter Nieselregen", 53: "Nieselregen", 55: "starker Nieselregen",
    56: "gefrierender Nieselregen", 57: "starker gefrierender Nieselregen",
    61: "leichter Regen", 63: "Regen", 65: "starker Regen",
    66: "gefrierender Regen", 67: "starker gefrierender Regen",
    71: "leichter Schneefall", 73: "Schneefall", 75: "starker Schneefall",
    77: "Schneegriesel",
    80: "leichte Schauer", 81: "Schauer", 82: "kräftige Schauer",
    85: "leichte Schneeschauer", 86: "Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "schweres Gewitter mit Hagel",
}


def describe(code: int | None) -> str:
    return _WMO.get(code, "") if code is not None else ""


def _coords(profile) -> tuple[float, float, str]:
    """Ort des Nutzers, sonst der neutrale Settings-Fallback."""
    lat = getattr(profile, "weather_lat", None)
    lon = getattr(profile, "weather_lon", None)
    place = getattr(profile, "weather_place", None)
    if lat is None or lon is None:
        return (settings.weather_default_lat, settings.weather_default_lon,
                settings.weather_default_place)
    return (float(lat), float(lon), place or "")


def today(profile, for_date: date | None = None) -> dict | None:
    """Tagesvorhersage als Dict oder None (Soft-Fail).

    Rückgabe: {place, code, text, temp_min, temp_max, precipitation_mm,
               precipitation_probability, sunrise, sunset}
    """
    if not settings.weather_url:
        return None
    for_date = for_date or date.today()
    lat, lon, place = _coords(profile)
    key = (round(lat, 3), round(lon, 3), for_date.isoformat())
    if key in _cache:
        return _cache[key]

    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ("weather_code,temperature_2m_min,temperature_2m_max,"
                  "precipitation_sum,precipitation_probability_max,sunrise,sunset"),
        "timezone": "Europe/Berlin",
        "start_date": for_date.isoformat(),
        "end_date": for_date.isoformat(),
    }
    try:
        with httpx.Client(timeout=settings.weather_timeout) as client:
            resp = client.get(settings.weather_url, params=params)
        resp.raise_for_status()
        daily = (resp.json() or {}).get("daily") or {}

        def first(name):
            values = daily.get(name) or []
            return values[0] if values else None

        code = first("weather_code")
        out = {
            "place": place,
            "code": code,
            "text": describe(code),
            "temp_min": first("temperature_2m_min"),
            "temp_max": first("temperature_2m_max"),
            "precipitation_mm": first("precipitation_sum"),
            "precipitation_probability": first("precipitation_probability_max"),
            "sunrise": first("sunrise"),
            "sunset": first("sunset"),
        }
        if out["temp_max"] is None:
            return None
        # Cache nur den aktuellen Tag halten, sonst wächst er unbegrenzt.
        _cache.clear()
        _cache[key] = out
        return out
    except Exception as exc:  # Netz weg / Open-Meteo down / Format geändert
        log.warning("weather.fetch.error", error=str(exc)[:200])
        return None


def spoken(weather: dict | None) -> str:
    """Ein gesprochener Satz fürs Audio. Leerstring, wenn kein Wetter da ist."""
    if not weather:
        return ""
    parts = []
    place = weather.get("place")
    text = weather.get("text")
    lead = f"Das Wetter in {place}" if place else "Das Wetter"
    parts.append(f"{lead}: {text}." if text else f"{lead}.")

    tmin, tmax = weather.get("temp_min"), weather.get("temp_max")
    if tmin is not None and tmax is not None:
        parts.append(f"{round(tmin)} bis {round(tmax)} Grad.")
    elif tmax is not None:
        parts.append(f"Bis {round(tmax)} Grad.")

    prob = weather.get("precipitation_probability")
    millimetres = weather.get("precipitation_mm")
    if prob is not None and prob >= 30:
        if millimetres:
            # Der Text wird VORGELESEN: „7.8" spricht das TTS als „sieben punkt acht".
            # Ganze Millimeter reichen für eine Wetteransage; bei unter einem
            # Millimeter wäre „0 Millimeter" irreführend, deshalb nur die Prozentzahl.
            gerundet = round(millimetres)
            if gerundet >= 1:
                parts.append(f"Regenwahrscheinlichkeit {round(prob)} Prozent, "
                             f"etwa {gerundet} Millimeter.")
            else:
                parts.append(f"Regenwahrscheinlichkeit {round(prob)} Prozent.")
        else:
            parts.append(f"Regenwahrscheinlichkeit {round(prob)} Prozent.")
    return " ".join(parts)
