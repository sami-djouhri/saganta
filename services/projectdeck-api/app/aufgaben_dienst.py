"""Der Weg zum Aufgaben-Dienst, im Namen des Aufrufers.

Seit der sechsten Fragerunde (04.11., `docs/RICHTUNG.md`) gehoeren Aufgaben
`aufgaben-api`. Das ProjectDeck zeigt die Aufgaben eines Projekts, legt an und
hakt ab, **ohne eigene Kopie**. Eine Aufgabe nennt ihr Projekt ueber dessen
Slug (wie die Notizen); der Slug ist nach dem Anlegen nicht aenderbar.

Das Token stempelt dieser Dienst selbst, mit `aud=aufgaben-api` und dem
`sub` des Aufrufers, 60 Sekunden gueltig, dasselbe Muster wie
`aufgaben-api/app/kalender.py`. Der `sub` kommt ausschliesslich aus dem schon
geprueften Token der Anfrage.
"""
from __future__ import annotations

import time
from datetime import date
from types import SimpleNamespace
from typing import Any

import httpx
from jose import jwt

from .auth import Me
from .config import settings

ZIELGRUPPE = "aufgaben-api"


class AufgabenNichtErreichbar(Exception):
    """Netz, Zeitueberschreitung oder 5xx."""


def _token(me: Me) -> str:
    jetzt = int(time.time())
    return jwt.encode(
        {"iss": "saganta", "sub": me.sub, "email": me.email, "aud": ZIELGRUPPE,
         "iat": jetzt, "exp": jetzt + 60},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def aufruf(me: Me, methode: str, pfad: str, **kw: Any) -> Any:
    """Ein Aufruf am Aufgaben-Dienst. Wirft bei 4xx ``httpx.HTTPStatusError``."""
    try:
        with httpx.Client(base_url=settings.aufgaben_api_url,
                          timeout=settings.aufgaben_timeout_seconds) as klient:
            antwort = klient.request(
                methode, pfad, headers={"Authorization": f"Bearer {_token(me)}"}, **kw)
    except httpx.HTTPError as exc:
        raise AufgabenNichtErreichbar(str(exc)) from exc
    if antwort.status_code >= 500:
        raise AufgabenNichtErreichbar(f"aufgaben-api {antwort.status_code}")
    antwort.raise_for_status()
    return antwort.json() if antwort.content else None


def _datum(wert: str | None) -> date | None:
    return date.fromisoformat(wert) if wert else None


def als_task(aufgabe: dict) -> SimpleNamespace:
    """Eine Aufgabe des Dienstes in der Form, die Risiko und Befunde lesen.

    Nur die Felder, die `deadline_risk` und `rules` anfassen. Planbar ist,
    was nicht wartet: der Planer des Dienstes ueberspringt Wartende auch.
    """
    return SimpleNamespace(
        status="done" if aufgabe.get("erledigt") else "open",
        can_schedule=not aufgabe.get("wartet"),
        remaining_minutes=None,
        estimated_minutes=aufgabe.get("dauer_min"),
        deadline=_datum(aufgabe.get("faellig")),
    )


def offene_je_projekt(me: Me) -> dict[str, list[SimpleNamespace]] | None:
    """Offene Aufgaben nach Projekt-Slug, ``None`` wenn der Dienst nicht antwortet.

    ``None`` und ``{}`` sind zwei Antworten: „weiss nicht" und „keine".
    Wer beide gleich behandelt, meldet bei einem Ausfall fuer jedes Projekt mit
    Frist „kein planbarer Task" (fail-soft heisst hier: nichts behaupten).
    """
    try:
        alle = aufruf(me, "GET", "/api/aufgaben") or []
    except (AufgabenNichtErreichbar, httpx.HTTPStatusError):
        return None
    je: dict[str, list[SimpleNamespace]] = {}
    for a in alle:
        if a.get("projekt"):
            je.setdefault(a["projekt"], []).append(als_task(a))
    return je


def zaehlung(me: Me) -> dict[str, dict[str, int]] | None:
    try:
        return aufruf(me, "GET", "/api/projekte/zaehlung") or {}
    except (AufgabenNichtErreichbar, httpx.HTTPStatusError):
        return None


# --- Was Risiko, Befunde und KI-Begruendung lesen --------------------------
#
# Beide liefern ``(aufgaben, unbekannt)``. ``project_tasks`` liest seit dem
# Umzug niemand mehr; die Tabelle bleibt als Archiv stehen.


def quelle_alle(me: Me) -> tuple[dict[str, list[SimpleNamespace]], bool]:
    je = offene_je_projekt(me)
    return (je or {}), je is None


def quelle_projekt(me: Me, slug: str) -> tuple[list[SimpleNamespace], bool]:
    try:
        roh = aufruf(me, "GET", "/api/aufgaben", params={"projekt": slug}) or []
    except (AufgabenNichtErreichbar, httpx.HTTPStatusError):
        return [], True
    return [als_task(a) for a in roh], False
