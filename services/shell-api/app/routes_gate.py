"""SSO-Gate für nginx `auth_request`.

Native Dienste (briefkasten/nachrichten/nativer Kalender) haben nur schwache LAN-Auth
(statisches Token-Auto-Login bzw. gar keine). Um sie öffentlich über `*.saganta.de`
anzubieten, gatet nginx jeden Request erst hier: dieser Endpoint prüft die better-auth
`.saganta.de`-Session-Cookie und liefert 204 (eingeloggt) bzw. 401 (nicht). Erst hinter
diesem Gate greift das schwache Auto-Login der nativen Dienste, ein unauthentifizierter
Public-Request kommt also NIE am nativen Dienst an.

Bewusst stdlib-`urllib` (kein httpx-Runtime-Dep). Sync-Endpoint genügt für den
leichtgewichtigen internen get-session-Call.
"""

from __future__ import annotations

import json
import urllib.request

from fastapi import APIRouter, Request, Response

from .config import settings

router = APIRouter()


@router.get("/auth/check")
def auth_check(request: Request) -> Response:
    cookie = request.headers.get("cookie", "")
    # Schnell-Filter: ohne Session-Cookie gar nicht erst nachfragen.
    if "saganta.session_token" not in cookie:
        return Response(status_code=401)
    try:
        req = urllib.request.Request(
            f"{settings.auth_service_url}/api/auth/get-session",
            headers={"Cookie": cookie},
        )
        with urllib.request.urlopen(req, timeout=4) as r:  # noqa: S310 (interne URL)
            body = r.read().decode("utf-8", "replace").strip()
    except Exception:
        # Fail-closed: Auth-Service nicht erreichbar → kein Zugang.
        return Response(status_code=401)

    # better-auth get-session: `null` = keine Session; sonst Objekt mit `user`.
    try:
        data = json.loads(body)
    except ValueError:
        return Response(status_code=401)
    if isinstance(data, dict) and data.get("user"):
        return Response(status_code=204)
    return Response(status_code=401)
