"""API-Smoke + Verhaltenstests via TestClient.

Hinweis: Container-Test-Image hat ggf. kein httpx → lokal im venv laufen
.
"""

import os
import tempfile
import unittest

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mktemp(suffix='.db')}")
os.environ.setdefault("JWT_SECRET", "test-secret")

from fastapi.testclient import TestClient  # noqa: E402

from app.auth import Me, verify_jwt  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402

app.dependency_overrides[verify_jwt] = lambda: Me(sub="tester", email="t@t")
init_db()
client = TestClient(app)


class TestHealth(unittest.TestCase):
    def test_healthz(self):
        self.assertEqual(client.get("/healthz").status_code, 200)

    def test_ready(self):
        r = client.get("/health/ready")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["db"], "ok")


class TestProjectLifecycle(unittest.TestCase):
    def test_create_and_acceptance_examples(self):
        # djouhri.de als Public Project
        r = client.post(
            "/api/projects",
            json={"name": "Djouhri.de", "type": "public", "visibility": "public"},
        )
        self.assertEqual(r.status_code, 201, r.text)
        dj = r.json()
        self.assertEqual(dj["slug"], "djouhri-de")

        # marktwatch als Private Product Candidate
        client.post(
            "/api/projects",
            json={"name": "Marktwatch", "type": "product_candidate", "visibility": "private"},
        )
        # edel-pralinen als Client mit Hard Deadline
        ed = client.post(
            "/api/projects",
            json={
                "name": "edel-pralinen",
                "type": "client",
                "client_id": "edel-pralinen",
                "deadline_date": "2026-07-15",
                "deadline_type": "hard",
            },
        ).json()
        # planbarer Task → erscheint im Deadline Center
        client.post(
            f"/api/projects/{ed['id']}/tasks",
            json={"title": "Shop-Update", "estimated_minutes": 240, "can_schedule": True},
        )

        dc = client.get("/api/deadline-center").json()
        self.assertTrue(any(x["slug"] == "edel-pralinen" for x in dc))
        # Client+Hard steht vorne
        self.assertEqual(dc[0]["slug"], "edel-pralinen")

    def test_slug_uniqueness(self):
        a = client.post("/api/projects", json={"name": "Doppelt"}).json()
        b = client.post("/api/projects", json={"name": "Doppelt"}).json()
        self.assertNotEqual(a["slug"], b["slug"])

    def test_review_applies_decision(self):
        p = client.post("/api/projects", json={"name": "Review-Test", "status": "active"}).json()
        r = client.post(
            f"/api/projects/{p['id']}/reviews",
            json={"decision": "pause", "new_status": "frozen", "new_priority": 4},
        )
        self.assertEqual(r.status_code, 201, r.text)
        updated = client.get(f"/api/projects/{p['id']}").json()
        self.assertEqual(updated["status"], "frozen")
        self.assertEqual(updated["priority"], 4)
        self.assertIsNotNone(updated["last_reviewed_at"])

    def test_frozen_not_auto_schedulable(self):
        p = client.post("/api/projects", json={"name": "Frozen", "status": "frozen"}).json()
        client.post(
            f"/api/projects/{p['id']}/tasks",
            json={"title": "x", "estimated_minutes": 60},
        )
        r = client.post(f"/api/projects/{p['id']}/plan")
        self.assertEqual(r.status_code, 409)

    def test_assets_roundtrip(self):
        p = client.post("/api/projects", json={"name": "Assets-Test"}).json()
        a = client.post(
            f"/api/projects/{p['id']}/assets",
            json={"type": "domain", "label": "Domain", "value": "djouhri.de"},
        )
        self.assertEqual(a.status_code, 201)
        lst = client.get(f"/api/projects/{p['id']}/assets").json()
        self.assertEqual(len(lst), 1)

    def test_readiness_checklist(self):
        p = client.post("/api/projects", json={"name": "Ready-Test"}).json()
        r = client.put(
            f"/api/projects/{p['id']}/readiness",
            json={"items": {"description": {"done": True, "note": "ok"}}},
        ).json()
        self.assertEqual(r["completed"], 1)
        self.assertEqual(r["total"], 10)

    def test_shutdown_checklist_persists(self):
        p = client.post(
            "/api/projects", json={"name": "Sunset-Test", "status": "shutdown_candidate"}
        ).json()
        # Default: alle Items vorhanden, nichts erledigt
        before = client.get(f"/api/projects/{p['id']}/shutdown").json()
        self.assertEqual(before["completed"], 0)
        self.assertEqual(before["total"], 10)
        # Setzen + persistieren
        r = client.put(
            f"/api/projects/{p['id']}/shutdown",
            json={"items": {"stop_deployment": {"done": True, "note": "compose down"}}},
        ).json()
        self.assertEqual(r["completed"], 1)
        # Readback bestätigt Persistenz
        after = client.get(f"/api/projects/{p['id']}/shutdown").json()
        self.assertTrue(after["items"]["stop_deployment"]["done"])


