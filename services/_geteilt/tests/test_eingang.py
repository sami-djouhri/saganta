"""Ein unbekannter Feldname darf nicht mehr wortlos wegfallen.

Geprueft werden alle drei Zustaende des Schalters und die zwei Dinge, die bei
einer Meldezeile schiefgehen koennen: dass ein Wert ins Protokoll geraet, und
dass ein boeswilliger Rumpf das Protokoll flutet.
"""
import logging
import os
import unittest

from pydantic import Field, ValidationError

from saganta_dienst.eingang import SCHALTER, Eingang


class Beispiel(Eingang):
    titel: str | None = None
    zieldatum: str | None = Field(None, alias="target_date")


class Grund(unittest.TestCase):
    def setUp(self):
        self._alt = os.environ.get(SCHALTER)

    def tearDown(self):
        if self._alt is None:
            os.environ.pop(SCHALTER, None)
        else:
            os.environ[SCHALTER] = self._alt

    def schalten(self, wert):
        if wert is None:
            os.environ.pop(SCHALTER, None)
        else:
            os.environ[SCHALTER] = wert


class TestZustaende(Grund):
    def test_vorgabe_meldet_und_nimmt_an(self):
        self.schalten(None)
        with self.assertLogs("uvicorn.error", level="WARNING") as log:
            m = Beispiel.model_validate({"titel": "a", "due_date": "geheim-2026"})
        self.assertEqual(m.titel, "a")
        zeile = "\n".join(log.output)
        self.assertIn("Beispiel", zeile)
        self.assertIn("due_date", zeile)
        # Positivkontrolle gegen das eigentliche Risiko: der Wert bleibt draussen.
        self.assertNotIn("geheim-2026", zeile)

    def test_ablehnen_wirft_mit_feldnamen(self):
        self.schalten("ablehnen")
        with self.assertLogs("uvicorn.error", level="WARNING"):
            with self.assertRaises(ValidationError) as fehler:
                Beispiel.model_validate({"titel": "a", "due_date": "x"})
        self.assertIn("due_date", str(fehler.exception))

    def test_ignorieren_bleibt_still(self):
        self.schalten("ignorieren")
        with self.assertNoLogs("uvicorn.error", level="WARNING"):
            m = Beispiel.model_validate({"titel": "a", "due_date": "x"})
        self.assertEqual(m.titel, "a")

    def test_tippfehler_im_schalter_kappt_nicht(self):
        self.schalten("ablehnn")
        with self.assertLogs("uvicorn.error", level="WARNING"):
            Beispiel.model_validate({"due_date": "x"})

    def test_bekannte_felder_und_alias_bleiben_still(self):
        self.schalten("ablehnen")
        with self.assertNoLogs("uvicorn.error", level="WARNING"):
            m = Beispiel.model_validate({"titel": "a", "target_date": "2026-11-01"})
        self.assertEqual(m.zieldatum, "2026-11-01")

    def test_kein_dict_wird_durchgereicht(self):
        self.schalten("ablehnen")
        m = Beispiel.model_validate(Beispiel(titel="a"))
        self.assertEqual(m.titel, "a")


class TestUnterklasse(Grund):
    def test_unterklasse_meldet_unter_eigenem_namen(self):
        class Unter(Beispiel):
            mehr: int | None = None

        self.schalten("melden")
        with self.assertLogs("uvicorn.error", level="WARNING") as log:
            Unter.model_validate({"mehr": 1, "weniger": 2})
        zeile = "\n".join(log.output)
        self.assertIn("Unter", zeile)
        self.assertIn("weniger", zeile)
        self.assertNotIn("'mehr'", zeile)


class TestFlut(Grund):
    def test_viele_lange_namen_werden_gekappt(self):
        self.schalten("melden")
        rumpf = {f"{i:03d}" + "x" * 500: 1 for i in range(200)}
        with self.assertLogs("uvicorn.error", level="WARNING") as log:
            Beispiel.model_validate(rumpf)
        zeile = "\n".join(log.output)
        self.assertLess(len(zeile), 2000)
        self.assertIn("180 weitere", zeile)


if __name__ == "__main__":
    logging.basicConfig()
    unittest.main()
