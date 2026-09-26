"""Der Lager-Spiegel gegen die echte Antwortform des Lagers.

Gefunden am 2026-09-18, als die Asset-Tabelle erstmals gefuellt werden sollte:
`POST /assets/sync/lager` brach bei jedem Aufruf mit
"'str' object has no attribute 'get'". Ursache war die Form der Antwort. Das
Lager liefert `Page[ElectronicAssetOut]`, also `{"items": [...], "total": n,
"offset": 0, "limit": 200}`; der Spiegel iterierte das JSON direkt und lief
damit ueber die Schluessel des Objekts. Der Weg war deshalb nie gelaufen, und
das sah von aussen nicht wie ein Fehler aus, sondern wie eine leere App.

Geprueft wird die Antwortform, nicht die Verbindung: das Lager wird ersetzt, die
Route bleibt echt. Dazu der zweite Fall, der hier besonders leise waere, ein
Spiegel mit 200 von 300 Geraeten.
"""

import os
import tempfile
import unittest

_tmp = tempfile.mkdtemp(prefix="assets-spiegel-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["ALLOWED_SUBS"] = ""
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-pruefung")

import time  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app import routes_assets  # noqa: E402
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


class _Antwort:
    def __init__(self, nutzlast):
        self._nutzlast = nutzlast
        self.status_code = 200
        self.content = b"{}"
        self.text = ""

    def json(self):
        return self._nutzlast


class _Lager:
    """Ersetzt den httpx-Client und gibt vorgegebene Seiten heraus."""

    def __init__(self, seiten):
        self.seiten = list(seiten)
        self.abfragen = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def get(self, _pfad, params=None):
        self.abfragen.append(params or {})
        return _Antwort(self.seiten.pop(0))


def _geraet(nr: int) -> dict:
    return {
        "id": nr,
        "name": f"Geraet {nr}",
        "category": "Homelab Host",
        "location": "Homelab",
        "usage_status": "critical",
        "purchase_price": None,
        "estimated_resale_value": None,
    }


class TestLagerSpiegel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()
        cls.c = TestClient(app)

    def setUp(self):
        self._echt = routes_assets.lager_client

    def tearDown(self):
        routes_assets.lager_client = self._echt

    def _lager_stellen(self, seiten) -> _Lager:
        lager = _Lager(seiten)
        routes_assets.lager_client = lambda _sub=None: lager
        return lager

    def test_paginierte_huelle_wird_gespiegelt(self):
        """Die echte Form des Lagers. Vor dem Fix: 500 statt 200."""
        self._lager_stellen([{"items": [_geraet(1), _geraet(2)], "total": 2, "offset": 0, "limit": 200}])
        r = self.c.post("/api/assets/sync/lager", headers=kopf(ANNA))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["added"], 2)

        liste = self.c.get("/api/assets", headers=kopf(ANNA))
        namen = {a["name"] for a in liste.json()}
        self.assertEqual(namen, {"Geraet 1", "Geraet 2"})

    def test_zweiter_lauf_aktualisiert_statt_zu_verdoppeln(self):
        """Beide Laeufe hier im Test, nicht auf die Test-Reihenfolge verlassen."""
        seite = {"items": [_geraet(31), _geraet(32)], "total": 2, "offset": 0, "limit": 200}
        nutzer = kopf("sub-zweimal")

        self._lager_stellen([seite])
        erst = self.c.post("/api/assets/sync/lager", headers=nutzer)
        self.assertEqual(erst.status_code, 200, erst.text)
        self.assertEqual(erst.json()["added"], 2)

        self._lager_stellen([seite])
        wieder = self.c.post("/api/assets/sync/lager", headers=nutzer)
        self.assertEqual(wieder.status_code, 200, wieder.text)
        self.assertEqual(wieder.json()["added"], 0)
        self.assertEqual(wieder.json()["updated"], 2)

    def test_blaettert_bis_total(self):
        """Ein Spiegel mit 2 von 3 Geraeten saehe vollstaendig aus."""
        lager = self._lager_stellen(
            [
                {"items": [_geraet(11), _geraet(12)], "total": 3, "offset": 0, "limit": 2},
                {"items": [_geraet(13)], "total": 3, "offset": 2, "limit": 2},
            ]
        )
        r = self.c.post("/api/assets/sync/lager", headers=kopf("sub-blaettern"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["added"], 3)
        self.assertEqual(len(lager.abfragen), 2)
        self.assertEqual(lager.abfragen[1]["offset"], 2)

    def test_flache_liste_bleibt_zulaessig(self):
        """Ein anderes oder aelteres Lager darf weiter eine Liste liefern."""
        self._lager_stellen([[_geraet(21)]])
        r = self.c.post("/api/assets/sync/lager", headers=kopf("sub-flach"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["added"], 1)


if __name__ == "__main__":
    unittest.main()
