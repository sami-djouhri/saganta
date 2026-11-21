"""Verknuepfungen in den Notizen abraeumen, wenn eine Aufgabe geloescht wird.

Der Notizen-Dienst speichert zu jeder Verknuepfung nur Typ, Kennung und eine
Kopie der Beschriftung. Loeschte man eine Aufgabe, blieb die Verknuepfung an
der Notiz stehen und zeigte auf nichts (gemeldet 2026-11-21). Geloescht wird
aus drei Oberflaechen (Web, App, ProjectDeck), deshalb raeumt dieser Dienst
selbst ab und nicht jede Oberflaeche fuer sich.

Token wie in `kalender.py`: selbst gestempelt, `aud=notizen-api`, `sub` nur
aus dem geprueften Token der Anfrage, 60 Sekunden gueltig.
Im Hintergrund und fail-soft: das Loeschen der Aufgabe haengt nicht an den
Notizen. Scheitert der Aufruf, steht es im Log; die Notizen-Oberflaeche bietet
am X der Verknuepfung das Entfernen weiter an.
"""
from __future__ import annotations

import time

import httpx
import structlog
from fastapi import BackgroundTasks
from jose import jwt

from .auth import Me
from .config import settings

log = structlog.get_logger()
ZIELGRUPPE = "notizen-api"


def _token(me: Me) -> str:
    jetzt = int(time.time())
    return jwt.encode(
        {"iss": "saganta", "sub": me.sub, "email": me.email, "aud": ZIELGRUPPE, "iat": jetzt, "exp": jetzt + 60},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _abraeumen(me: Me, aufgabe_id: str) -> None:
    if not settings.notizen_api_url:
        return
    try:
        with httpx.Client(base_url=settings.notizen_api_url, timeout=10.0) as klient:
            antwort = klient.delete(
                "/api/notizen/verknuepft",
                params={"typ": "aufgabe", "ref": aufgabe_id},
                headers={"Authorization": f"Bearer {_token(me)}"},
            )
        antwort.raise_for_status()
        entfernt = antwort.json().get("entfernt", 0)
        if entfernt:
            log.info("notizen.verknuepfung_entfernt", anzahl=entfernt)
    except (httpx.HTTPError, ValueError) as exc:
        log.warning("notizen.nicht_abgeraeumt", fehler=repr(exc)[:200])


def vormerken(hintergrund: BackgroundTasks, me: Me, aufgabe_id: str) -> None:
    hintergrund.add_task(_abraeumen, me, aufgabe_id)
