"""Der Aufruf am Modell, fuer alle Apps gleich.

Uebernommen aus ``kalender-bff/app/routes_assistent.py`` (Stufe 2, gemessen
15/15 mit homelab-smart). Was eine App ausmacht (Systemtext, Schema,
Kontext), bringt das Werkzeug der App mit; hier steht nur der Weg.
"""
from __future__ import annotations

import json

import httpx
from fastapi import HTTPException, status

from .config import settings

#: Nur Modelle im Haus (Entscheid 02.11.).
ERLAUBTE_MODELLE = {"homelab-smart", "homelab-fast"}


def modell() -> str:
    name = (settings.llm_model or "").strip()
    if not settings.llm_gateway_url or name not in ERLAUBTE_MODELLE:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Kein Modell im Haus konfiguriert (LLM_GATEWAY_URL, LLM_MODEL aus {sorted(ERLAUBTE_MODELLE)}).",
        )
    return name


def erstes_json(text: str) -> dict | None:
    t = text.strip()
    try:
        wert = json.loads(t)
    except ValueError:
        a, b = t.find("{"), t.rfind("}")
        if a < 0 or b <= a:
            return None
        try:
            wert = json.loads(t[a:b + 1])
        except ValueError:
            return None
    return wert if isinstance(wert, dict) else None


async def fragen(
    name: str, system: str, schema: dict, schema_name: str,
    verlauf: list[tuple[str, str]], kontext: str, nachricht: str,
) -> dict:
    """Ein Aufruf mit erzwungenem JSON-Schema; ``verlauf`` als (rolle, text)."""
    nachrichten = [{"role": "system", "content": system}]
    for rolle, text in verlauf[-10:]:
        nachrichten.append({"role": "user" if rolle == "nutzer" else "assistant", "content": text})
    nachrichten.append({"role": "user", "content": f"{kontext}\n\nNachricht: {nachricht}"})
    kopf = {}
    if settings.llm_gateway_key:
        kopf["Authorization"] = f"Bearer {settings.llm_gateway_key}"
    try:
        async with httpx.AsyncClient(timeout=settings.assistent_timeout_seconds) as client:
            r = await client.post(
                settings.llm_gateway_url.rstrip("/") + "/v1/chat/completions",
                headers=kopf,
                json={
                    "model": name,
                    "messages": nachrichten,
                    "max_tokens": 800,
                    "temperature": 0.1,
                    # gpt-oss gibt ohne ihn eine leere Antwort ohne Fehler;
                    # das Gateway verwirft ihn fuer Modelle, die ihn nicht kennen.
                    "reasoning_effort": "low",
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {"name": schema_name, "schema": schema},
                    },
                },
            )
        r.raise_for_status()
        inhalt = ((r.json().get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Modell nicht erreichbar: {e!r}"[:300]) from e
    obj = erstes_json(inhalt) if isinstance(inhalt, str) else None
    if obj is None:
        raise HTTPException(502, "Das Modell hat keine lesbare Antwort gegeben.")
    return obj
