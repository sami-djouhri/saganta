"""Die Nachbardienste der Projektakte (2026-11-15).

Die Akte zeigt, was einem Projekt gehoert, haelt davon aber nichts selbst:
Termine liegen im Kalender, Kontakte in Saganta Kontakte, Notizen in Saganta
Notizen, Buchungen in Finanzen. Jeder Aufruf hier ist **fail-soft**: faellt ein
Dienst aus, kommt ``None`` zurueck, und die Akte sagt „nicht erreichbar" statt
„keine Termine" zu behaupten (dieselbe Unterscheidung wie in
``aufgaben_dienst.offene_je_projekt``).

Die Saganta-Dienste bekommen je Aufruf ein 60-s-Token mit ihrer Zielgruppe
und dem ``sub`` des Aufrufers, gestempelt mit demselben Schluessel, mit dem
dieser Dienst prueft (Muster ``aufgaben_dienst._token``). Finanzen kennt keine
Saganta-Konten; dort gilt ein Nur-Lese-Schluessel, der allein die zwei
Projekt-Routen oeffnet. Er wird nur fuer die Konten in ``allowed_subs``
benutzt, damit ein zweites Saganta-Konto nicht das Buch des Owners liest.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from jose import jwt

from .auth import Me
from .config import settings

logger = logging.getLogger("projectdeck.nachbarn")


def _token(me: Me, zielgruppe: str) -> str:
    jetzt = int(time.time())
    return jwt.encode(
        {"iss": "saganta", "sub": me.sub, "email": me.email, "aud": zielgruppe,
         "iat": jetzt, "exp": jetzt + 60},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _hole(basis: str, pfad: str, kopf: dict[str, str], params: dict | None = None) -> Any | None:
    try:
        with httpx.Client(base_url=basis, timeout=settings.nachbar_timeout_seconds) as klient:
            antwort = klient.get(pfad, headers=kopf, params=params)
    except httpx.HTTPError as exc:
        logger.warning("Nachbar %s%s nicht erreichbar: %s", basis, pfad, exc)
        return None
    if antwort.status_code >= 400:
        logger.warning("Nachbar %s%s antwortet %s", basis, pfad, antwort.status_code)
        return None
    return antwort.json() if antwort.content else None


def termine(me: Me, slugs: list[str], von: str, bis: str) -> list[dict] | None:
    """Termine der Projekte im Zeitraum (Serien als Vorkommen), ueber den kalender-bff."""
    if not slugs:
        return []
    antwort = _hole(
        settings.kalender_bff_url, "/api/events/range",
        {"Authorization": f"Bearer {_token(me, 'kalender-bff')}"},
        {"start": von, "end": bis, "projekt": ",".join(slugs)},
    )
    return None if antwort is None else list(antwort.get("items") or [])


def kontakt(me: Me, kontakt_id: str) -> dict | None | bool:
    """Ein Kontakt; ``False`` heisst „gibt es nicht (mehr)", ``None`` „Dienst weg"."""
    try:
        with httpx.Client(base_url=settings.kontakte_api_url,
                          timeout=settings.nachbar_timeout_seconds) as klient:
            antwort = klient.get(
                f"/api/kontakte/{kontakt_id}",
                headers={"Authorization": f"Bearer {_token(me, 'kontakte-api')}"})
    except httpx.HTTPError as exc:
        logger.warning("kontakte-api nicht erreichbar: %s", exc)
        return None
    if antwort.status_code == 404:
        return False
    if antwort.status_code >= 400:
        return None
    return antwort.json()


def kontakte_suche(me: Me, suche: str | None) -> list[dict] | None:
    """Kontakte zum Anheften: nur Kennung, Name und Gruppe, nichts sonst."""
    antwort = _hole(
        settings.kontakte_api_url, "/api/kontakte",
        {"Authorization": f"Bearer {_token(me, 'kontakte-api')}"},
        {"suche": suche} if suche else None,
    )
    if antwort is None:
        return None
    return [{"id": k["id"], "name": k["name"], "gruppe": k.get("gruppe")}
            for k in antwort.get("kontakte") or []]


def notizen_zu(me: Me, typ: str, refs: list[str]) -> dict[str, list[dict]] | None:
    """Notizen zu mehreren Gegenstuecken in einem Aufruf (``/api/notizen/verknuepft``)."""
    if not refs:
        return {}
    ergebnis: dict[str, list[dict]] = {}
    for anfang in range(0, len(refs), 200):
        teil = _hole(
            settings.notizen_api_url, "/api/notizen/verknuepft",
            {"Authorization": f"Bearer {_token(me, 'notizen-api')}"},
            {"typ": typ, "refs": ",".join(refs[anfang:anfang + 200])},
        )
        if teil is None:
            return None
        ergebnis.update(teil)
    return ergebnis


def budget_erlaubt(me: Me) -> bool:
    return bool(settings.finanzen_leseschluessel) and (
        not settings.allowed_subs or me.sub in settings.allowed_subs)


def budgets(me: Me) -> dict[str, dict] | None:
    """Stand je Projekt-Slug aus Finanzen; ``None`` ohne Schluessel oder bei Ausfall."""
    if not budget_erlaubt(me):
        return None
    antwort = _hole(settings.finanzen_url, "/api/projekte",
                    {"X-Projekt-Lesen": settings.finanzen_leseschluessel})
    if antwort is None:
        return None
    return {e["projekt"]: e for e in antwort if isinstance(e, dict) and e.get("projekt")}


def budget_stand(me: Me, slug: str) -> dict | None:
    if not budget_erlaubt(me):
        return None
    return _hole(settings.finanzen_url, f"/api/projekte/{slug}/stand",
                 {"X-Projekt-Lesen": settings.finanzen_leseschluessel})