class TestAuth(unittest.TestCase):
    def test_missing_header_is_401_not_422(self):
        # Ohne dependency_override: echter verify_jwt greift.
        from app.auth import verify_jwt as real_verify

        app.dependency_overrides.pop(verify_jwt, None)
        try:
            r = client.get("/api/projects")
            self.assertEqual(r.status_code, 401, r.text)
        finally:
            app.dependency_overrides[verify_jwt] = lambda: Me(sub="tester", email="t@t")
        _ = real_verify  # nur Import-Sicherung


class TestRules(unittest.TestCase):
    def test_review_date_due_triggers_finding(self):
        p = client.post(
            "/api/projects",
            json={"name": "ReviewDate", "status": "active", "review_date": "2020-01-01"},
        ).json()
        fs = client.get("/api/findings").json()
        mine = [f for f in fs if f["project_id"] == p["id"]]
        self.assertTrue(any(f["rule_id"] == "review_overdue" for f in mine))

    def test_sunset_overdue_escalates_to_warn(self):
        p = client.post(
            "/api/projects", json={"name": "Sunset-Past", "sunset_date": "2020-01-01"}
        ).json()
        fs = client.get("/api/findings").json()
        sc = [f for f in fs if f["project_id"] == p["id"] and f["rule_id"] == "shutdown_candidate"]
        self.assertTrue(sc and sc[0]["severity"] == "warn")


class TestMeilensteineSindKeineEinbahnstrasse(unittest.TestCase):
    """Bis zum 2026-10-16 gab es GET, POST und DELETE, aber kein PATCH.

    ``status`` blieb damit fuer immer ``open``, auch wenn der Meilenstein
    erreicht war, und ``description`` liess sich nach dem Anlegen nicht setzen.
    Wer etwas aendern wollte, musste loeschen und neu anlegen -- und verlor das
    Anlege-Datum. Seit derselben Runde zaehlt der Deadline-Center ueberfaellige
    Meilensteine; ohne einen Weg, einen als erreicht zu markieren, koennte diese
    Zahl nur steigen, und eine nicht abstellbare Warnung wird ignoriert.
    """

    def _projekt_und_meilenstein(self):
        pid = client.post("/api/projects", json={"name": "MS-Test"}).json()["id"]
        m = client.post(
            f"/api/projects/{pid}/milestones",
            json={"title": "Erster Wurf", "target_date": "2026-01-05"},
        )
        self.assertEqual(m.status_code, 201, m.text)
        return pid, m.json()

    def test_status_laesst_sich_setzen(self):
        pid, m = self._projekt_und_meilenstein()
        self.assertEqual(m["status"], "open")
        r = client.patch(
            f"/api/projects/{pid}/milestones/{m['id']}", json={"status": "erreicht"}
        )
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["status"], "erreicht")

    def test_nicht_mitgeschickte_felder_bleiben_stehen(self):
        """``exclude_unset``: ein PATCH ist kein Ersetzen."""
        pid, m = self._projekt_und_meilenstein()
        r = client.patch(
            f"/api/projects/{pid}/milestones/{m['id']}", json={"description": "Notiz"}
        )
        self.assertEqual(r.json()["title"], "Erster Wurf")
        self.assertEqual(r.json()["target_date"], "2026-01-05")
        self.assertEqual(r.json()["description"], "Notiz")

    def test_fremdes_projekt_ist_nicht_erreichbar(self):
        pid, m = self._projekt_und_meilenstein()
        r = client.patch(f"/api/projects/{pid + 99999}/milestones/{m['id']}", json={"status": "x"})
        self.assertIn(r.status_code, (403, 404), r.text)

    def test_meilenstein_eines_anderen_projekts_ist_nicht_erreichbar(self):
        """Die ID allein darf nicht reichen: geprueft wird auch die Zugehoerigkeit."""
        pid, m = self._projekt_und_meilenstein()
        anderes = client.post("/api/projects", json={"name": "MS-Test-2"}).json()["id"]
        r = client.patch(
            f"/api/projects/{anderes}/milestones/{m['id']}", json={"status": "erreicht"}
        )
        self.assertEqual(r.status_code, 404, r.text)

    def test_erreichter_meilenstein_zaehlt_im_deadline_center_nicht_mehr(self):
        """Der Kreis schliesst sich: die Warnung laesst sich abstellen."""
        pid, m = self._projekt_und_meilenstein()
        drin = [z for z in client.get("/api/deadline-center").json() if z["project_id"] == pid]
        self.assertEqual(len(drin), 1, "ueberfaelliger Meilenstein fehlt im Deadline-Center")
        self.assertEqual(drin[0]["overdue_milestones"], 1)

        client.patch(f"/api/projects/{pid}/milestones/{m['id']}", json={"status": "erreicht"})
        danach = [z for z in client.get("/api/deadline-center").json() if z["project_id"] == pid]
        self.assertEqual(danach, [], "erreichter Meilenstein warnt weiter")


