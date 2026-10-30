"""Der Health-Filter darf leise sein, aber nie taub.

Die Gefahr bei einem Filter dieser Art ist nicht, dass er zu wenig wegnimmt,
sondern dass er zu viel wegnimmt: verschluckt er auch die *fehlschlagenden*
Prüfungen, sieht ein sterbender Dienst im Protokoll aus wie ein stiller
gesunder. Deshalb prüfen die Tests beide Richtungen.
"""
import logging
import unittest

from saganta_dienst.zugriffslog import (
    NurUnauffaelligeGesundheitspruefungen,
    einrichten,
)


def _zugriff(pfad: str, status: int) -> logging.LogRecord:
    """Baut einen Datensatz so, wie uvicorn.access ihn erzeugt."""
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:1234", "GET", pfad, "1.1", status),
        exc_info=None,
    )


class TestFilter(unittest.TestCase):
    def setUp(self):
        self.filter = NurUnauffaelligeGesundheitspruefungen()

    def test_gesunde_pruefung_wird_unterdrueckt(self):
        for pfad in ("/healthz", "/health", "/healthz?ausfuehrlich=1"):
            for status in (200, 204):
                with self.subTest(pfad=pfad, status=status):
                    self.assertFalse(self.filter.filter(_zugriff(pfad, status)))

    def test_fehlgeschlagene_pruefung_bleibt_sichtbar(self):
        """Der eigentliche Zweck des Tests, hier verstummt sonst der Alarm."""
        for status in (400, 404, 500, 502, 503):
            with self.subTest(status=status):
                self.assertTrue(
                    self.filter.filter(_zugriff("/healthz", status)),
                    f"HTTP {status} auf /healthz darf nicht gefiltert werden",
                )

    def test_normale_zugriffe_bleiben(self):
        for pfad in ("/api/news", "/metrics", "/", "/health-report", "/healthzz"):
            with self.subTest(pfad=pfad):
                self.assertTrue(self.filter.filter(_zugriff(pfad, 200)))

    def test_unerwarteter_datensatz_wird_durchgelassen(self):
        """Fail-open: ein geändertes uvicorn bringt Rauschen zurück, nie Stille."""
        for args in (None, (), ("nur", "drei", "teile"), ("a", "b", 42, "d", "e")):
            with self.subTest(args=args):
                r = _zugriff("/healthz", 200)
                r.args = args
                self.assertTrue(self.filter.filter(r))


class TestEinrichten(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("uvicorn.access")
        self._vorher = list(self.logger.filters)

    def tearDown(self):
        self.logger.filters = self._vorher

    def test_haengt_den_filter_an_und_zwar_genau_einmal(self):
        einrichten()
        einrichten()
        einrichten()
        passende = [
            f for f in self.logger.filters
            if isinstance(f, NurUnauffaelligeGesundheitspruefungen)
        ]
        self.assertEqual(len(passende), 1, "einrichten() muss idempotent sein")


if __name__ == "__main__":
    unittest.main()
