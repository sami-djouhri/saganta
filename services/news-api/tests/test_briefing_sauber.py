"""Briefing sauber (14.11.2026): Kurztext, Bezahlschranke, Rubrik, Vortage,
Begruessung, Behauptungen.

Wie in `test_briefing_auswahl.py` stammen die Faelle aus den echten Briefings
vom 08. bis 14.11.2026, und jede Gruppe hat eine Gegenprobe.
"""
import os
import unittest
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite://")

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.briefing_models import UserBriefing  # noqa: E402
from app.db import Base  # noqa: E402
from app.models import FeedItem  # noqa: E402
from app.services import interest_taxonomy as tax  # noqa: E402
from app.services.briefing_assembly import (  # noqa: E402
    _ensure_greeting,
    _hinter_bezahlschranke,
    _kerne,
    _ohne_klammer,
    _rubrik,
    _vortags_meldungen,
    _zu_aehnlich,
    _zusammenfassung_saeubern,
    behauptung_verloren,
)

PROFIL = {"politik": 1.0, "wirtschaft": 1.0, "tech": 1.0, "ki": 1.0,
          "wissenschaft": 1.0, "gesundheit": 1.0, "welt": 1.0}


class TestZusammenfassung(unittest.TestCase):
    def test_bild_tag_faellt_weg(self):
        roh = ('<img align="left" alt="Aktivistin Teresa Anderson mit Megafon" '
               'src="https://bilder.deutschlandfunk.de/x.jpg" />Fuehrende '
               'Wirtschaftswissenschaftler erwarten schwierige Jahre.')
        self.assertEqual(_zusammenfassung_saeubern(roh),
                         "Fuehrende Wirtschaftswissenschaftler erwarten schwierige Jahre.")

    def test_abspann_der_fachpresse_faellt_weg(self):
        roh = ('<p>Chinesische Investoren duerfen keine Anteile zeichnen.</p>\n'
               '<p>Der Artikel <a href="https://the-decoder.de/x">Nach SpaceX</a> '
               'erschien zuerst auf THE-DECODER.de.</p>')
        self.assertEqual(_zusammenfassung_saeubern(roh),
                         "Chinesische Investoren duerfen keine Anteile zeichnen.")

    def test_autorenzeile_faellt_weg(self):
        roh = ("Umweltverbaende werfen Kanzler Merz einen Rollback vor. "
               "Von Susanne Henn.")
        self.assertEqual(_zusammenfassung_saeubern(roh),
                         "Umweltverbaende werfen Kanzler Merz einen Rollback vor.")

    def test_von_mitten_im_satz_bleibt(self):
        """Gegenprobe: „von" als Praeposition ist keine Autorenzeile."""
        satz = "Die Rede von Kanzler Merz wurde kritisiert."
        self.assertEqual(_zusammenfassung_saeubern(satz), satz)


class TestBezahlschranke(unittest.TestCase):
    def test_heise_plus(self):
        self.assertTrue(_hinter_bezahlschranke(FeedItem(
            title="Bit-Rauschen: Nvidia-Chef tritt ab",
            link="https://www.heise.de/hintergrund/x.html?wt_mc=rss.red.ho.ho.atom.beitrag_plus.beitrag_plus")))
        self.assertTrue(_hinter_bezahlschranke(FeedItem(
            title="heise+ | Bit-Rauschen: EU-CPU rechnet los", link="https://www.heise.de/x")))

    def test_freie_heise_meldung_bleibt(self):
        self.assertFalse(_hinter_bezahlschranke(FeedItem(
            title="Aus fuer OnePlus: Hersteller zieht sich zurueck",
            link="https://www.heise.de/news/x.html?wt_mc=rss.red.ho.ho.atom.beitrag.beitrag")))


class TestThemensuche(unittest.TestCase):
    def test_esa_trifft_nicht_teresa(self):
        self.assertNotIn("wissenschaft", tax.match_tags("Aktivistin Teresa Anderson"))

    def test_esa_als_wort_trifft(self):
        self.assertIn("wissenschaft", tax.match_tags("Die ESA startet eine Sonde"))

    def test_kompositum_mit_langem_stichwort_trifft_weiter(self):
        self.assertIn("politik", tax.match_tags("Vor der Bundestagswahl"))

    def test_ki_bindestrich_am_wortanfang(self):
        self.assertIn("ki", tax.match_tags("KI-Aktien fahren Achterbahn"))


class TestRubrik(unittest.TestCase):
    def test_titel_vor_kurztext(self):
        """Lief am 14.11. unter Politik (wegen „Midterm-Wahlen" im Kurztext)."""
        tags = ["wirtschaft", "ki", "politik", "welt"]
        self.assertEqual(
            _rubrik("Bit-Rauschen: Nvidia-Chef tritt ab, KI-Aktien fahren Achterbahn",
                    tags, PROFIL), "wirtschaft")

    def test_tuerkei_demo_nicht_unter_wissenschaft(self):
        """Mit den Themen, die Titel und gesaeuberter Kurztext wirklich tragen."""
        titel = ("Türkei - Genehmigte Demonstrationen zur Halbzeit der "
                 "UNO-Klimakonferenz angekündigt")
        kurz = _zusammenfassung_saeubern(
            '<img alt="Aktivistin Teresa Anderson mit Megafon bei der UN-Klimakonferenz" />'
            'Zur Halbzeit der Weltklimakonferenz sind Demonstrationen angekuendigt.')
        tags = sorted(tax.match_tags(f"{titel} {kurz}"))
        self.assertNotIn("wissenschaft", tags)
        self.assertEqual(_rubrik(titel, tags, PROFIL), "welt")

    def test_ohne_titeltreffer_zaehlt_der_kurztext(self):
        self.assertEqual(_rubrik("Werner-Holzer-Preis für Gloger und Abdul Karim",
                                 ["politik", "welt"], PROFIL), "politik")


