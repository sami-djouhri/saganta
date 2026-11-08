"""Die Kostenbremse des Briefings, unter den Namen, die news-api kennt.

Seit dem 05.11.2026 heisst das hier Kostenbremse und nicht Tarif
(RICHTUNG.md, dritte Runde: „es geht um Rechenzeit, nicht um Tarife"). Die
gespeicherten Werte bleiben ``free`` und ``pro``, denn sie liegen in der
auth-DB (``user.plan``) und reisen im JWT-Claim ``plan`` durch alle Dienste;
ein Umbenennen dort waere ein Umbau der Anmeldekette fuer ein Wort. Neu sind
nur die Namen, die jemand liest: ``begrenzt`` und ``voll``.

Was ein Wert bedeutet, steht weiter in ``saganta_dienst.tarife``.

Seit dem 02.09.2026 steht hier keine eigene Tabelle mehr. Die Tarife gelten
suite-weit und liegen in ``saganta_dienst.tarife``, weil der Tarif zum Konto
gehoert und nicht zum Briefing: solange er nur hier definiert war, konnte kein
anderes Backend ihn pruefen.

Dieses Modul bleibt als Uebersetzungsschicht bestehen, damit der bestehende
news-api-Code (``plans.features(...)["audio"]``) unveraendert weiterlaeuft. Es
haelt die Briefing-Namen der Merkmale auf die suite-weiten Schluessel.
"""
from __future__ import annotations

from saganta_dienst import tarife

BEGRENZT = tarife.FREI
VOLL = tarife.PRO

#: Was die volle Rechenzeit zusaetzlich bringt, fuer die Oberflaeche. Eigene
#: Liste statt ``tarife.PRO_VORTEILE``: dort steht auch „Prioritaets-Generierung",
#: und die setzt kein Dienst durch. Ein Merkmal ohne Durchsetzung ist ein
#: Versprechen, das niemand haelt.
VOLLER_UMFANG = [
    "Gesprochenes Briefing (Sprachsynthese)",
    "Redigierte Sprech-Fassung statt des festen Textes",
    "Laenge: lang",
    "Eigene Themen-Stichwoerter",
    "Zustellung an das Smart Home (Webhook)",
]

_ETIKETT = {BEGRENZT: "begrenzt", VOLL: "voll"}

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
    """Die Briefing-Merkmale einer Kostenbremse, unter ihren bisherigen Namen."""
    quelle = tarife.merkmale(plan)
    ergebnis: dict = {"label": _ETIKETT[tarife.normalisiere(plan)]}
    for name, schluessel in _UEBERSETZUNG.items():
        ergebnis[name] = quelle[schluessel]
    return ergebnis


def clamp_length(plan: str | None, length: str) -> str:
    """Begrenzt die gewuenschte Laenge auf das unter der Kostenbremse Erlaubte."""
    return tarife.stutze_laenge(plan, length)
