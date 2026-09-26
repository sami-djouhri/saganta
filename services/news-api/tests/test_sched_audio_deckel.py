"""Der Scheduler darf die Sprachsynthese nicht am Stueck durchlaufen lassen.

XTTS arbeitet single-threaded und braucht 20 bis 40 Sekunden je Briefing. Die
Standard-Wunschzeit ist bei allen 06:30, also treffen alle faelligen Profile im
selben Durchlauf ein. Ohne Deckel belegt ein Tick den TTS-Dienst fuer Minuten,
und zwar genau den, den Saganta und life-ops gleichzeitig brauchen.

Geprueft wird deshalb nicht, dass der Deckel im Code steht, sondern dass ein
Durchlauf mit fuenf faelligen Nutzern hoechstens zwei Sprachfassungen anstoesst,
alle fuenf ihren Text bekommen und die uebrigen Sprachfassungen in den folgenden
Durchlaeufen wirklich nachkommen.
"""
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="news-sched-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-pruefung")
os.environ["BRIEFING_AUDIO_MAX_PER_TICK"] = "2"

from datetime import date  # noqa: E402

import app.briefing_sched as sched  # noqa: E402
from app.briefing_models import BriefingProfile, UserBriefing  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402
from app.services.briefing_service import audio_erlaubt as echte_tarifpruefung  # noqa: E402


class FakeBriefingService:
    """Ersetzt den echten Dienst: legt Zeilen an, ruft aber kein TTS und kein LLM.

    Der Ersatz ist absichtlich so nah am Original wie noetig: `generate_for_sub`
    schreibt eine Briefing-Zeile und setzt `audio_path` nur, wenn Audio verlangt
    war. Nur so nimmt der naechste Durchlauf denselben Nachzieh-Pfad wie live.
    """

    def __init__(self):
        self.texte = []
        self.audios = []

    def generate_for_sub(self, db, sub, for_date=None, force=False, with_audio=None):
        self.texte.append(sub)
        ub = UserBriefing(
            sub=sub,
            briefing_date=for_date or date.today(),
            content={"item_count": 0},
        )
        if with_audio:
            self.audios.append(sub)
            ub.audio_path = f"/data/{sub}.mp3"
            ub.audio_mime = "audio/mpeg"
        db.add(ub)
        db.commit()
        return ub

    def render_audio(self, db, sub, for_date=None):
        self.audios.append(sub)
        ub = (
            db.query(UserBriefing)
            .filter(UserBriefing.sub == sub, UserBriefing.briefing_date == (for_date or date.today()))
            .one_or_none()
        )
        if not ub:
            return False
        ub.audio_path = f"/data/{sub}.mp3"
        ub.audio_mime = "audio/mpeg"
        db.commit()
        return True

    # ★ Die Tarifpruefung wird NICHT nachgebaut, sondern an das Original
    # weitergereicht. Ein Ersatz, der hier einfach True lieferte, wuerde genau die
    # Regel wegnehmen, um die es geht. Und als der Scheduler diese Funktion neu
    # aufrief, der Ersatz sie aber noch nicht kannte, starb der ganze Durchlauf an
    # einem AttributeError: vier Tests fielen mit "0 statt 5 Texten" um, was nach
    # kaputtem Deckel aussah und ein fehlendes Stueck Attrappe war.
    audio_erlaubt = staticmethod(echte_tarifpruefung)

    def cleanup(self, db):
        return 0


class TestAudioDeckel(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        self.fake = FakeBriefingService()
        self.echt = sched.briefing_service
        sched.briefing_service = self.fake
        db = SessionLocal()
        try:
            for i in range(5):
                # 00:00 ist immer schon faellig, damit der Test nicht von der
                # Uhrzeit abhaengt, zu der er laeuft.
                # plan="pro": Sprachfassung ist seit dem 30.08.2026 ein Tarifmerkmal.
                # Ohne das waeren diese Tests still gruen geworden, weil gar nichts
                # mehr synthetisiert wird, und der Deckel bliebe ungeprueft.
                db.add(
                    BriefingProfile(
                        sub=f"nutzer-{i}",
                        enabled=True,
                        delivery_time="00:00",
                        audio_enabled=True,
                        plan="pro",
                    )
                )
            db.commit()
        finally:
            db.close()

    def tearDown(self):
        sched.briefing_service = self.echt

    def test_ein_durchlauf_erzeugt_hoechstens_zwei_sprachfassungen(self):
        sched._tick()
        self.assertEqual(len(self.fake.texte), 5, "jeder bekommt seinen Text sofort")
        self.assertEqual(len(self.fake.audios), settings.briefing_audio_max_per_tick)
        self.assertEqual(len(sched._state["last_audio_deferred"]), 3)

    def test_die_uebrigen_kommen_in_den_naechsten_durchlaeufen_nach(self):
        sched._tick()          # 2 von 5
        sched._tick()          # 2 weitere
        sched._tick()          # der letzte
        self.assertEqual(sorted(set(self.fake.audios)), [f"nutzer-{i}" for i in range(5)])
        self.assertEqual(len(self.fake.texte), 5, "kein zweiter Textaufbau")

    def test_ist_alles_vertont_bleibt_der_naechste_durchlauf_still(self):
        for _ in range(3):
            sched._tick()
        vorher = len(self.fake.audios)
        sched._tick()
        self.assertEqual(len(self.fake.audios), vorher)
        self.assertEqual(sched._state["last_audio_deferred"], [])

    def test_free_bekommt_keine_sprachfassung(self):
        """Der Tarif haelt, auch wenn der Nutzer Audio eingeschaltet hat.

        Die Synthese ist der teure Teil des Briefings. Bei offener Registrierung
        koennte sonst jeder Angemeldete taeglich Rechenzeit im Haus binden.
        """
        db = SessionLocal()
        try:
            for prof in db.query(BriefingProfile).all():
                prof.plan = "free"
            db.commit()
        finally:
            db.close()
        sched._tick()
        self.assertEqual(self.fake.audios, [], "free darf nichts synthetisieren")
        self.assertEqual(len(self.fake.texte), 5, "den Text bekommt trotzdem jeder")
        self.assertEqual(
            sched._state["last_audio_deferred"], [],
            "nicht verschoben, sondern gar nicht vorgesehen",
        )

    def test_ohne_audiowunsch_wird_nichts_verschoben(self):
        db = SessionLocal()
        try:
            for prof in db.query(BriefingProfile).all():
                prof.audio_enabled = False
            db.commit()
        finally:
            db.close()
        sched._tick()
        self.assertEqual(self.fake.audios, [])
        self.assertEqual(sched._state["last_audio_deferred"], [])
        self.assertEqual(len(self.fake.texte), 5)


if __name__ == "__main__":
    unittest.main()