class TestVortage(unittest.TestCase):
    def test_folgemeldung_ist_dieselbe_nachricht(self):
        """13.11. gegen 12.11., gemessen 0,43."""
        self.assertTrue(_zu_aehnlich(
            _kerne("Spionageaffäre - US-Senat lädt Ex-Nvidia-Chef Jensen Huang und "
                   "Handelsminister Howard Lutnick vor"),
            _kerne("Jensen Huang nach weiterer Affäre mit Mitarbeiterin wohl vor dem Aus")))

    def test_anderes_thema_bleibt(self):
        """Gegenprobe, gemessen 0,25: Klimaschutz gegen Haushaltskompromiss."""
        self.assertFalse(_zu_aehnlich(
            _kerne("Keine Priorität für Klimaschutz in der Koalition"),
            _kerne("Haushalt 2027 - Koalition findet Etat-Kompromisse, "
                   "Stromsteuer für Private")))

    def test_liest_nur_vortage_derselben_person(self):
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        meldung = {"title": "Jensen Huang vor dem Aus", "link": "https://x.example.invalid/1"}
        db.add_all([
            UserBriefing(sub="a", briefing_date=date(2026, 11, 13),
                         content={"top_items": [meldung], "sections": []}),
            UserBriefing(sub="a", briefing_date=date(2026, 11, 10),
                         content={"top_items": [{"title": "Zu alt", "link": "https://x.example.invalid/2"}]}),
            UserBriefing(sub="b", briefing_date=date(2026, 11, 13),
                         content={"top_items": [{"title": "Fremd", "link": "https://x.example.invalid/3"}]}),
            UserBriefing(sub="a", briefing_date=date(2026, 11, 14),
                         content={"top_items": [{"title": "Heute", "link": "https://x.example.invalid/4"}]}),
        ])
        db.commit()
        links, kerne = _vortags_meldungen(db, "a", date(2026, 11, 14))
        self.assertEqual(links, {"https://x.example.invalid/1"})
        self.assertEqual(len(kerne), 1)


class TestBegruessung(unittest.TestCase):
    def test_falsche_begruessung_wird_ersetzt(self):
        """14.11.: 06:13 UTC = 07:13 Berlin, das Modell sagte „Guten Tag"."""
        content = {"generated_at": "2026-11-14T06:13:05+00:00"}
        self.assertEqual(_ensure_greeting("Guten Tag, 14.11.2026. Das Wetter ist neblig.", content),
                         "Guten Morgen. 14.11.2026. Das Wetter ist neblig.")
        self.assertTrue(_ensure_greeting("Hallo, heute ist der 13. November.", content)
                        .startswith("Guten Morgen. Heute ist"))

    def test_ohne_begruessung_kommt_eine_dazu(self):
        content = {"generated_at": "2026-11-14T06:13:05+00:00"}
        self.assertEqual(_ensure_greeting("Das Wetter ist neblig.", content),
                         "Guten Morgen. Das Wetter ist neblig.")


class TestBehauptung(unittest.TestCase):
    CONTENT = {"sections": [{"items": [{
        "title": "Ex-OpenAI-Forscher will Nutzung sanktionierter Nvidia-Chips in "
                 "chinesischen Top-KI-Modellen nachgewiesen haben",
        "summary": "Ex-OpenAI-Forscher Will DePue will erstmals technisch belegt haben, "
                   "dass DeepSeek trotz US-Exportkontrollen Blackwell-GPUs nutzt.",
    }]}]}

    def test_behauptung_als_tatsache_wird_erkannt(self):
        """Wortlaut der Sprachfassung vom 14.11."""
        text = ("The Decoder berichtet ebenfalls, dass ein Ex-OpenAI-Forscher Will DePue "
                "erstmals technisch belegt hat, dass Nvidia-Chips genutzt werden.")
        self.assertEqual(behauptung_verloren(text, self.CONTENT), ["belegt"])

    def test_behauptung_als_behauptung_ist_in_ordnung(self):
        text = "Der Forscher Will DePue will erstmals technisch belegt haben, dass Chips genutzt werden."
        self.assertEqual(behauptung_verloren(text, self.CONTENT), [])
        text = "Laut Will DePue ist erstmals technisch belegt, dass Chips genutzt werden."
        self.assertEqual(behauptung_verloren(text, self.CONTENT), [])

    def test_ohne_behauptung_in_der_quelle_nichts(self):
        content = {"top_items": [{"title": "Studie hat Wirkung belegt", "summary": ""}]}
        self.assertEqual(behauptung_verloren("Eine Studie hat die Wirkung belegt.", content), [])


class TestTerminKlammer(unittest.TestCase):
    def test_klammer_faellt_weg(self):
        self.assertEqual(_ohne_klammer("Probeprüfung: Prozesse der Lagerlogistik (Lernstufe, IHK-Modus)"),
                         "Probeprüfung: Prozesse der Lagerlogistik")
        self.assertEqual(_ohne_klammer("Weg nach Hause (Zuhause)"), "Weg nach Hause")

    def test_ohne_klammer_unveraendert(self):
        self.assertEqual(_ohne_klammer("Homelab-Zeit"), "Homelab-Zeit")
        self.assertEqual(_ohne_klammer(None), "")


if __name__ == "__main__":
    unittest.main()
