"""Das Briefing kommt zur Aufstehzeit aus dem Kalender, nicht zur festen Wunschzeit.

Gemessen am 2026-11-08: Arbeitstag, Aufstehen 05:42, Briefing fest um 06:30, also
nach dem Wecken und kurz vor dem Losgehen (ZIELBILD 48, RICHTUNG.md Abschnitt
Zeitpunkt). Geprueft wird die Faelligkeit selbst, der Rueckfall auf
`delivery_time` und dass der Kalender nicht jede Minute gefragt wird.
"""
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="news-aufsteh-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-pruefung")

from datetime import date, datetime  # noqa: E402

import app.briefing_sched as sched  # noqa: E402
from app.briefing_models import BriefingProfile  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import Base, SessionLocal, engine  # noqa: E402

TAG = date(2026, 11, 9)


class FakeKalender:
    def __init__(self, wert):
        self.wert = wert
        self.abrufe = 0

    def fetch_aufstehen(self, sub, day):
        self.abrufe += 1
        if isinstance(self.wert, Exception):
            raise self.wert
        return self.wert


def profil(delivery="06:30"):
    return BriefingProfile(sub="probe-sub", delivery_time=delivery)


class TestAufstehzeit(unittest.TestCase):
    def setUp(self):
        self.echt = sched.kalender_client
        self.vorlauf = settings.briefing_vorlauf_min
        settings.briefing_vorlauf_min = 15
        sched._aufstehen_cache.clear()

    def tearDown(self):
        sched.kalender_client = self.echt
        settings.briefing_vorlauf_min = self.vorlauf
        sched._aufstehen_cache.clear()

    def test_aufstehzeit_minus_vorlauf(self):
        sched.kalender_client = FakeKalender("05:42")
        ab, vom_plan = sched._faellig_ab(profil(), TAG, 5 * 60)
        self.assertEqual(ab, 5 * 60 + 27)
        self.assertTrue(vom_plan)

    def test_rueckfall_auf_wunschzeit_ohne_kalenderzeit(self):
        sched.kalender_client = FakeKalender(None)
        ab, vom_plan = sched._faellig_ab(profil("07:10"), TAG, 5 * 60)
        self.assertEqual(ab, 7 * 60 + 10)
        self.assertFalse(vom_plan)

    def test_rueckfall_wenn_kalender_wirft(self):
        sched.kalender_client = FakeKalender(RuntimeError("weg"))
        ab, vom_plan = sched._faellig_ab(profil("06:30"), TAG, 5 * 60)
        self.assertEqual(ab, 6 * 60 + 30)
        self.assertFalse(vom_plan)

    def test_unbrauchbarer_wert_gilt_als_keiner(self):
        sched.kalender_client = FakeKalender("25:99")
        ab, vom_plan = sched._faellig_ab(profil("06:30"), TAG, 5 * 60)
        self.assertEqual((ab, vom_plan), (6 * 60 + 30, False))

    def test_nie_vor_mitternacht(self):
        sched.kalender_client = FakeKalender("00:05")
        ab, _ = sched._faellig_ab(profil(), TAG, 0)
        self.assertEqual(ab, 0)

    def test_cache_fragt_nicht_jede_minute(self):
        fake = FakeKalender("05:42")
        sched.kalender_client = fake
        for minute in range(4 * 60, 4 * 60 + 5):
            sched._faellig_ab(profil(), TAG, minute)
        self.assertEqual(fake.abrufe, 1)

    def test_erreichte_zeit_wird_nicht_nachgefragt(self):
        fake = FakeKalender("05:42")
        sched.kalender_client = fake
        sched._faellig_ab(profil(), TAG, 5 * 60)
        # Cache kuenstlich altern lassen: ein erreichter Wert bleibt trotzdem.
        wert, _ = sched._aufstehen_cache[("probe-sub", TAG)]
        sched._aufstehen_cache[("probe-sub", TAG)] = (wert, -10_000.0)
        fake.wert = "09:00"
        ab, _ = sched._faellig_ab(profil(), TAG, 6 * 60)
        self.assertEqual(ab, 5 * 60 + 27)
        self.assertEqual(fake.abrufe, 1)

    def test_veralteter_unerreichter_wert_wird_erneuert(self):
        fake = FakeKalender("07:00")
        sched.kalender_client = fake
        sched._faellig_ab(profil(), TAG, 4 * 60)
        sched._aufstehen_cache[("probe-sub", TAG)] = ("07:00", -10_000.0)
        fake.wert = "05:42"  # nachts kam ein frueher Termin dazu
        ab, _ = sched._faellig_ab(profil(), TAG, 4 * 60 + 30)
        self.assertEqual(ab, 5 * 60 + 27)
        self.assertEqual(fake.abrufe, 2)


class FesteUhr:
    """Ersetzt `datetime` im Scheduler-Modul, nur `now` wird gebraucht."""

    jetzt = None

    @classmethod
    def now(cls, tz=None):
        return cls.jetzt.replace(tzinfo=tz)


class ZaehlenderDienst:
    def __init__(self):
        self.texte = []

    def generate_for_sub(self, db, sub, for_date=None, force=False, with_audio=None):
        from app.briefing_models import UserBriefing

        self.texte.append(sub)
        db.add(UserBriefing(sub=sub, briefing_date=for_date, content={"item_count": 0},
                            audio_path="/data/x.mp3" if with_audio else None))
        db.commit()

    def audio_erlaubt(self, prof):
        return False

    def cleanup(self, db):
        return 0


class TestDurchlauf(unittest.TestCase):
    """Der Tick selbst haelt sich an die Aufstehzeit, nicht nur die Hilfsfunktion."""

    def setUp(self):
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        db = SessionLocal()
        db.add(BriefingProfile(sub="probe-sub", enabled=True, delivery_time="06:30"))
        db.commit()
        db.close()
        self.echt = (sched.kalender_client, sched.briefing_service, sched.datetime)
        sched.kalender_client = FakeKalender("05:42")
        self.dienst = ZaehlenderDienst()
        sched.briefing_service = self.dienst
        sched.datetime = FesteUhr
        sched._aufstehen_cache.clear()
        self.vorlauf = settings.briefing_vorlauf_min
        settings.briefing_vorlauf_min = 15

    def tearDown(self):
        sched.kalender_client, sched.briefing_service, sched.datetime = self.echt
        sched._aufstehen_cache.clear()
        settings.briefing_vorlauf_min = self.vorlauf

    def test_vorgabe_klingelt_nicht_vor_dem_wecker(self):
        settings.briefing_vorlauf_min = type(settings).model_fields["briefing_vorlauf_min"].default
        FesteUhr.jetzt = datetime(2026, 11, 9, 5, 41)
        sched._tick()
        self.assertEqual(self.dienst.texte, [])
        FesteUhr.jetzt = datetime(2026, 11, 9, 5, 42)
        sched._tick()
        self.assertEqual(self.dienst.texte, ["probe-sub"])

    def test_kommt_vor_der_wunschzeit_wenn_der_kalender_frueher_weckt(self):
        FesteUhr.jetzt = datetime(2026, 11, 9, 5, 26)
        sched._tick()
        self.assertEqual(self.dienst.texte, [])
        FesteUhr.jetzt = datetime(2026, 11, 9, 5, 27)
        sched._tick()
        self.assertEqual(self.dienst.texte, ["probe-sub"])
        self.assertEqual(sched.status()["zeit_aus_kalender"], 1)


if __name__ == "__main__":
    unittest.main()
