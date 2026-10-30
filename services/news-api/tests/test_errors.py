"""Fehlertexte des News-Ingests.

Anlass: über 10 Tage Betrieb standen 7 von 8 protokollierten Poll-Fehlern als
``error=""`` im Log. Die Quelle fiel aus, der Grund war nicht rekonstruierbar,
und derselbe leere String landete in ``FeedSource.last_error``, wo er als falsy
nicht mehr von "nie fehlgeschlagen" (None) zu unterscheiden war.

Deshalb prüfen die Tests hier NICHT nur die Hilfsfunktion, sondern den echten
Poll-Pfad: ein Test gegen ``describe()`` allein wäre grün geblieben, während
``poll_source`` weiter ``str(exc)`` schreibt.
"""
import asyncio
import os
import unittest

os.environ.setdefault("DATABASE_URL", "sqlite://")  # in-memory, vor dem app-Import

import httpx  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import ingest  # noqa: E402
from app.db import Base  # noqa: E402
from app.errors import describe  # noqa: E402
from app.models import FeedSource  # noqa: E402

# Genau die Klassen, die httpx bei Netzproblemen ohne Message wirft. Ein leerer
# Konstruktor-Text ist hier kein konstruierter Sonderfall, sondern der Normalfall.
STUMME_FEHLER = [
    httpx.ReadTimeout(""),
    httpx.ConnectTimeout(""),
    httpx.ConnectError(""),
    httpx.RemoteProtocolError(""),
    httpx.PoolTimeout(""),
]


class TestDescribe(unittest.TestCase):
    def test_stumme_netzwerkfehler_nennen_wenigstens_ihren_typ(self):
        for exc in STUMME_FEHLER:
            with self.subTest(typ=type(exc).__name__):
                self.assertEqual(str(exc), "", "Vorbedingung: str(exc) ist leer")
                text = describe(exc)
                self.assertTrue(text, "describe() darf nie leer sein")
                self.assertIn(type(exc).__name__, text)

    def test_http_fehler_nennt_den_statuscode(self):
        anfrage = httpx.Request("GET", "https://example.invalid/feed")
        antwort = httpx.Response(406, request=anfrage)
        exc = httpx.HTTPStatusError("egal", request=anfrage, response=antwort)
        text = describe(exc)
        self.assertIn("406", text)
        # Die httpx-Standardmeldung ist mehrzeilig und endet in einem MDN-Link:
        # den wollen wir nicht in einer 300-Zeichen-Spalte.
        self.assertNotIn("\n", text)

    def test_gespraechige_fehler_behalten_ihren_text(self):
        text = describe(ValueError("Feed liefert kein XML"))
        self.assertIn("ValueError", text)
        self.assertIn("Feed liefert kein XML", text)

    def test_limit_wird_eingehalten(self):
        text = describe(ValueError("x" * 5000), limit=300)
        self.assertLessEqual(len(text), 300)


class _FehlerClient:
    """AsyncClient-Ersatz, der beim GET eine vorgegebene Exception wirft."""

    def __init__(self, exc):
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, *_args, **_kwargs):
        raise self._exc


class TestPollSourceSchreibtLesbarenFehler(unittest.TestCase):
    """Der echte Pfad: was landet nach einem Timeout in der Datenbank?"""

    def setUp(self):
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self._echter_client = httpx.AsyncClient

    def tearDown(self):
        httpx.AsyncClient = self._echter_client
        self.engine.dispose()

    def _poll_mit_fehler(self, exc):
        httpx.AsyncClient = lambda *a, **kw: _FehlerClient(exc)
        db = self.Session()
        # slug ist UNIQUE, und die subTests einer Methode teilen sich eine DB:
        # ein fester Name lässt ab dem zweiten Durchlauf schon das INSERT scheitern.
        self._lauf = getattr(self, "_lauf", 0) + 1
        slug = f"testquelle-{self._lauf}"
        try:
            quelle = FeedSource(slug=slug, name="Testquelle", feed_url="https://x.invalid/f")
            db.add(quelle)
            db.commit()
            neu = asyncio.run(ingest.poll_source(db, quelle))
            db.refresh(quelle)
            return neu, quelle.last_error
        finally:
            db.close()

    def test_last_error_ist_nach_timeout_nicht_leer(self):
        for exc in STUMME_FEHLER:
            with self.subTest(typ=type(exc).__name__):
                neu, last_error = self._poll_mit_fehler(exc)
                self.assertEqual(neu, 0)
                # Der eigentliche Regressionsschutz: "" wäre falsy und damit von
                # last_error=None ("gesund") nicht zu unterscheiden.
                self.assertTrue(last_error, f"last_error={last_error!r} ist falsy")
                self.assertIn(type(exc).__name__, last_error)

    def test_last_error_passt_in_die_spalte(self):
        _, last_error = self._poll_mit_fehler(ValueError("y" * 5000))
        self.assertLessEqual(len(last_error), 300, "Spalte ist String(300)")


if __name__ == "__main__":
    unittest.main()
