"""Datumsangaben aus dem Zugriffsprotokoll nehmen.

Uvicorn protokolliert jede Anfrage samt Pfad und Query-String. Die Adressen
dieses Dienstes tragen das Datum (``/api/eintraege/2026-09-06``), und daraus
liesse sich lueckenlos rekonstruieren, an welchen Tagen jemand geschrieben,
gelesen oder geloescht hat. Der Inhalt bliebe verschlossen, das Muster nicht.

Das ist hier kein Randfall, sondern der Regelfall, denn die Protokolle bleiben
nicht auf dem Wirt: ``promtail`` sammelt per ``docker_sd_configs`` die Ausgabe
**aller** Container nach Loki, und dessen Volume liegt in der Off-Site-Sicherung
(``docker/monitoring/promtail/promtail-config.yml``). Genau diese Kette hat den
``feed_token`` des Kalenders in 509 von 644 Protokollzeilen ins Backup getragen,
bis es 2026-08-25 auffiel.

Vorbild und Begruendung im Detail: ``docker/kalender/backend/zugriffsprotokoll.py``.
Von dort stammen auch die beiden Entwurfsentscheidungen:

★ **Der Feldname bleibt stehen, nur der Wert geht.** Aus
  ``/api/eintraege/2026-09-06`` wird ``/api/eintraege/<datum>``. Man sieht
  weiterhin, welche Route gerufen wurde und mit welchem Ergebnis, also bleibt
  das Protokoll fuer den Betrieb brauchbar. Ein gekuerztes Praefix des Datums
  waere ausdruecklich kein Kompromiss, sondern nur ein kleinerer Verrat.

★ **Der Filter haengt am Logger, nicht am Handler.** ``logging.config.dictConfig``
  entfernt beim Konfigurieren die Handler eines Loggers, aber nicht dessen
  Filter. So ueberlebt er ein erneutes ``uvicorn.Config.configure_logging()``.

``--no-access-log`` waere der falsche Tausch. Stille hat hier schon einmal einen
Ausfall verdeckt, und ein Dienst, der gar nichts mehr sagt, ist nicht sicherer,
sondern nur unbeobachtet.
"""
from __future__ import annotations

import logging
import re

#: ISO-Datum an jeder Stelle des Pfades oder der Query.
_DATUM = re.compile(r"\d{4}-\d{2}-\d{2}")
#: Jahres- und Monatsangaben als Query-Wert (``?jahr=2026``, ``?monat=2026-09``
#: faengt bereits die Datumsregel oben). Ohne diese Zeile bliebe die Jahreszahl
#: stehen, was allein harmlos ist, in Verbindung mit der Trefferzahl der
#: Uebersichtsroute aber wieder ein Muster ergibt.
_JAHR = re.compile(r"(?<=[?&])(jahr|von|bis)=[^&\s]*")


def maskiere(pfad: str) -> str:
    """Ersetzt Datumsangaben in einem Pfad samt Query.

    Reine Funktion, damit sie ohne Logging-Aufbau geprueft werden kann.
    """
    ohne_datum = _DATUM.sub("<datum>", pfad)
    return _JAHR.sub(lambda t: f"{t.group(1)}=<wert>", ohne_datum)


class OhneDatumsangaben(logging.Filter):
    """Nimmt Datumsangaben aus der Zugriffszeile, laesst alles andere stehen.

    Gibt immer ``True`` zurueck: dieser Filter verwirft nichts, er schreibt um.
    Das Entrauschen der Health-Pruefungen macht ein zweiter, geteilter Filter
    (``saganta_dienst.zugriffslog``), und beide haengen nebeneinander am selben
    Logger.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn.access fuellt args mit (client, methode, pfad, http_version,
        # status). Sieht der Datensatz anders aus, wird er unveraendert
        # durchgelassen. Ein geaendertes uvicorn faellt damit auf, statt still
        # eine halb maskierte Zeile zu schreiben.
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        pfad = args[2]
        if not isinstance(pfad, str):
            return True
        maskiert = maskiere(pfad)
        if maskiert != pfad:
            record.args = args[:2] + (maskiert,) + args[3:]
        return True


def einrichten() -> None:
    """Haengt den Filter an uvicorns Zugriffs-Logger.

    Aufruf beim Import von ``app.main``, also nachdem uvicorn sein Logging
    eingerichtet hat (``Config.__init__`` konfiguriert das Logging, erst
    ``Config.load()`` importiert die App).
    """
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, OhneDatumsangaben) for f in logger.filters):
        logger.addFilter(OhneDatumsangaben())
