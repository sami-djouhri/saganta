"""Freemium-Tarife des Briefing-Produkts.

★ Seit dem 02.09.2026 steht hier keine eigene Tabelle mehr. Die Tarife gelten
suite-weit und liegen in ``saganta_dienst.tarife``, weil der Tarif zum Konto
gehoert und nicht zum Briefing: solange er nur hier definiert war, konnte kein
anderes Backend ihn pruefen.

Dieses Modul bleibt als Uebersetzungsschicht bestehen, damit der bestehende
news-api-Code (``plans.features(...)["audio"]``) unveraendert weiterlaeuft. Es
haelt die Briefing-Namen der Merkmale auf die suite-weiten Schluessel.
"""
from __future__ import annotations

from saganta_dienst import tarife

FREE = tarife.FREI
PRO = tarife.PRO

PRO_BENEFITS = tarife.PRO_VORTEILE

# Briefing-Name -> suite-weiter Schluessel. Die linke Seite ist das, was der
# vorhandene Code und die Oberflaeche kennen.
_UEBERSETZUNG = {
    "max_length": "briefing.max_laenge",
    "audio": "briefing.audio",
    "premium_voice": "briefing.premium_stimme",
    "webhook": "briefing.webhook",
    "custom_topics": "briefing.eigene_themen",
}


def features(plan: str | None) -> dict:
    """Die Briefing-Merkmale eines Tarifs, unter ihren bisherigen Namen."""
    quelle = tarife.merkmale(plan)
    ergebnis: dict = {"label": quelle["etikett"]}
    for name, schluessel in _UEBERSETZUNG.items():
        ergebnis[name] = quelle[schluessel]
    return ergebnis


def clamp_length(plan: str | None, length: str) -> str:
    """Begrenzt die gewuenschte Laenge auf das im Tarif Erlaubte."""
    return tarife.stutze_laenge(plan, length)
