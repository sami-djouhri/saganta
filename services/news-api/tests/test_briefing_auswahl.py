"""Auswahl und Sprech-Aufbereitung des Briefings.

Alle Faelle hier sind **gemessene** Titel aus den Briefings vom 09. bis
16.10.2026, keine erfundenen Beispiele. Das ist Absicht: die Schwellen in
`briefing_assembly` sind an genau diesem Bestand kalibriert, und ein Test mit
ausgedachten Titeln wuerde eine Verschiebung der Schwelle nicht bemerken.

Jede Gruppe hat eine Positiv- UND eine Negativkontrolle. Eine Dedup-Schwelle
ohne Gegenprobe laesst sich beliebig scharf stellen und wirft dann echte
Nachrichten weg, was im Betrieb niemandem auffaellt: es fehlt ja nur etwas.
"""
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.services.briefing_assembly import (  # noqa: E402
    _als_satz,
    _kerne,
    _ohne_eigene_nachricht,
    _titel_saeubern,
    _zu_aehnlich,
    erfundener_anteil,
)

LANG = chr(0x2014)
KURZ = chr(0x2013)


class TestTitelSaeubern(unittest.TestCase):
    def test_html_entity_wird_aufgeloest(self):
        """`&amp;` ging bis 16.10. unveraendert ins TTS."""
        self.assertEqual(
            _titel_saeubern("Das Ende von Photoshop, Word &amp; Co.?"),
            "Das Ende von Photoshop, Word & Co.?",
        )

    def test_anfuehrungszeichen_entity(self):
        self.assertEqual(
            _titel_saeubern("Ukraine legt &quot;russisches Google&quot; lahm"),
            'Ukraine legt "russisches Google" lahm',
        )

    def test_quellmarke_faellt_weg(self):
        self.assertEqual(
            _titel_saeubern("heise+ | Bit-Rauschen: EU-CPU rechnet los"),
            "Bit-Rauschen: EU-CPU rechnet los",
        )

    def test_normaler_titel_bleibt_unveraendert(self):
        satz = "Notfallmedizin unter Druck: Bundestag stimmt ueber Reform ab"
        self.assertEqual(_titel_saeubern(satz), satz)

    def test_leer_bleibt_leer(self):
        self.assertEqual(_titel_saeubern(""), "")
        self.assertEqual(_titel_saeubern(None), "")


class TestOhneEigeneNachricht(unittest.TestCase):
    def test_sendungshinweis(self):
        """Stand an fuenf von acht gemessenen Tagen im Briefing."""
        self.assertTrue(_ohne_eigene_nachricht("tagesschau 20:00 Uhr"))

    def test_sammelzeile_der_fachpresse(self):
        self.assertTrue(_ohne_eigene_nachricht(
            "Mittwoch: KI-Insolvenz nach Suizid-Klagen, KI-Vereinfachung der App-Entwicklung"
        ))

    def test_echte_meldung_bleibt(self):
        for titel in (
            "Notfallmedizin unter Druck: Bundestag stimmt ueber Reform ab",
            "Angriff auf Yandex: Ukraine legt russisches Google lahm",
            "Microsoft-President: KI wird lascher kontrolliert als Milch",
        ):
            self.assertFalse(_ohne_eigene_nachricht(titel), titel)

    def test_uhrzeit_mitten_im_titel_ist_kein_hinweis(self):
        """Nur ein Titel, der NUR aus Sendung und Uhrzeit besteht, faellt weg."""
        self.assertFalse(_ohne_eigene_nachricht(
            "Bahnstreik ab 20:00 Uhr: Was Reisende wissen muessen"
        ))


class TestDoppelungen(unittest.TestCase):
    """Die vier echten Doppelungen des Messzeitraums."""

    ECHTE_PAARE = [
        ("Notfallmedizin unter Druck: Bundestag stimmt ueber Reform ab",
         "Gesundheitspolitik - Bundestag will Reform der Notfallversorgung beschliessen"),
        ("Angriff auf Yandex: Ukraine legt russisches Google lahm",
         "Yandex: Ukrainische Drohnenangriffe legen Russlands Google lahm "
         "und der Bot-Traffic bricht ein"),
        ("Ukraine: Trump setzt Praesident Selenskyj weiter unter Druck",
         "US-Praesident - Trump: Beilegung des Ukraine-Kriegs scheitert an Selenskyj, "
         "nicht an Putin"),
        ("Erst KI-Vorzeigefirma, dann Klagewelle, jetzt Insolvenz: "
         "Character.ai sucht einen Kaeufer",
         "Einst milliardenschwer, jetzt Pleite: Gehyptes KI-Startup Character.ai "
         "muss Insolvenz anmelden"),
    ]

    # Paare, die sich ein Thema teilen und trotzdem verschiedene Nachrichten
    # sind. Sie liegen bei 0,25 und muessen unter der Schwelle bleiben.
    VERSCHIEDENE_PAARE = [
        ("Wirtschaft - Bericht: Bundesregierung vor KI-Partnerschaft mit Nvidia",
         "Mehrere US-Bundesstaaten verklagen KI-Firma OpenAI"),
        ("Mehrere US-Bundesstaaten verklagen KI-Firma OpenAI",
         "Bundestag - Fruehstart-Rente: Wie aus zehn Euro eine Altersvorsorge werden soll"),
        ("Googles Gemini-4-Modell Carbon soll mit Anthropics staerkstem "
         "Coding-Modell mithalten",
         "Anthropic zieht die Reissleine und kappt seinen KI-Modellen in Tests "
         "den Internetzugang"),
        ("EU fordert Auskunft von OpenAI und Anthropic nach KI-Angriffen",
         "KI-Sicherheit: OpenAI buesst weiter an Glaubwuerdigkeit ein"),
    ]

    def test_echte_doppelungen_werden_erkannt(self):
        for a, b in self.ECHTE_PAARE:
            self.assertTrue(
                _zu_aehnlich(_kerne(a), _kerne(b)),
                f"nicht als Doppelung erkannt:\n  {a}\n  {b}",
            )

    def test_verschiedene_nachrichten_bleiben_beide(self):
        for a, b in self.VERSCHIEDENE_PAARE:
            self.assertFalse(
                _zu_aehnlich(_kerne(a), _kerne(b)),
                f"faelschlich zusammengelegt:\n  {a}\n  {b}",
            )

    def test_komposita_werden_zusammengefuehrt(self):
        """Der Grund fuer den Praefix-Vergleich, an einem Minimalfall."""
        self.assertTrue(_zu_aehnlich(_kerne("Notfallmedizin Bundestag Reform"),
                                     _kerne("Notfallversorgung Bundestag Reform")))

    def test_leere_mengen_sind_nicht_aehnlich(self):
        self.assertFalse(_zu_aehnlich(set(), _kerne("irgendein Titel hier")))


