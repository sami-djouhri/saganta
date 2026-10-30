"""Marktwert ohne konfigurierte Quelle.

Gefunden am 2026-09-12 beim Durchgang durch die Suite: `MARKTWATCH_BASE_URL`
war mit `http://marktwatch:8120` vorbelegt, und diesen Dienst gibt es weder in
der Suite noch auf dem Wirt, auf dem dieser Dienst laeuft (marktwatch steht
anderswo). Der Knopf "Marktwert" antwortete deshalb mit 502
"marktwatch unreachable", was nach einer Stoerung aussieht und keine war.

Geprueft wird das Verhalten der API, nicht die Vorbelegung: eine leere Adresse
muss 503 mit einer Aussage ueber die Konfiguration ergeben, und zwar ohne
Verbindungsversuch.
"""
import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="assets-markt-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ALLOWED_SUBS"] = ""
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-pruefung")

import time  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

ANNA = "sub-anna"


def kopf(sub: str) -> dict:
    token = jwt.encode(
        {"sub": sub, "iss": "saganta", "aud": "assets-api", "exp": int(time.time()) + 300},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


class TestMarktquelle(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.c = TestClient(app)

    def setUp(self):
        self._vorher = settings.marktwatch_base_url

    def tearDown(self):
        settings.marktwatch_base_url = self._vorher

    def _anlegen(self, name: str) -> int:
        r = self.c.post("/api/assets", json={"name": name}, headers=kopf(ANNA))
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()["id"]

    def test_ohne_quelle_503_statt_502(self):
        settings.marktwatch_base_url = ""
        kennung = self._anlegen("Kamera ohne Marktquelle")
        r = self.c.post(f"/api/assets/{kennung}/market", headers=kopf(ANNA))
        self.assertEqual(r.status_code, 503, r.text)
        self.assertIn("MARKTWATCH_BASE_URL", r.json()["detail"])

    def test_die_leere_adresse_ist_die_vorbelegung(self):
        """Damit die Vorbelegung nicht unbemerkt wieder auf einen Namen faellt,
        den es nirgends gibt."""
        from app.config import Settings

        frisch = Settings(_env_file=None)
        self.assertEqual(frisch.marktwatch_base_url, "")


if __name__ == "__main__":
    unittest.main()
