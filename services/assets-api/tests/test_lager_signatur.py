"""Der Lager-Spiegel darf das Lager nur mit Signatur ansprechen.

**Der Fehler, den dieser Test festnagelt** (gemessen 2026-10-16): ``upstream.py``
setzte ``X-Saganta-Sub`` ohne ``X-Saganta-Sub-Sig``, und
``LAGER_TENANT_SECRET`` stand in diesem Dienst nirgends. Das scharfe Lager
antwortete deshalb auf jede Spiegelung mit 401.

Der zweite Fall ist der teurere, und er ist der Grund fuer die mittlere
Pruefung unten. ``kopfzeilen()`` gibt bei fehlendem Geheimnis bewusst ein leeres
Dict zurueck. Wer nur den Aufruf umstellt und das Geheimnis vergisst, erzeugt
damit einen **headerlosen** Aufruf, und darauf antwortet das Lager mit 200 und
dem Bestand des Owners (``DEFAULT_OWNER_SUB``). Jeder Saganta-Nutzer bekaeme
dann die Elektronikliste des Owners in seine eigene Asset-Tabelle gespiegelt,
mit Erfolgsmeldung und ohne Logzeile. Das 401 war die einzige Sperre davor.

Geprueft wird deshalb dreierlei: dass die Signatur mitgeht, dass sie zum
richtigen ``sub`` gehoert, und dass ohne Geheimnis **kein** Aufruf hinausgeht.
"""

import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="assets-signatur-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ALLOWED_SUBS"] = ""
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-pruefung")

import time  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402
from saganta_dienst.tenant_sig import SIG_HEADER, SUB_HEADER, signatur  # noqa: E402

from app import upstream  # noqa: E402
from app.config import settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

ANNA = "sub-anna"
BERT = "sub-bert"
GEHEIM = "geheimnis-nur-fuer-die-pruefung"


def kopf(sub: str) -> dict:
    token = jwt.encode(
        {"sub": sub, "iss": "saganta", "aud": "assets-api", "exp": int(time.time()) + 300},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    return {"Authorization": f"Bearer {token}"}


class _Antwort:
    status_code = 200
    content = b"{}"

    def json(self):
        return {"items": [], "total": 0, "offset": 0, "limit": 200}


class _MitschreibenderClient:
    """Faengt die Kopfzeilen ab, mit denen das Lager angesprochen wuerde."""

    gesehen: list[dict] = []

    def __init__(self, *_, headers=None, **__):
        type(self).gesehen.append(dict(headers or {}))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, *_, **__):
        return _Antwort()


class LagerSignatur(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.client = TestClient(app)

    def setUp(self):
        self._altes_geheimnis = settings.lager_tenant_secret
        self._echter_client = upstream.httpx.AsyncClient
        _MitschreibenderClient.gesehen = []

    def tearDown(self):
        settings.lager_tenant_secret = self._altes_geheimnis
        upstream.httpx.AsyncClient = self._echter_client

    def test_signatur_geht_mit_und_haengt_am_richtigen_sub(self):
        settings.lager_tenant_secret = GEHEIM
        upstream.httpx.AsyncClient = _MitschreibenderClient

        r = self.client.post("/api/assets/sync/lager", headers=kopf(ANNA))
        self.assertEqual(r.status_code, 200, r.text)

        self.assertEqual(len(_MitschreibenderClient.gesehen), 1)
        kopfzeilen = _MitschreibenderClient.gesehen[0]
        self.assertEqual(kopfzeilen.get(SUB_HEADER), ANNA)
        self.assertEqual(kopfzeilen.get(SIG_HEADER), signatur(ANNA, GEHEIM))
        # Die Signatur haengt an genau diesem sub: die eines anderen Mandanten
        # darf nicht durchgehen, sonst waere sie umhaengbar.
        self.assertNotEqual(kopfzeilen.get(SIG_HEADER), signatur(BERT, GEHEIM))

    def test_ohne_geheimnis_geht_KEIN_aufruf_hinaus(self):
        """Der teure Fall: headerlos bekaeme man 200 mit den Daten des Owners."""
        settings.lager_tenant_secret = ""
        upstream.httpx.AsyncClient = _MitschreibenderClient

        r = self.client.post("/api/assets/sync/lager", headers=kopf(ANNA))
        self.assertEqual(r.status_code, 503, r.text)
        self.assertIn("LAGER_TENANT_SECRET", r.text)
        # Das ist die eigentliche Zusicherung: nicht "die Antwort ist ein
        # Fehler", sondern "es wurde ueberhaupt nicht gerufen".
        self.assertEqual(_MitschreibenderClient.gesehen, [])

    def test_headerloser_pfad_bleibt_erlaubt(self):
        """Ohne Mandanten gibt es nichts falsch zuzuordnen."""
        settings.lager_tenant_secret = ""
        upstream.httpx.AsyncClient = _MitschreibenderClient

        upstream.lager_client(None)
        self.assertEqual(_MitschreibenderClient.gesehen, [{}])


if __name__ == "__main__":
    unittest.main()