class TestAlsSatz(unittest.TestCase):
    def test_fragezeichen_bekommt_keinen_punkt(self):
        """Am 15.10. als `replizieren?.` im Audio."""
        self.assertEqual(
            _als_satz("Koennen sich KI-Systeme selbst replizieren?"),
            "Koennen sich KI-Systeme selbst replizieren?",
        )

    def test_titel_ohne_satzzeichen_bekommt_punkt(self):
        self.assertEqual(_als_satz("Bundestag stimmt ab"), "Bundestag stimmt ab.")

    def test_ausrufezeichen_bleibt_einfach(self):
        self.assertEqual(_als_satz("Achtung Betrug!"), "Achtung Betrug!")

    def test_kaufmaennisches_und_wird_ausgeschrieben(self):
        self.assertEqual(
            _als_satz("Photoshop, Word & Co. im Test"),
            "Photoshop, Word und Co. im Test.",
        )

    def test_und_ohne_leerzeichen(self):
        self.assertEqual(_als_satz("Strom&Gas teurer"), "Strom und Gas teurer.")

    def test_leerer_titel(self):
        self.assertEqual(_als_satz(""), "")


class TestErfundenerAnteil(unittest.TestCase):
    """Die Nachmessung der Sprachfassung gegen ihr Quellenmaterial."""

    INHALT = {
        "top_items": [{
            "title": "Notfallmedizin unter Druck: Bundestag stimmt ueber Reform ab",
            "summary": "Notaufnahmen und Rettungsdienste sind seit Jahren "
                       "ueberlastet. Nun will der Bundestag eine Reform auf den "
                       "Weg bringen.",
        }],
        "sections": [],
        "day": None,
        "weather": None,
    }

    def test_treue_fassung_liegt_niedrig(self):
        """Eine Fassung, die nur umformuliert, bleibt unter der Grenze."""
        treu = ("Der Bundestag stimmt heute ueber eine Reform der Notfallmedizin ab. "
                "Notaufnahmen und Rettungsdienste sind seit Jahren ueberlastet.")
        self.assertLess(erfundener_anteil(treu, self.INHALT), 0.25)

    def test_erfundene_fassung_schlaegt_an(self):
        """Gemessener Ausschnitt der 4B-Fassung vom 15.10."""
        erfunden = ("Der Bundestag hat sich kuerzlich auf eine umfassende Reform "
                    "geeinigt, um die Versorgungsluecken zu schliessen und die "
                    "Reaktionszeiten zu verkuerzen. Gleichzeitig bleibt die Sorge "
                    "vor einer Ueberflutung von Daten bestehen, was eine positive "
                    "Nachricht fuer die finanzielle Planung bedeutet.")
        self.assertGreater(erfundener_anteil(erfunden, self.INHALT), 0.25)

    def test_leerer_text_erfindet_nichts(self):
        self.assertEqual(erfundener_anteil("", self.INHALT), 0.0)


class TestBaselineSprechtext(unittest.TestCase):
    """Der Pfad, der tatsaechlich ausgeliefert wird, wenn das Modell schweigt."""

    def _bauen(self, titel: str) -> str:
        from app.services.briefing_assembly import _build_spoken_text
        return _build_spoken_text(
            top_items=[{"title": titel}],
            sections=[],
            for_date=__import__("datetime").date(2026, 10, 15),
        )

    def test_gedankenstrich_erreicht_das_tts_nicht(self):
        """874 Feed-Titel tragen einen solchen Strich; bisher schuetzte nur der
        LLM-Pfad davor, also genau der, der an einem langsamen Tag ausfaellt."""
        text = self._bauen(f"E-Bike-Boom flaut ab {KURZ} Preise fallen")
        self.assertNotIn(KURZ, text)
        self.assertNotIn(LANG, text)
        self.assertIn("E-Bike-Boom flaut ab, Preise fallen.", text)

    def test_kein_doppeltes_satzzeichen_im_ganzen_text(self):
        text = self._bauen("Koennen KI-Systeme sich selbst replizieren?")
        self.assertNotIn("?.", text)

    def test_begruessung_und_abschluss_stehen(self):
        text = self._bauen("Irgendeine Meldung")
        self.assertTrue(text.startswith(("Guten Morgen.", "Guten Tag.", "Guten Abend.")))
        self.assertIn("Das war dein Briefing.", text)


if __name__ == "__main__":
    unittest.main()
