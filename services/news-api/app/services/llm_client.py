"""Dünner LLM-Gateway-Client (LiteLLM, OpenAI-kompatibel).

Soft-Fail per Design: ist das Gateway nicht konfiguriert oder antwortet es nicht,
gibt `summarize` None zurück und der Aufrufer nutzt den Roh-Feed-Text weiter. So
funktioniert das Briefing auch ohne LLM, nur weniger redaktionell.
"""
from __future__ import annotations

import httpx
import structlog

from ..config import settings

log = structlog.get_logger()


def available() -> bool:
    return bool(settings.llm_gateway_url and settings.llm_gateway_key)


def chat(system: str, user: str, max_tokens: int = 400, temperature: float = 0.3) -> str | None:
    """Ein einzelner Chat-Completion-Call. None bei Nichtverfügbarkeit/Fehler."""
    if not available():
        return None
    url = settings.llm_gateway_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    headers = {"Authorization": f"Bearer {settings.llm_gateway_key}"}
    try:
        with httpx.Client(timeout=settings.llm_timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        text = (data.get("choices") or [{}])[0].get("message", {}).get("content")
        return text.strip() if isinstance(text, str) and text.strip() else None
    except Exception as exc:  # Gateway down / Budget aus / Timeout → Soft-Fail
        log.warning("llm.chat.error", error=str(exc)[:200])
        return None
