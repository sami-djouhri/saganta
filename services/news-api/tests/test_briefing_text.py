"""Der Sprech-Text des Briefings darf keine langen Gedankenstriche enthalten.

Der Text entsteht jeden Morgen neu aus einem lokalen Modell. Eine Bitte im
System-Prompt ist deshalb keine Zusicherung: haelt das Modell sich einmal nicht
daran, steht der Strich im angezeigten Briefing und im vorgelesenen Audio, und
niemand sieht es, weil am naechsten Tag schon der naechste Text da ist.
Geprueft wird deshalb die Durchsetzung im Code, nicht die Formulierung im Prompt.

Die beiden Striche werden hier aus ihrem Codepoint gebaut, damit die Datei
selbst frei von ihnen bleibt.
"""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.services.briefing_assembly import _clean_narration, _ohne_gedankenstrich  # noqa: E402

LANG = chr(0x2014)   # em dash
KURZ = chr(0x2013)   # en dash


class TestOhneGedankenstrich(unittest.TestCase):
    def test_einschub_wird_zum_komma(self):
        self.assertEqual(
            _ohne_gedankenstrich(f"Heute ist frei {LANG} der Tag gehoert dir."),
            "Heute ist frei, der Tag gehoert dir.",
        )

    def test_auch_der_kurze_strich(self):
        """Ein en dash faellt sonst durch jede Pruefung, die nur auf em dash schaut."""
        self.assertEqual(
            _ohne_gedankenstrich(f"Zwei Termine {KURZ} beide vormittags."),
            "Zwei Termine, beide vormittags.",
        )

    def test_ohne_leerzeichen_geschrieben(self):
        self.assertEqual(
            _ohne_gedankenstrich(f"Regen{LANG}den ganzen Tag."),
            "Regen, den ganzen Tag.",
        )

    def test_kein_doppeltes_satzzeichen(self):
        """Steht der Strich vor einem Satzzeichen, darf kein Komma davor entstehen."""
        self.assertEqual(_ohne_gedankenstrich(f"Das war es {LANG}."), "Das war es.")

    def test_normaler_bindestrich_bleibt(self):
        satz = "Der Nord-Sued-Verkehr laeuft wieder."
        self.assertEqual(_ohne_gedankenstrich(satz), satz)

    def test_minuszeichen_in_temperatur_bleibt(self):
        satz = "Nachts -3 bis 0 Grad."
        self.assertEqual(_ohne_gedankenstrich(satz), satz)


class TestCleanNarration(unittest.TestCase):
    def test_ganzer_text_bleibt_strichfrei(self):
        roh = (
            f"Guten Morgen. Hier ist dein Briefing {LANG} kurz und knapp.\n"
            f"- Erste Meldung {KURZ} mit Nachtrag.\n"
        )
        sauber = _clean_narration(roh)
        self.assertNotIn(LANG, sauber)
        self.assertNotIn(KURZ, sauber)
        self.assertIn("Erste Meldung, mit Nachtrag.", sauber)


if __name__ == "__main__":
    unittest.main()
