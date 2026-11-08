"""Eingangsschemas: ein unbekannter Feldname faellt nicht mehr wortlos weg.

Pydantics Vorgabe ``extra="ignore"`` verwirft jedes Feld, das ein Modell nicht
kennt, und die Antwort ist trotzdem 200 oder 201. Ein Tippfehler im Client
(``due_date`` statt ``target_date``) wird damit zum Datenverlust mit
Erfolgsmeldung: der Client glaubt die Aenderung uebernommen, der Server hat
getan, was dastand, und die Oberflaeche zeigt nur, was angekommen ist.
Befund und Herleitung: ``docs/FELDNAMEN_BEFUND.md``.

``extra="forbid"`` haette den Befund mit einer Zeile geschlossen, aber fuer jeden
bestehenden Client auf einmal: ein aelterer Android-Client oder ein Formular mit
Hilfsfeld bekaeme ab dann 422. Deshalb drei Zustaende, wie bei
``TENANT_HEADER_ENFORCE``, geschaltet je Dienst ueber ``SAGANTA_FREMDFELDER``:

``ignorieren``
    das alte Verhalten, ohne Protokollzeile.
``melden`` (Vorgabe)
    verhaltensneutral, schreibt aber je Anfrage eine Zeile mit Modell und
    Feldnamen. **Nie die Werte**: in den Rumpfen stehen Nutzerdaten.
``ablehnen``
    422 mit den Feldnamen. Erst schalten, wenn ``melden`` ueber eine
    Beobachtungsphase leer geblieben ist.

Ein unbekannter Wert in ``SAGANTA_FREMDFELDER`` gilt als ``melden``, nicht als
``ablehnen``: ein Tippfehler im Schalter selbst soll keinen Dienst kappen.

Der Zustand wird bei jeder Pruefung gelesen, nicht beim Import. Das kostet einen
``os.environ``-Zugriff und erlaubt den Tests, ihn je Fall umzustellen.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

SCHALTER = "SAGANTA_FREMDFELDER"
ZUSTAENDE = ("ignorieren", "melden", "ablehnen")
VORGABE = "melden"

# uvicorn.error ist der Logger, an dem in diesen Diensten ein Handler haengt;
# ein eigener Name ginge ueber den lastResort-Handler ohne Zeitstempel hinaus.
log = logging.getLogger("uvicorn.error")

# Feldnamen kommen vom Client. Gekuerzt und gezaehlt, damit ein boeswilliger
# Rumpf mit tausend langen Schluesseln das Protokoll nicht fluten kann.
_HOECHSTENS_NAMEN = 20
_HOECHSTENS_ZEICHEN = 60


def zustand() -> str:
    wert = os.environ.get(SCHALTER, VORGABE).strip().lower()
    return wert if wert in ZUSTAENDE else VORGABE


def _bekannte_namen(modell: type[BaseModel]) -> set[str]:
    namen: set[str] = set()
    for name, feld in modell.model_fields.items():
        namen.add(name)
        if feld.alias:
            namen.add(feld.alias)
    return namen


def _darstellen(fremd: list[str]) -> str:
    gezeigt = [repr(n[:_HOECHSTENS_ZEICHEN]) for n in fremd[:_HOECHSTENS_NAMEN]]
    rest = len(fremd) - len(gezeigt)
    return ", ".join(gezeigt) + (f" und {rest} weitere" if rest > 0 else "")


class Eingang(BaseModel):
    """Vorfahr fuer alle Eingangsschemas (``*In``, ``*Patch``, ``*An``).

    ``extra`` bleibt ``ignore``: das Verwerfen selbst entscheidet der Validator
    nach ``SAGANTA_FREMDFELDER``, nicht die Modellkonfiguration. Wer in einer
    Unterklasse ``extra="forbid"`` setzt, schaltet sie damit unabhaengig vom
    Schalter scharf.
    """

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def _fremdfelder_pruefen(cls, daten: Any) -> Any:
        if not isinstance(daten, dict):
            return daten
        bekannt = _bekannte_namen(cls)
        fremd = sorted(str(k) for k in daten if k not in bekannt)
        if not fremd:
            return daten
        z = zustand()
        if z == "ignorieren":
            return daten
        log.warning("Fremdfelder in %s (%s): %s", cls.__name__, z, _darstellen(fremd))
        if z == "ablehnen":
            raise ValueError(f"unbekannte Felder: {_darstellen(fremd)}")
        return daten
