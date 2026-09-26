"""Zugriffsprotokoll entrauschen: erfolgreiche Health-Pruefungen nicht mitschreiben.

Docker prueft alle 30 s. Das sind rund 2880 Zeilen pro Tag und Dienst, und sie
verdraengen alles andere. Gemessen am 27.08.2026 ueber die Saganta-Backends:
98 bis 100 % aller Protokollzeilen waren genau diese Abrufe (assets-api: 53.062
von 53.094; projectdeck-api und auth-proxy je 15.685 von 15.694). Ein echtes
Betriebsereignis war darin nicht mehr auffindbar, und bei der eingestellten
Rotation (3 x 50 MB) draengt das Rauschen es zusaetzlich aus dem Fenster.

★ Diese Datei lag bis zum 02.09.2026 als identische Kopie in jedem Dienst, mit
der Begruendung, eine echte Kopie mit Abgleich sei ehrlicher als eine geteilte
Schicht, von der niemand merkt, dass sie nicht greift. Der Abgleich verglich
aber die Quellbaeume, nicht die laufenden Dienste, und uebersah damit genau den
Fall, der eintrat: am 30.08. war der Filter seit drei Tagen in allen acht
Baeumen und wirkte in genau einem Dienst, weil nur der seither neu gebaut
worden war. Ein geteiltes Paket macht daraus eine Frage, die man am Image
stellen kann, statt an acht Dateien.
"""
from __future__ import annotations

import logging

GESUNDHEITSPFADE = ("/healthz", "/health")


class NurUnauffaelligeGesundheitspruefungen(logging.Filter):
    """Laesst alles durch, ausser erfolgreichen Abrufen der Health-Endpunkte.

    ★ Bewusst nur 2xx. Eine *fehlschlagende* Pruefung ist die eine Zeile, auf die
    es ankommt; ein Filter auf den blossen Pfad haette genau sie verschluckt und
    aus einem stillen Dienst einen scheinbar gesunden gemacht.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        # uvicorn.access fuellt args mit (client, methode, pfad, http_version,
        # status). Sieht der Datensatz anders aus, wird er durchgelassen: ein
        # geaendertes uvicorn bringt damit hoechstens das alte Rauschen zurueck,
        # niemals eine verlorene Fehlermeldung.
        if not isinstance(args, tuple) or len(args) < 5:
            return True
        pfad, status = args[2], args[4]
        if not isinstance(pfad, str):
            return True
        try:
            status = int(status)
        except (TypeError, ValueError):
            return True
        return not (pfad.split("?", 1)[0] in GESUNDHEITSPFADE and 200 <= status < 300)


def einrichten() -> None:
    """Haengt den Filter an uvicorns Zugriffs-Logger.

    Aufruf beim Import von ``app.main``, also nachdem uvicorn sein Logging
    eingerichtet hat (``Config.__init__`` konfiguriert das Logging, erst
    ``Config.load()`` importiert die App). ``logging.config.dictConfig`` entfernt
    beim Konfigurieren bestehende *Handler*, aber keine *Filter*.
    """
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, NurUnauffaelligeGesundheitspruefungen) for f in logger.filters):
        logger.addFilter(NurUnauffaelligeGesundheitspruefungen())
