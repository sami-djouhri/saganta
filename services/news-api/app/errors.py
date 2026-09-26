"""Fehlertexte, die auch dann etwas aussagen, wenn die Exception selbst schweigt."""
from __future__ import annotations

import httpx


def describe(exc: BaseException, limit: int = 200) -> str:
    """Immer ein aussagekräftiger Fehlertext, nie ein leerer String.

    ``str(exc)`` ist bei genau der Fehlerklasse leer, die ein Feed-Poller am
    häufigsten trifft: httpx wirft ``ReadTimeout``/``ConnectTimeout``/
    ``ConnectError``/``RemoteProtocolError`` regelmäßig ohne Message. Gemessen
    über 10 Tage Betrieb: 7 von 8 protokollierten Poll-Fehlern hatten deshalb
    ``error=""``, man sah, DASS eine Quelle ausfiel, nie warum.

    Schlimmer als das Log ist die Persistenz: ``FeedSource.last_error`` bekam
    denselben leeren String, und "" ist falsy. Eine dauerhaft kaputte Quelle war
    damit von einer gesunden (``last_error=None``) nicht mehr zu unterscheiden.

    Bei HTTP-Fehlern steht die Fehlerklasse im Statuscode, nicht im Fließtext:
    httpx' Standardmeldung ist mehrzeilig und endet in einem MDN-Link.
    """
    name = type(exc).__name__

    if isinstance(exc, httpx.HTTPStatusError):
        return f"{name}: HTTP {exc.response.status_code} für {exc.request.url}"[:limit]

    text = str(exc).strip()
    if not text:
        return name
    return f"{name}: {text}"[:limit]
