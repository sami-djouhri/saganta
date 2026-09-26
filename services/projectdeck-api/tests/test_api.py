"""API-Smoke + Verhaltenstests via TestClient.

Hinweis: Container-Test-Image hat ggf. kein httpx → lokal im venv laufen
(feedback_kalender_test_image_httpx).
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
