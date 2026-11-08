"""Aufgaben aus dem Aufgaben-Dienst: Durchreichen, Projektgrenze, Rechnung, Ausfall.

Sechste Fragerunde (04.11., `docs/RICHTUNG.md`). Der Dienst wird hier durch
einen kleinen Nachbau im Speicher ersetzt (`aufgaben_nachbau.py`).
"""

import os
import tempfile
import unittest
import uuid

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='.db')}")
os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app import aufgaben_dienst  # noqa: E402
from app.auth import Me, verify_jwt  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from tests.aufgaben_nachbau import Nachbau  # noqa: E402

app.dependency_overrides[verify_jwt] = lambda: Me(sub="tester", email="t@t")
init_db()
client = TestClient(app)


class Grundlage(unittest.TestCase):
    def setUp(self):
        self.dienst = Nachbau()
        self._alt = aufgaben_dienst.aufruf
        aufgaben_dienst.aufruf = self.dienst

    def tearDown(self):
        aufgaben_dienst.aufruf = self._alt

    def projekt(self, **felder) -> dict:
        r = client.post("/api/projects", json={"name": f"P {uuid.uuid4().hex[:6]}", **felder})
        self.assertEqual(r.status_code, 201, r.text)
        return r.json()


class TestDurchreichen(Grundlage):
    def test_anlegen_setzt_das_projekt_selbst(self):
        p = self.projekt()
        r = client.post(f"/api/projects/{p['id']}/aufgaben",
                        json={"titel": "Shop-Update", "projekt": "fremd", "liste_id": "x"})
        self.assertEqual(r.status_code, 201, r.text)
        gesendet = self.dienst.aufrufe[-1][2]["json"]
        self.assertEqual(gesendet["projekt"], p["slug"])
        self.assertNotIn("liste_id", gesendet)
        liste = client.get(f"/api/projects/{p['id']}/aufgaben").json()
        self.assertEqual([a["titel"] for a in liste], ["Shop-Update"])

    def test_aufgabe_eines_anderen_projekts_ist_404(self):
        a, b = self.projekt(), self.projekt()
        aufgabe = client.post(f"/api/projects/{a['id']}/aufgaben", json={"titel": "x"}).json()
        for methode, pfad in (("put", ""), ("post", "/erledigt"), ("post", "/offen"), ("delete", "")):
            kw = {"json": {"titel": "y"}} if methode == "put" else {}
            r = getattr(client, methode)(f"/api/projects/{b['id']}/aufgaben/{aufgabe['id']}{pfad}", **kw)
            self.assertEqual(r.status_code, 404, (methode, pfad))
        self.assertEqual(self.dienst.aufgaben[aufgabe["id"]]["titel"], "x")

    def test_abhaken_aendern_loeschen(self):
        p = self.projekt()
        a = client.post(f"/api/projects/{p['id']}/aufgaben", json={"titel": "x"}).json()
        self.assertTrue(client.post(f"/api/projects/{p['id']}/aufgaben/{a['id']}/erledigt").json()["erledigt"])
        r = client.put(f"/api/projects/{p['id']}/aufgaben/{a['id']}", json={"titel": "neu", "projekt": None})
        self.assertEqual(r.json()["titel"], "neu")
        self.assertEqual(r.json()["projekt"], p["slug"], "umgehaengt wird nicht ueber das ProjectDeck")
        self.assertEqual(client.delete(f"/api/projects/{p['id']}/aufgaben/{a['id']}").status_code, 204)
        self.assertNotIn(a["id"], self.dienst.aufgaben)

    def test_fehler_des_dienstes_kommen_mit_code_an(self):
        p = self.projekt()
        self.assertEqual(client.put(f"/api/projects/{p['id']}/aufgaben/gibtsnicht", json={}).status_code, 404)
        self.dienst.aus = True
        self.assertEqual(client.get(f"/api/projects/{p['id']}/aufgaben").status_code, 503)

    def test_fremdes_projekt_ist_404_ohne_aufruf_am_dienst(self):
        r = client.get("/api/projects/999999/aufgaben")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(self.dienst.aufrufe, [])


