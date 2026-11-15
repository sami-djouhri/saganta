"""Briefing am 15.11.2026: Modell stumm, Textvorlage holprig.

Das llm-gateway nahm an dem Morgen Verbindungen an und beantwortete keine
(sein Gast lagerte aus). Gesprochen wurde die Textvorlage, mit
„Europamagazin:" vor dem Titel, „Trauerfeier - …" und drei Anthropic-Meldungen.
Jede Gruppe hat eine Gegenprobe.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app import briefing_sched  # noqa: E402
from app.services import briefing_assembly as ba  # noqa: E402

INHALT = {
    "date": "2026-11-15",
    "spoken_text": "Guten Morgen. Hier ist dein Briefing.",
    "top_items": [{"title": "KI hat Windpark in unter zwei Stunden von Stromnetz getrennt",
                   "summary": "Ein KI-System hat einen Windpark vom Netz getrennt.",
                   "source": "heise online"}],
    "sections": [],
}
# Nur Wörter aus Titel und Kurztext, sonst verwirft `erfundener_anteil` die
# Fassung (zu Recht) und der Test prüft die Erfindungsprüfung statt des Wegs.
MODELLTEXT = ("KI hat Windpark in unter zwei Stunden von Stromnetz getrennt. "
              "Ein KI-System hat einen Windpark vom Netz getrennt.")


class TestTextvorlage(unittest.TestCase):
    def test_sendungsname_faellt_weg(self):
        self.assertEqual(ba._als_satz("Europamagazin: Ein Aufschwung, den die Spanier nicht spüren"),
                         "Ein Aufschwung, den die Spanier nicht spüren.")

    def test_dachzeile_wird_doppelpunkt(self):
        self.assertEqual(ba._als_satz("Raffineriekrise - SPD forderte strengere Regeln"),
                         "Raffineriekrise: SPD forderte strengere Regeln.")
        self.assertEqual(ba._als_satz("Nach Einigung für 2027 - Führende Ökonomen warnen"),
                         "Nach Einigung für 2027: Führende Ökonomen warnen.")

    def test_gegenprobe_strich_mitten_im_satz_bleibt(self):
        titel = "Die USA und China streiten sich - wieder einmal"
        self.assertEqual(ba._als_satz(titel), titel + ".")

    def test_gegenprobe_doppelpunkt_ohne_sendung_bleibt(self):
        titel = "Auf Anthropic wetten statt Aktien kaufen: Wie riskant sind Perpetual Futures?"
        self.assertEqual(ba._als_satz(titel), titel)


class TestThemenbremse(unittest.TestCase):
    TITEL = [
        "Auf Anthropic wetten statt Aktien kaufen: Wie riskant sind Perpetual Futures?",
        '"Große Unsicherheit": Anthropic-Chef hadert kurz vor Rekord-IPO',
        "Anthropic legt nach: Fable 5.2 und Mythos 5.2 im Performance-Check",
    ]

    def _auswahl(self, titel):
        zaehler, gewaehlt = {}, []
        for t in titel:
            k = ba._kerne(t)
            if ba._thema_voll(k, zaehler):
                continue
            gewaehlt.append(t)
            for x in k:
                zaehler[x] = zaehler.get(x, 0) + 1
        return gewaehlt

    def test_dritte_meldung_zum_selben_thema_faellt_weg(self):
        self.assertEqual(self._auswahl(self.TITEL), self.TITEL[:2])

    def test_gegenprobe_verschiedene_themen_bleiben(self):
        titel = ["Raffineriekrise - SPD forderte strengere Regeln für Spritpreisdeckel",
                 "KI hat Windpark in unter zwei Stunden von Stromnetz getrennt",
                 "Trauerfeier - Angehörige nehmen Abschied von Aiwanger"]
        self.assertEqual(self._auswahl(titel), titel)


class TestAusweichmodell(unittest.TestCase):
    def test_gateway_stumm_wartet_nicht_auf_den_chat(self):
        with mock.patch.object(ba.llm_client, "gateway_lebt", return_value=False), \
             mock.patch.object(ba.llm_client, "chat") as chat:
            text, herkunft = ba.spoken_narration(INHALT)
        self.assertEqual(herkunft, "deterministisch_llm_stumm")
        self.assertEqual(text, INHALT["spoken_text"])
        chat.assert_not_called()

    def test_hauptmodell_stumm_ausweichmodell_spricht(self):
        with mock.patch.object(ba.llm_client, "gateway_lebt", return_value=True), \
             mock.patch.object(ba.llm_client, "chat", side_effect=[None, MODELLTEXT]) as chat:
            text, herkunft = ba.spoken_narration(INHALT)
        self.assertEqual(herkunft, "llm_ausweich")
        self.assertIn("Windpark", text)
        self.assertEqual(chat.call_args_list[1].kwargs["model"], ba.settings.llm_model_ausweich)

    def test_gegenprobe_hauptmodell_spricht_kein_zweiter_aufruf(self):
        with mock.patch.object(ba.llm_client, "gateway_lebt", return_value=True), \
             mock.patch.object(ba.llm_client, "chat", return_value=MODELLTEXT) as chat:
            _text, herkunft = ba.spoken_narration(INHALT)
        self.assertEqual(herkunft, "llm")
        self.assertEqual(chat.call_count, 1)

    def test_beide_stumm(self):
        with mock.patch.object(ba.llm_client, "gateway_lebt", return_value=True), \
             mock.patch.object(ba.llm_client, "chat", return_value=None):
            _text, herkunft = ba.spoken_narration(INHALT)
        self.assertEqual(herkunft, "deterministisch_llm_stumm")


class TestNachholen(unittest.TestCase):
    JETZT = datetime(2026, 11, 15, 6, 45, tzinfo=timezone.utc)

    def _inhalt(self, vor_min, herkunft="deterministisch_llm_stumm", **mehr):
        return {"audio_text_herkunft": herkunft,
                "audio_fertig_um": (self.JETZT - timedelta(minutes=vor_min)).isoformat(),
                **mehr}

    def test_nach_frist_faellig(self):
        self.assertTrue(briefing_sched.llm_nachholen_faellig(self._inhalt(25), self.JETZT))

    def test_vor_frist_nicht(self):
        self.assertFalse(briefing_sched.llm_nachholen_faellig(self._inhalt(5), self.JETZT))

    def test_nur_einmal(self):
        for vermerk in (False, True):
            self.assertFalse(briefing_sched.llm_nachholen_faellig(
                self._inhalt(25, llm_nachgeholt=vermerk), self.JETZT))

    def test_gegenprobe_modell_hat_gesprochen(self):
        for h in ("llm", "llm_ausweich", "deterministisch_llm_erfand", "deterministisch_tarif"):
            self.assertFalse(briefing_sched.llm_nachholen_faellig(self._inhalt(25, h), self.JETZT))

    def test_altbestand_ohne_zeitstempel(self):
        self.assertFalse(briefing_sched.llm_nachholen_faellig(
            {"audio_text_herkunft": "deterministisch_llm_stumm"}, self.JETZT))


if __name__ == "__main__":
    unittest.main()
