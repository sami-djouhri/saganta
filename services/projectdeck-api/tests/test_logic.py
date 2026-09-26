"""Reine-Logik-Tests (kein DB/HTTP nötig)."""

import unittest
from datetime import timedelta
from types import SimpleNamespace

from app.deadline_risk import _level_from_pressure, compute_risk
from app.enums import RiskLevel
from app.util import slugify, today, week_iso


def _task(**kw):
    base = dict(
        status="open", can_schedule=True, remaining_minutes=None, estimated_minutes=None
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _project(**kw):
    base = dict(
        id=1,
        slug="p",
        name="P",
        deadline_date=None,
        deadline_type=None,
        tasks=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestUtil(unittest.TestCase):
    def test_slugify(self):
        self.assertEqual(slugify("Djouhri.de Portfolio!"), "djouhri-de-portfolio")
        self.assertEqual(slugify("   "), "projekt")

    def test_week_iso_format(self):
        self.assertRegex(week_iso(), r"^\d{4}-W\d{2}$")


class TestRiskLevel(unittest.TestCase):
    def test_overdue_beats_everything(self):
        self.assertEqual(_level_from_pressure(0.1, -1), RiskLevel.OVERDUE)

    def test_thresholds(self):
        self.assertEqual(_level_from_pressure(None, 5), RiskLevel.RELAXED)
        self.assertEqual(_level_from_pressure(0.3, 5), RiskLevel.RELAXED)
        self.assertEqual(_level_from_pressure(0.5, 5), RiskLevel.WATCH)
        self.assertEqual(_level_from_pressure(0.8, 5), RiskLevel.TIGHT)
        self.assertEqual(_level_from_pressure(1.2, 5), RiskLevel.CRITICAL)
        self.assertEqual(_level_from_pressure(2.0, 5), RiskLevel.IMPOSSIBLE)


class TestComputeRisk(unittest.TestCase):
    def test_no_deadline_is_relaxed(self):
        r = compute_risk(_project())
        self.assertEqual(r.risk_level, "relaxed")
        self.assertEqual(r.total_remaining_minutes, 0)

    def test_remaining_uses_estimated_fallback(self):
        p = _project(
            deadline_date=today() + timedelta(days=10),
            tasks=[_task(estimated_minutes=600), _task(remaining_minutes=120)],
        )
        r = compute_risk(p)
        self.assertEqual(r.total_remaining_minutes, 720)
        self.assertTrue(r.has_schedulable_tasks)

    def test_done_and_unschedulable_excluded(self):
        p = _project(
            deadline_date=today() + timedelta(days=5),
            tasks=[
                _task(estimated_minutes=600, status="done"),
                _task(estimated_minutes=300, can_schedule=False),
                _task(estimated_minutes=60),
            ],
        )
        r = compute_risk(p)
        self.assertEqual(r.total_remaining_minutes, 60)

    def test_available_minutes_drives_pressure(self):
        p = _project(
            deadline_date=today() + timedelta(days=3),
            tasks=[_task(remaining_minutes=300)],
        )
        r = compute_risk(p, available_minutes=200)
        self.assertAlmostEqual(r.deadline_pressure, 1.5)
        self.assertEqual(r.risk_level, "critical")

    def test_overdue_with_remaining(self):
        p = _project(
            deadline_date=today() - timedelta(days=2),
            tasks=[_task(remaining_minutes=100)],
        )
        r = compute_risk(p)
        self.assertEqual(r.risk_level, "overdue")


if __name__ == "__main__":
    unittest.main()
