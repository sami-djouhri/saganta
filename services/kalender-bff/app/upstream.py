from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException

from .auth import current_owner_sub
from .config import settings
from .tenant_sig import tenant_headers


@asynccontextmanager
async def authed_kalender_client() -> AsyncIterator[httpx.AsyncClient]:
    """httpx-Client mit gültiger Kalender-Session (Context-Manager).

    Der native Kalender (host) akzeptiert den Feed-Token NICHT direkt auf den
    Daten-Endpoints (/api/calendars, /api/events), die liegen hinter dem
    Session-Middleware. Stattdessen tauscht `/api/auth/token-login?token=…` den
    Feed-Token einmalig gegen eine `session_token`-Cookie, die der httpx-Cookie-Jar
    speichert; mit ihr gelten die Folge-Requests.
    """
    sub = current_owner_sub.get()
    headers = tenant_headers(sub) or None
    async with httpx.AsyncClient(
        base_url=settings.kalender_base_url,
        timeout=settings.kalender_timeout_seconds,
        headers=headers,
    ) as client:
        r = await client.get(
            "/api/auth/token-login", params={"token": settings.kalender_feed_token}
        )
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"kalender token-login fehlgeschlagen: {r.status_code}",
                request=r.request,
                response=r,
            )
        yield client


async def upstream(
    method: str,
    path: str,
    *,
    params: dict | None = None,
    json: dict | None = None,
) -> httpx.Response:
    """Ein Aufruf an den nativen Kalender, mit Session und Fehlerübersetzung.

    Lag urspruenglich als privates ``_upstream`` in ``routes_tasks.py``. Hochgezogen,
    als die Proxy-Routen fuer die native App dazukamen (Kontakte, Gewohnheiten,
    Mobile): vier Kopien derselben acht Zeilen waeren vier Stellen gewesen, an
    denen die Fehlerbehandlung auseinanderlaufen kann.

    Upstream-Fehler werden 1:1 durchgereicht (404 bleibt 404), damit die App
    unterscheiden kann, ob etwas fehlt oder der Dienst weg ist, ein pauschales
    502 haette beides gleich aussehen lassen.
    """
    async with authed_kalender_client() as client:
        try:
            r = await client.request(method, path, params=params, json=json)
        except httpx.HTTPError as e:
            raise HTTPException(502, f"kalender upstream unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"kalender error: {r.text[:200]}")
    return r
