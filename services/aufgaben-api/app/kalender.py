"""Der Weg zum Kalender, im Namen des Aufrufers.

Der Kalender bleibt die Engine fuer Zeit: freie Fenster, Tageskapazitaet,
Tageszeit-Vorlieben und die Tagesziele. Dieser Dienst fragt ihn ueber den
`kalender-bff`, nicht direkt: dort sitzen Mandanten-Signatur und Pruefung, und
ein zweiter Weg an `kalender:8085` vorbei waere eine zweite Stelle, an der das
stimmen muss.

Das Token stempelt dieser Dienst selbst, mit `aud=kalender-bff` und dem
`sub` des Aufrufers, 60 Sekunden gueltig. Es ist derselbe Schluessel, mit dem
jede Saganta-App ihre Backend-Token stempelt; ein Dienst, der ihn zum Pruefen
kennt, kann damit auch stempeln. Der `sub` kommt ausschliesslich aus dem
bereits geprueften Token der Anfrage, nie aus einem Parameter.
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from jose import jwt

from .auth import Me
from .config import settings

ZIELGRUPPE = "kalender-bff"
WARTEZEIT_S = 30.0


class KalenderNichtErreichbar(Exception):
    """Netz, Zeitueberschreitung oder 5xx: der Tag ist ohne Kalender zu zeigen."""


def _token(me: Me) -> str:
    jetzt = int(time.time())
    return jwt.encode(
        {
            "iss": "saganta",
            "sub": me.sub,
            "email": me.email,
            "aud": ZIELGRUPPE,
            "iat": jetzt,
            "exp": jetzt + 60,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def aufruf(me: Me, methode: str, pfad: str, **kw: Any) -> Any:
    """Ein Aufruf am kalender-bff. Wirft bei 4xx ``httpx.HTTPStatusError``."""
    try:
        with httpx.Client(base_url=settings.kalender_bff_url, timeout=WARTEZEIT_S) as klient:
            antwort = klient.request(
                methode, pfad, headers={"Authorization": f"Bearer {_token(me)}"}, **kw
            )
    except httpx.HTTPError as exc:
        raise KalenderNichtErreichbar(str(exc)) from exc
    if antwort.status_code >= 500:
        raise KalenderNichtErreichbar(f"kalender-bff {antwort.status_code}")
    antwort.raise_for_status()
    return antwort.json() if antwort.content else None
