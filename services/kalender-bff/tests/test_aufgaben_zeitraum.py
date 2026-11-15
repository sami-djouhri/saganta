"""Aufgaben im Kalender: der Lese-Weg zum Aufgaben-Dienst (seit 2026-11-11).

Der Aufgaben-Dienst wird nachgebaut: er prueft das Token wie das Original
(Zielgruppe, Signatur) und haelt fest, in wessen Namen gefragt wurde.
"""
import json
import os
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

os.environ.setdefault("JWT_SECRET", "test-secret-nur-fuer-den-testlauf")
os.environ.setdefault("ALLOWED_SUBS", "owner-sub")
os.environ.setdefault("KALENDER_TENANT_SECRET", "test-tenant-geheimnis")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

GEFRAGT: list[tuple[str, dict]] = []  # (sub, Abfrage)
ANTWORT_CODE = [200]


class AufgabenNachbau(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):  # noqa: N802
        from app.config import settings
        url = urlparse(self.path)
        kopf = self.headers.get("Authorization", "")
        try:
            nutzlast = jwt.decode(kopf.removeprefix("Bearer "), settings.jwt_secret,
                                  algorithms=["HS256"], audience="aufgaben-api")
        except Exception:
            self.send_response(401)
            self.end_headers()
            return
        if url.path != "/api/aufgaben/zeitraum":
            self.send_response(404)
            self.end_headers()
            return
        GEFRAGT.append((nutzlast["sub"], parse_qs(url.query)))
        rumpf = json.dumps([{"id": "a1", "titel": "Video-Ident", "tag": "2026-11-12",
                             "start": "2026-11-12T10:00:00", "ende": "2026-11-12T10:30:00"}])
        self.send_response(ANTWORT_CODE[0])
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(rumpf.encode())


def _jwt(sub: str = "owner-sub") -> str:
    from app.config import settings
    return jwt.encode({"iss": "saganta", "sub": sub, "aud": "kalender-bff", "email": "t@example.invalid",
                       "iat": int(time.time()), "exp": int(time.time()) + 300},
                      settings.jwt_secret, algorithm=settings.jwt_algorithm)


class AufgabenZeitraumTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), AufgabenNachbau)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        from app.config import settings
        cls.alt = settings.aufgaben_api_url
        settings.aufgaben_api_url = f"http://127.0.0.1:{cls.server.server_port}"
        from app.main import app
        cls.klient = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        from app.config import settings
        settings.aufgaben_api_url = cls.alt
        cls.server.shutdown()

    def setUp(self):
        GEFRAGT.clear()
        ANTWORT_CODE[0] = 200

    def test_fragt_im_namen_des_aufrufers_und_reicht_durch(self):
        r = self.klient.get("/api/aufgaben/zeitraum?von=2026-11-09&bis=2026-11-15",
                            headers={"Authorization": f"Bearer {_jwt()}"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()[0]["titel"], "Video-Ident")
        self.assertEqual(GEFRAGT, [("owner-sub", {"von": ["2026-11-09"], "bis": ["2026-11-15"]})])

    def test_ohne_anmeldung_kein_aufruf(self):
        r = self.klient.get("/api/aufgaben/zeitraum?von=2026-11-09&bis=2026-11-15")
        self.assertIn(r.status_code, (401, 403))
        self.assertEqual(GEFRAGT, [])

    def test_unsinniges_datum_wird_abgewiesen(self):
        r = self.klient.get("/api/aufgaben/zeitraum?von=morgen&bis=2026-11-15",
                            headers={"Authorization": f"Bearer {_jwt()}"})
        self.assertEqual(r.status_code, 422)

    def test_dienst_kaputt_ist_503(self):
        ANTWORT_CODE[0] = 500
        r = self.klient.get("/api/aufgaben/zeitraum?von=2026-11-09&bis=2026-11-15",
                            headers={"Authorization": f"Bearer {_jwt()}"})
        self.assertEqual(r.status_code, 503)

    def test_vorschlag_nimmt_fenster_an(self):
        from app.routes_assistant import VorschlagIn
        v = VorschlagIn.model_validate({"date": "2026-11-12", "aufgaben": [
            {"id": "a", "title": "A", "fenster": [{"von": "09:00", "bis": "18:00"}]}]})
        self.assertEqual(v.model_dump(exclude_none=True)["aufgaben"][0]["fenster"],
                         [{"von": "09:00", "bis": "18:00"}])
        with self.assertRaises(Exception):
            VorschlagIn.model_validate({"date": "2026-11-12", "aufgaben": [
                {"id": "a", "title": "A", "fenster": [{"von": "9 Uhr", "bis": "18:00"}]}]})


if __name__ == "__main__":
    unittest.main()
