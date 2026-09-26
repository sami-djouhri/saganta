"""Outbound-Delivery (opt-in Webhook). Kein Inbound-Credential in Saganta:
der User hinterlegt SEINE Webhook-URL (eigenes HA/ntfy/…); wir posten nur hin.
"""
from __future__ import annotations

import httpx
import structlog

from ..config import settings

log = structlog.get_logger()


def post_webhook(url: str, secret: str | None, payload: dict) -> bool:
    """POSTet das Briefing-Ereignis an eine user-eigene Webhook-URL. Best-effort."""
    if not url:
        return False
    headers = {"Content-Type": "application/json"}
    if secret:
        headers["Authorization"] = f"Bearer {secret}"
    try:
        with httpx.Client(timeout=settings.webhook_timeout) as client:
            resp = client.post(url, json=payload, headers=headers)
        ok = resp.status_code < 400
        if not ok:
            log.warning("delivery.webhook.status", status=resp.status_code)
        return ok
    except Exception as exc:
        log.warning("delivery.webhook.error", error=str(exc)[:200])
        return False
