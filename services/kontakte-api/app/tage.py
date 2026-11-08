"""Geburtstage und Jahrestage: naechster Termin, Zahl, Spiegelzeilen.

Dieselbe Regel wie ``kalender/backend/birthday_utils.py``: der 29. Februar
faellt in Nicht-Schaltjahren auf den 28.
"""
from __future__ import annotations

import calendar
import uuid
from datetime import date

from .models import Kontakt

#: Fester Namensraum fuer die Kennungen der Jahrestags-Spiegelzeilen. Eine
#: zufaellige Kennung je Abgleich gaebe dem Kalender bei jeder Aenderung neue
#: Zeilen, und seine Erinnerungs-Merker (``<id>:<datum>:<vorlauf>``) griffen
#: nicht mehr: dieselbe Erinnerung kaeme ein zweites Mal.
_NAMENSRAUM = uuid.UUID("6f1d0c52-6a2e-4f53-9d0e-4b6b1f3a7c21")


def im_jahr(tag: date, jahr: int) -> date:
    if tag.month == 2 and tag.day == 29 and not calendar.isleap(jahr):
        return date(jahr, 2, 28)
    return date(jahr, tag.month, tag.day)


def naechster(tag: date, ab: date) -> date:
    kandidat = im_jahr(tag, ab.year)
    if kandidat < ab:
        kandidat = im_jahr(tag, ab.year + 1)
    return kandidat


def jahrestag_kennung(kontakt_id: str, bezeichnung: str, datum: str) -> str:
    return str(uuid.uuid5(_NAMENSRAUM, f"{kontakt_id}|{bezeichnung}|{datum}"))


def jahrestag_name(kontakt: Kontakt, bezeichnung: str) -> str:
    return f"{bezeichnung} {kontakt.name}"[:200]


def tage_von(kontakt: Kontakt) -> list[tuple[str, str, date]]:
    """``(art, bezeichnung, datum)`` je Tag des Kontakts."""
    tage: list[tuple[str, str, date]] = []
    if kontakt.geburtstag:
        tage.append(("geburtstag", "Geburtstag", kontakt.geburtstag))
    for j in kontakt.jahrestage or []:
        try:
            tage.append(("jahrestag", j["bezeichnung"], date.fromisoformat(j["datum"])))
        except (KeyError, TypeError, ValueError):
            continue
    return tage


def spiegelzeilen(kontakte: list[Kontakt]) -> list[dict]:
    """Was der Kalender bekommt: eine Zeile je Geburtstag oder Jahrestag.

    Der Geburtstag traegt die Kennung des Kontakts, wie vor dem Umzug im
    Kalender. Damit bleiben dort gesetzte Erinnerungs-Merker gueltig.
    """
    zeilen: list[dict] = []
    for k in kontakte:
        for art, bezeichnung, datum in tage_von(k):
            if art == "geburtstag":
                zeilen.append({"id": k.id, "name": k.name, "birthday": datum.isoformat(),
                               "art": "geburtstag"})
            else:
                zeilen.append({
                    "id": jahrestag_kennung(k.id, bezeichnung, datum.isoformat()),
                    "name": jahrestag_name(k, bezeichnung),
                    "birthday": datum.isoformat(),
                    "art": "jahrestag",
                })
    return zeilen