class TestFokusLesenSchreibtNicht(unittest.TestCase):
    """Ein GET darf nichts anlegen.

    ``GET /api/focus`` rief bis zum 2026-10-16 ``get_or_create``. Gemessen am
    laufenden Dienst: ein Konto, das die Seite nur geoeffnet hatte, meldete
    danach ``summe: 1`` in seiner eigenen Loeschvorschau. Das ist eine falsche
    Antwort auf die Frage "was ist ueber mich gespeichert", und die Frage ist
    der Grund, aus dem es den Loeschweg ueberhaupt gibt.

    Geprueft wird nicht die Antwort des GET, sondern der **Bestand danach** --
    die Antwort sah vorher und sieht nachher gleich aus, bis auf die ``id``.
    """

    def _zeilen(self) -> int:
        from app.db import SessionLocal
        from app.models import WeeklyFocus

        db = SessionLocal()
        try:
            return db.query(WeeklyFocus).filter(WeeklyFocus.owner == "tester").count()
        finally:
            db.close()

    def test_lesen_legt_keine_zeile_an(self):
        vorher = self._zeilen()
        r = client.get("/api/focus", params={"week": "2019-W01"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNone(r.json()["id"], "ungespeichert, also ohne id")
        self.assertEqual(r.json()["project_ids"], [])
        self.assertEqual(self._zeilen(), vorher, "ein GET hat geschrieben")

    def test_schreiben_legt_eine_zeile_an(self):
        """Positivkontrolle: der schreibende Weg legt weiterhin an."""
        vorher = self._zeilen()
        r = client.put("/api/focus", json={"project_ids": [], "week_iso": "2019-W02"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertIsNotNone(r.json()["id"])
        self.assertEqual(self._zeilen(), vorher + 1)

    def test_nach_dem_schreiben_liest_das_get_die_zeile(self):
        client.put("/api/focus", json={"project_ids": [], "week_iso": "2019-W03"})
        r = client.get("/api/focus", params={"week": "2019-W03"})
        self.assertIsNotNone(r.json()["id"])


class TestWeeklyFocus(unittest.TestCase):
    def test_max_three(self):
        ids = [
            client.post("/api/projects", json={"name": f"F{i}"}).json()["id"] for i in range(4)
        ]
        ok = client.put("/api/focus", json={"project_ids": ids[:3]})
        self.assertEqual(ok.status_code, 200, ok.text)
        too_many = client.put("/api/focus", json={"project_ids": ids})
        self.assertEqual(too_many.status_code, 422)


class TestDashboard(unittest.TestCase):
    def test_dashboard_shape(self):
        d = client.get("/api/dashboard").json()
        self.assertIn("tiles", d)
        self.assertIn("counts", d)
        self.assertIn("client_projects", d["tiles"])


if __name__ == "__main__":
    unittest.main()
