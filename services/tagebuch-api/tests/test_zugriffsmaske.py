"""Jeder Test prueft beide Richtungen: das Geheimnis ist weg UND es wird
weiterhin etwas Brauchbares protokolliert. Ein Filter, der alles verschluckt,
bestuende sonst die halbe Pruefung und machte aus einem stillen Dienst einen
scheinbar gesunden.
"""

import logging

from app.zugriffsmaske import OhneDatumsangaben, einrichten, maskiere


class TestMaskiere:
    def test_datum_im_pfad_verschwindet(self):
        assert maskiere("/api/eintraege/2026-09-06") == "/api/eintraege/<datum>"

    def test_die_route_bleibt_erkennbar(self):
        """Die Gegenrichtung: man muss weiterhin sehen, was gerufen wurde."""
        assert "api/eintraege" in maskiere("/api/eintraege/2026-09-06")

    def test_mehrere_daten_in_einer_query(self):
        ergebnis = maskiere("/api/eintraege?von=2026-01-01&bis=2026-12-31")
        assert "2026" not in ergebnis
        assert ergebnis.startswith("/api/eintraege?")

    def test_jahr_als_query_wert(self):
        assert maskiere("/api/eintraege/tage?jahr=2026") == "/api/eintraege/tage?jahr=<wert>"

    def test_pfade_ohne_datum_bleiben_unveraendert(self):
        for pfad in ("/healthz", "/api/tresor", "/metrics", "/api/tresor/passphrase"):
            assert maskiere(pfad) == pfad


class TestFilter:
    def _datensatz(self, pfad: str, status: int = 200) -> logging.LogRecord:
        satz = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg='%s - "%s %s HTTP/%s" %d',
            args=("1.2.3.4:5", "GET", pfad, "1.1", status),
            exc_info=None,
        )
        return satz

    def test_filter_schreibt_um_und_verwirft_nicht(self):
        satz = self._datensatz("/api/eintraege/2026-09-06")
        assert OhneDatumsangaben().filter(satz) is True
        assert satz.args[2] == "/api/eintraege/<datum>"
        # Der Rest der Zeile bleibt vollstaendig: Methode und Status tragen die
        # Betriebsinformation.
        assert satz.args[1] == "GET"
        assert satz.args[4] == 200

    def test_fehlerzeilen_bleiben_erhalten(self):
        satz = self._datensatz("/api/eintraege/2026-09-06", status=500)
        assert OhneDatumsangaben().filter(satz) is True
        assert satz.args[4] == 500

    def test_fremd_geformte_datensaetze_gehen_unveraendert_durch(self):
        """Ein geaendertes uvicorn bringt hoechstens das alte Rauschen zurueck,
        niemals eine verlorene Zeile."""
        satz = logging.LogRecord(
            name="uvicorn.access",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="etwas ganz anderes",
            args=None,
            exc_info=None,
        )
        assert OhneDatumsangaben().filter(satz) is True

    def test_einrichten_haengt_genau_einen_filter_an(self):
        logger = logging.getLogger("uvicorn.access")
        logger.filters = [f for f in logger.filters if not isinstance(f, OhneDatumsangaben)]
        einrichten()
        einrichten()
        eigene = [f for f in logger.filters if isinstance(f, OhneDatumsangaben)]
        assert len(eigene) == 1
