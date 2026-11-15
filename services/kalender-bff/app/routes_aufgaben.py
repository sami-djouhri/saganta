"""Was im Aufgaben-Dienst geplant ist, fuer die Kalenderansicht (seit 2026-11-11).

Die Aufgaben gehoeren `aufgaben-api` (seit 2026-11-03). Der Kalender zeigte
sie danach nirgends mehr: Web und App lasen weiter `/api/todos` des nativen
Kalenders, und diese Tabelle ist seit dem Umzug leer. Eine eingeplante Aufgabe
stand also in der Aufgaben-App mit Uhrzeit und im Kalender nicht.

Dieser Weg liest nur. Bearbeitet wird eine Aufgabe in der Aufgaben-App; der
Kalender haelt keine Kopie.

Das Token stempelt der BFF selbst, mit `aud=aufgaben-api` und dem `sub`
des schon geprueften Aufrufers, 60 Sekunden gueltig (Muster
`projectdeck-api/app/aufgaben_dienst.py`). Der `sub` kommt nie aus einem
Parameter.
"""
import time

import httpx
from fastapi import APIRouter, HTTPException, Query, status
from jose import jwt

from .auth import CurrentUser, Me
from .config import settings

router = APIRouter()

ZIELGRUPPE = "aufgaben-api"
_DATE = r"^\d{4}-\d{2}-\d{2}$"


def _token(me: Me) -> str:
    jetzt = int(time.time())
    return jwt.encode(
        {"iss": "saganta", "sub": me.sub, "email": me.email, "aud": ZIELGRUPPE,
         "iat": jetzt, "exp": jetzt + 60},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


@router.get("/api/aufgaben/zeitraum")
async def aufgaben_im_zeitraum(
    me: Me = CurrentUser,
    von: str = Query(..., pattern=_DATE),
    bis: str = Query(..., pattern=_DATE),
) -> list:
    """Offene Aufgaben mit Uhrzeit oder Plantag im Zeitraum, Felder wie im Dienst.

    ⚠️ 503, wenn der Dienst nicht antwortet: die Kalenderansicht zeigt dann ihre
    Termine ohne Aufgaben, statt zu scheitern (fail-soft beim Aufrufer).
    """
    try:
        async with httpx.AsyncClient(
            base_url=settings.aufgaben_api_url, timeout=settings.aufgaben_timeout_seconds
        ) as klient:
            r = await klient.get(
                "/api/aufgaben/zeitraum",
                params={"von": von, "bis": bis},
                headers={"Authorization": f"Bearer {_token(me)}"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Aufgaben-Dienst nicht erreichbar") from exc
    if r.status_code >= 500:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Aufgaben-Dienst {r.status_code}")
    if r.status_code >= 400:
        raise HTTPException(r.status_code, r.text[:200])
    return r.json()
