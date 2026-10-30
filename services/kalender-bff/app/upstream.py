from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

import httpx
from fastapi import HTTPException, status

from .auth import current_owner_sub
from .config import settings
from .tenant_sig import SIG_HEADER, tenant_headers


@asynccontextmanager
async def authed_kalender_client() -> AsyncIterator[httpx.AsyncClient]:
    """httpx-Client mit einer Kalender-Sitzung **dieses** Mandanten.

    Der native Kalender akzeptiert auf den Daten-Endpunkten keinen Token im
    Query, die liegen hinter der Sitzungs-Middleware. Es braucht also einen
    Anmeldeschritt, dessen Cookie der httpx-Jar fuer die Folge-Aufrufe haelt.

    **Hier stand bis zum 2026-10-16 ``token-login?token=<Owner-Feed-Token>``,
    und das war die falsche Anmeldung.** Der Owner-Feed-Token loest beim nativen
    Dienst auf ``DEFAULT_OWNER_SUB`` auf: die Sitzung gehoerte damit dem Owner,
    und zwar in jedem Aufruf jedes Mandanten. Dass trotzdem niemand fremde Daten
    sah, lag an einem zweiten, unabhaengigen Weg -- ``get_db`` scopt ueber
    ``X-Saganta-Sub``, nicht ueber die Sitzung. Identitaet und Scoping waren also
    zwei verschiedene Wahrheiten im selben Aufruf.

    Gemessen am 2026-10-16, bevor das hier umgebaut wurde: ueber diesen Pfad
    bekam ein fremdes Pruefkonto von ``/api/feed-token`` den **Token des
    Owners**, Byte fuer Byte denselben. Genau eine native Route liest die
    Sitzungs-Identitaet als Wert statt nur als Schranke (``get_feed_token``), und
    genau dort fiel es auf. Der Owner-Riegel im ``kalender-bff`` war die Sperre
    davor; wer ihn entfernt, ohne das hier zu aendern, oeffnet das Loch.

    Jetzt ``gate-login``: der nimmt den **signierten** Mandanten aus
    ``X-Saganta-Sub``/``-Sig`` und gibt eine Sitzung fuer genau diesen aus. Er
    wurde am 2026-09-27 fuer den nginx-Vhost-Weg gebaut; derselbe Grund gilt
    hier. Damit stimmen Sitzung und Scoping ueberein, und ein fehlendes oder
    falsches Geheimnis endet in einem 401 beim Anmelden statt in einem stillen
    Rueckfall auf den Owner (``resolve_owner_sub`` tut genau das, wenn der Header
    fehlt).

    ⚠️ Fail-closed ohne Mandanten: alle 81 Aufrufstellen liegen hinter
    ``CurrentUser``, ein leerer ``sub`` ist hier also kein Normalfall, sondern
    ein Fehler. Eine Anmeldung als Owner waere der bequemste Ausweg und genau
    der Fehler von vorher.
    """
    sub = current_owner_sub.get()
    if not sub:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Kalender-Aufruf ohne Mandanten: es gibt keinen Pfad, auf dem das "
            "richtig waere. Eine Anmeldung als Eigentuemer ist hier bewusst nicht "
            "vorgesehen.",
        )
    headers = tenant_headers(sub)
    # Geprueft wird die SIGNATUR, nicht ob ueberhaupt Kopfzeilen entstanden.
    # Die beiden Fassungen dieser Funktion im Repo verhalten sich ohne Geheimnis
    # verschieden: die geteilte `saganta_dienst.tenant_sig.kopfzeilen` gibt ein
    # leeres Dict, die dienst-lokale `tenant_headers` gibt den **Sub ohne
    # Signatur**. Eine Pruefung auf `not headers` greift bei der zweiten nie, und
    # genau das ist beim Schreiben dieses Tests passiert: der Aufruf ging
    # hinaus und bekam stromaufwaerts ein nacktes 401, ohne dass hier etwas
    # gesagt worden waere.
    if SIG_HEADER not in headers:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Kalender-Aufruf nicht moeglich: KALENDER_TENANT_SECRET ist im "
            "kalender-bff nicht konfiguriert. Setzen mit "
            "kalender/scripts/tenant-geheimnis-ausrollen.sh, dann neu erstellen.",
        )
    async with httpx.AsyncClient(
        base_url=settings.kalender_base_url,
        timeout=settings.kalender_timeout_seconds,
        headers=headers,
    ) as client:
        r = await client.get("/api/auth/gate-login")
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"kalender gate-login fehlgeschlagen: {r.status_code}",
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
