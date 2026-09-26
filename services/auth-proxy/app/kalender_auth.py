"""Holt einen Kalender-JWT via FEED_TOKEN → /api/auth/token-login und cached ihn.

Hintergrund: Der Kalender-Container schützt /api/* mit `get_current_user`,
das HS256-JWTs aus `session_token`-Cookies ODER aus `Authorization: Bearer`
akzeptiert. JWTs werden via Master-Password ODER FEED_TOKEN ausgestellt.
Wir nutzen den FEED_TOKEN, weil er rotierbar ist und nicht im Klartext
zur User-Authentifizierung dient.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import httpx

from .config import settings

logger = logging.getLogger(__name__)


@dataclass
class _CachedToken:
    value: str
    expires_at: datetime


class KalenderTokenCache:
    def __init__(self) -> None:
        self._token: _CachedToken | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> str | None:
        if not settings.kalender_feed_token:
            return None

        now = datetime.now(timezone.utc)
        cached = self._token
        if cached and cached.expires_at > now:
            return cached.value

        async with self._lock:
            cached = self._token
            if cached and cached.expires_at > now:
                return cached.value

            try:
                async with httpx.AsyncClient(timeout=settings.timeout_seconds, follow_redirects=False) as c:
                    r = await c.get(
                        f"{settings.kalender_base_url.rstrip('/')}/api/auth/token-login",
                        params={"token": settings.kalender_feed_token, "redirect": "/"},
                    )
                if r.status_code not in (302, 307):
                    logger.warning("kalender token-login status=%s body=%s", r.status_code, r.text[:200])
                    return None
                cookie = r.cookies.get("session_token")
                if not cookie:
                    # httpx folgt Set-Cookie über cookies, kann aber bei Redirects
                    # leer sein: fallback auf Header-Parsing.
                    set_cookie = r.headers.get("set-cookie", "")
                    if "session_token=" in set_cookie:
                        cookie = set_cookie.split("session_token=", 1)[1].split(";", 1)[0]
                if not cookie:
                    logger.warning("kalender token-login: no session_token cookie")
                    return None
                expires = now + timedelta(hours=max(1, settings.kalender_token_ttl_hours))
                self._token = _CachedToken(value=cookie, expires_at=expires)
                logger.info("kalender token acquired, valid until %s", expires.isoformat())
                return cookie
            except httpx.HTTPError as exc:
                logger.warning("kalender token-login failed: %s", exc)
                return None

    def invalidate(self) -> None:
        self._token = None


kalender_cache = KalenderTokenCache()
