"""Clients fuer die beiden fremden Dienste, die dieser Dienst anspricht.

**Warum der Lager-Client fehlschlagen darf und nicht einfach weniger Header
schickt.** Das Lager bestimmt den Mandanten aus ``X-Saganta-Sub`` und prueft den
Wert gegen ``X-Saganta-Sub-Sig`` (HMAC, geteiltes Geheimnis). Es kennt drei
Antworten, und die gefaehrlichste ist die freundliche:

| Aufruf | Antwort des Lagers |
|---|---|
| Sub mit gueltiger Signatur | 200, Bestand **dieses** Mandanten |
| Sub ohne oder mit falscher Signatur | 401 (bei ``TENANT_HEADER_ENFORCE=1``) |
| **ganz ohne Header** | 200, Bestand des **Owners** (``DEFAULT_OWNER_SUB``) |

Bis zum 2026-10-16 setzte diese Datei nur ``X-Saganta-Sub``, ohne Signatur, und
``LAGER_TENANT_SECRET`` stand hier nirgends: die Spiegelung antwortete also
durchgehend mit 401, seit das Lager scharf geschaltet ist.

⚠️ Die naheliegende Behebung ist schlimmer als der Fehler. ``kopfzeilen()`` gibt
bei fehlendem Geheimnis bewusst ein **leeres** Dict zurueck -- richtig fuer einen
Dienst ohne Mandanten, hier aber faellt der Aufruf damit in die dritte Zeile der
Tabelle. Jeder Saganta-Nutzer bekaeme dann die Elektronikliste des Owners in
seine eigene Asset-Tabelle gespiegelt, und zwar mit HTTP 200 und ohne eine
Logzeile. Das heutige 401 ist der einzige Grund, warum das nicht passiert.

Deshalb entscheidet hier **nicht** die Kopfzeilen-Funktion, sondern eine eigene
Bedingung: liegt ein Mandant vor und fehlt das Geheimnis, wird kein Client
gebaut. Ein Dienst, der seine Mandanten nicht nachweisen kann, spricht das Lager
gar nicht an. Gegenprobe steht in ``tests/test_lager_signatur.py``.
"""

import httpx
from fastapi import HTTPException, status
from saganta_dienst.tenant_sig import kopfzeilen

from .config import settings


def lager_client(owner_sub: str | None = None) -> httpx.AsyncClient:
    """Client fuer das Lager, im Namen dieses Mandanten.

    ``owner_sub=None`` ist der headerlose Pfad und bleibt erlaubt: dort gibt es
    keinen Mandanten, den man falsch zuordnen koennte. Mit Mandant ist die
    Signatur Pflicht.
    """
    headers: dict[str, str] | None = None
    if owner_sub:
        headers = kopfzeilen(owner_sub, settings.lager_tenant_secret)
        if not headers:
            # Kein stiller Rueckfall: ohne diese Zeile waere der Aufruf
            # headerlos und das Lager antwortete mit den Daten des Owners.
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Lager-Spiegelung nicht verfuegbar: LAGER_TENANT_SECRET ist in "
                "assets-api nicht konfiguriert. Setzen mit "
                "scripts/mandanten-kette.py --setzen, dann assets-api neu erstellen.",
            )
    return httpx.AsyncClient(
        base_url=settings.lager_base_url,
        timeout=settings.lager_timeout_seconds,
        headers=headers,
    )


def marktwatch_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.marktwatch_base_url,
        timeout=settings.marktwatch_timeout_seconds,
    )