class TestRechnung(Grundlage):
    def test_an_rechnet_mit_den_aufgaben_des_dienstes(self):
        p = self.projekt(deadline_date="2099-01-01")
        client.post(f"/api/projects/{p['id']}/aufgaben", json={"titel": "x", "dauer_min": 90})
        befunde = {f["rule_id"] for f in client.get("/api/findings").json() if f["slug"] == p["slug"]}
        self.assertNotIn("deadline_without_schedulable_tasks", befunde)
        risiko = next(r for r in client.get("/api/deadline-center").json() if r["slug"] == p["slug"])
        self.assertEqual(risiko["total_remaining_minutes"], 90)
        kachel = next(x for x in client.get("/api/projects").json() if x["id"] == p["id"])
        self.assertEqual(kachel["open_tasks"], 1)
        self.assertEqual(kachel["open_high"], 0)

    def test_kachel_zaehlt_hohe_prioritaet(self):
        p = self.projekt()
        for prio in ("hoch", "hoch", "mittel"):
            client.post(f"/api/projects/{p['id']}/aufgaben", json={"titel": "x", "prioritaet": prio})
        kachel = next(x for x in client.get("/api/projects").json() if x["id"] == p["id"])
        self.assertEqual((kachel["open_tasks"], kachel["open_high"]), (3, 2))

    def test_wartende_sind_nicht_planbar(self):
        p = self.projekt(deadline_date="2099-01-01")
        a = client.post(f"/api/projects/{p['id']}/aufgaben", json={"titel": "x"}).json()
        self.dienst.aufgaben[a["id"]]["wartet"] = True
        befunde = {f["rule_id"] for f in client.get("/api/findings").json() if f["slug"] == p["slug"]}
        self.assertIn("deadline_without_schedulable_tasks", befunde)

    def test_ausfall_behauptet_nichts(self):
        """Ohne Antwort weder „kein planbarer Task" noch „entspannt"."""
        p = self.projekt(deadline_date="2099-01-01")
        self.dienst.aus = True
        befunde = {f["rule_id"] for f in client.get("/api/findings").json() if f["slug"] == p["slug"]}
        self.assertNotIn("deadline_without_schedulable_tasks", befunde)
        risiko = next(r for r in client.get("/api/deadline-center").json() if r["slug"] == p["slug"])
        self.assertEqual(risiko["risk_level"], "unknown")
        ki = client.get(f"/api/projects/{p['id']}/ai/deadline-plan").json()
        self.assertTrue(any("nicht erreichbar" in z for z in ki["reasoning"]), ki["reasoning"])


class TestProjektLoeschen(Grundlage):
    def test_aufgaben_fallen_nach_nicht_zugeordnet(self):
        p = self.projekt()
        a = client.post(f"/api/projects/{p['id']}/aufgaben", json={"titel": "bleibt"}).json()
        self.assertEqual(client.delete(f"/api/projects/{p['id']}").status_code, 204)
        self.assertIsNone(self.dienst.aufgaben[a["id"]]["projekt"])

    def test_ohne_dienst_bleibt_das_projekt_stehen(self):
        p = self.projekt()
        self.dienst.aus = True
        self.assertEqual(client.delete(f"/api/projects/{p['id']}").status_code, 503)
        self.assertEqual(client.get(f"/api/projects/{p['id']}").status_code, 200)


class TestUebersicht(Grundlage):
    """GET /api/aufgaben: offene Aufgaben aller eigenen Projekte, mit Projekt."""

    def test_traegt_projekt_und_kennt_nur_eigene(self):
        a = self.projekt()
        b = self.projekt()
        client.post(f"/api/projects/{a['id']}/aufgaben", json={"titel": "UA", "prioritaet": "niedrig"})
        client.post(f"/api/projects/{b['id']}/aufgaben", json={"titel": "UB", "prioritaet": "hoch"})
        # Eine Aufgabe mit dem Slug eines fremden oder geloeschten Projekts und
        # eine ohne Projekt stehen in Saganta Aufgaben, nicht hier.
        self.dienst.aufgaben["x"] = {"id": "x", "titel": "fremd", "erledigt": False,
                                     "projekt": "gibt-es-nicht", "prioritaet": "hoch"}
        self.dienst.aufgaben["y"] = {"id": "y", "titel": "lose", "erledigt": False,
                                     "projekt": None, "prioritaet": "hoch"}
        liste = client.get("/api/aufgaben").json()
        titel = [t["titel"] for t in liste]
        self.assertEqual(titel, ["UB", "UA"], "hoch vor niedrig, nur eigene Projekte")
        self.assertEqual(liste[0]["project_id"], b["id"])
        self.assertEqual(liste[0]["project_name"], b["name"])

    def test_ausfall_ist_503(self):
        self.dienst.aus = True
        self.assertEqual(client.get("/api/aufgaben").status_code, 503)


class TestAlteKennung(Grundlage):
    def test_loest_ueber_herkunft_auf_und_nur_im_eigenen_projekt(self):
        p = self.projekt()
        q = self.projekt()
        self.dienst.aufgaben["u"] = {"id": "u", "titel": "alt", "erledigt": False,
                                     "projekt": p["slug"], "herkunft": "projectdeck:42"}
        r = client.get(f"/api/projects/{p['id']}/aufgaben/alt/42")
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["id"], "u")
        self.assertEqual(client.get(f"/api/projects/{q['id']}/aufgaben/alt/42").status_code, 404)
        self.assertEqual(client.get(f"/api/projects/{p['id']}/aufgaben/alt/7").status_code, 404)


if __name__ == "__main__":
    unittest.main()
