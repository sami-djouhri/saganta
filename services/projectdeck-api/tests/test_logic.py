"""Reine-Logik-Tests (kein DB/HTTP nötig)."""

import unittest
from datetime import timedelta
from types import SimpleNamespace

from app.deadline_risk import _level_from_pressure, compute_risk
from app.enums import ProjectStatus, ProjectType, RiskLevel, SchedulingMode
from app.rules import evaluate_project
from app.util import slugify, today, week_iso


def _task(**kw):
    base = dict(
        status="open",
        can_schedule=True,
        remaining_minutes=None,
        estimated_minutes=None,
        deadline=None,
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _meilenstein(**kw):
    base = dict(title="M", target_date=None, status="open")
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
        milestones=[],
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
        # Ohne Druckwert UND ohne unschaetzte Aufgaben ist entspannt richtig:
        # dann gibt es wirklich nichts zu tun. Mit unschaetzten Aufgaben nicht,
        # siehe TestKeineGrundlageIstNichtEntspannt.
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


class TestKeineGrundlageIstNichtEntspannt(unittest.TestCase):
    """Der gemessene Fall vom 2026-10-16, und er war die irreführendste
    Einzelauskunft der Suite.

    Ein Projekt mit Deadline in 5 Tagen und einer überfälligen Aufgabe meldete
    ``risk_level: relaxed``, ``deadline_pressure: 0.0``, und
    ``/ai/deadline-plan`` sagte wörtlich "im grünen Bereich". Ursache war nicht
    eine falsche Schwelle, sondern eine falsche Gleichsetzung: ``None`` als
    Aufwand zählte 0 Minuten, und 0 Minuten Arbeit ist die entspannteste Lage,
    die es gibt. "Ich weiß nicht, wie viel Arbeit das ist" ist aber keine
    Aussage über die Arbeitsmenge.
    """

    def test_unschaetzte_aufgaben_ergeben_unknown_statt_relaxed(self):
        p = _project(
            deadline_date=today() + timedelta(days=5),
            tasks=[_task(), _task(), _task()],
        )
        r = compute_risk(p)
        self.assertEqual(r.total_remaining_minutes, 0)
        self.assertEqual(r.open_tasks_without_estimate, 3)
        self.assertEqual(r.risk_level, RiskLevel.UNKNOWN.value)

    def test_ohne_offene_aufgaben_bleibt_es_entspannt(self):
        """Positivkontrolle: nichts zu tun ist weiterhin entspannt."""
        p = _project(
            deadline_date=today() + timedelta(days=5),
            tasks=[_task(status="done")],
        )
        self.assertEqual(compute_risk(p).risk_level, RiskLevel.RELAXED.value)

    def test_geschaetzte_aufgabe_rechnet_wie_vorher(self):
        p = _project(
            deadline_date=today() + timedelta(days=5),
            tasks=[_task(estimated_minutes=100)],
        )
        r = compute_risk(p)
        self.assertEqual(r.open_tasks_without_estimate, 0)
        self.assertAlmostEqual(r.deadline_pressure, 100 / (5 * 180))


class TestTermineInnerhalbDesProjekts(unittest.TestCase):
    """Aufgaben- und Meilenstein-Termine zählten bis zum 2026-10-16 gar nicht."""

    def test_ueberfaellige_aufgabe_eskaliert(self):
        p = _project(
            deadline_date=today() + timedelta(days=5),
            tasks=[_task(estimated_minutes=10, deadline=today() - timedelta(days=3))],
        )
        r = compute_risk(p)
        self.assertEqual(r.overdue_tasks, 1)
        self.assertEqual(r.risk_level, RiskLevel.CRITICAL.value)

    def test_ueberfaelliger_meilenstein_eskaliert_auch_ohne_projekt_deadline(self):
        """Der gemessene Bestandsfall: ein Meilenstein vom 05.01.2026.

        Ein solches Projekt erschien im Deadline-Center ueberhaupt nicht, weil
        die Route nur Projekte mit eigener ``deadline_date`` ansah.
        """
        p = _project(milestones=[_meilenstein(target_date=today() - timedelta(days=270))])
        r = compute_risk(p)
        self.assertEqual(r.overdue_milestones, 1)
        self.assertEqual(r.risk_level, RiskLevel.CRITICAL.value)

    def test_erreichter_meilenstein_zaehlt_nicht(self):
        p = _project(
            milestones=[_meilenstein(target_date=today() - timedelta(days=30), status="erreicht")]
        )
        self.assertEqual(compute_risk(p).overdue_milestones, 0)

    def test_eskalation_entschaerft_nichts(self):
        """Ein ueberfaelliger Meilenstein darf ein `impossible` nicht senken."""
        p = _project(
            deadline_date=today() + timedelta(days=3),
            tasks=[_task(estimated_minutes=5000)],
            milestones=[_meilenstein(target_date=today() - timedelta(days=10))],
        )
        r = compute_risk(p)
        self.assertEqual(r.risk_level, RiskLevel.IMPOSSIBLE.value)

    def test_gerissene_projekt_deadline_bleibt_overdue(self):
        """OVERDUE gehoert der eigenen Deadline und wird nicht nach CRITICAL gedrueckt."""
        p = _project(
            deadline_date=today() - timedelta(days=2),
            tasks=[_task(estimated_minutes=10, deadline=today() - timedelta(days=1))],
        )
        self.assertEqual(compute_risk(p).risk_level, RiskLevel.OVERDUE.value)


def _regel_projekt(**kw):
    """Ein Projekt, das `evaluate_project` vollstaendig lesen kann.

    Bewusst eine eigene Fabrik neben `_project`: jene deckt die Felder der
    Risiko-Rechnung, diese die der Portfolio-Regeln. Eine gemeinsame Fabrik mit
    allen Feldern beider waere die Stelle, an der ein Test gruen bleibt, weil er
    ein Feld mitbringt, das der echte Aufrufer nie setzt.
    """
    base = dict(
        id=1,
        slug="p",
        name="P",
        status=ProjectStatus.ACTIVE,
        type=ProjectType.INTERNAL,
        visibility="private",
        target_visibility=None,
        scheduling_mode=SchedulingMode.NONE,
        weekly_time_budget_minutes=0,
        next_action="etwas tun",
        can_auto_schedule=True,
        deadline_date=None,
        deadline_type=None,
        sunset_date=None,
        review_date=None,
        review_interval_days=None,
        last_reviewed_at=None,
        readiness=None,
        tasks=[],
        milestones=[],
    )
    base.update(kw)
    return SimpleNamespace(**base)


class TestBudgetRegelHaengtAmPlanungsmodus(unittest.TestCase):
    """Beide Richtungen, sonst baut man eine dauerhaft stumme Regel.

    Die Regel `active_zero_budget` feuerte bis zum 2026-10-24 auf jedem aktiven
    Projekt, weil sie allein am Status hing: gemessen hatten alle 33 Projekte
    `scheduling_mode: none` und Budget 0. Sie haengt jetzt am Modus.
    """

    def _ids(self, p):
        return {f.rule_id for f in evaluate_project(p)}

    def test_ohne_planungsmodus_kein_befund(self):
        """Budget 0 bei `none` ist der stimmige Zustand, nicht eine Auslassung."""
        self.assertNotIn("active_zero_budget", self._ids(_regel_projekt()))

    def test_mit_planungsmodus_und_ohne_budget_feuert(self):
        """Wer einen Modus setzt, will einplanen -- dann ist 0 ein Widerspruch."""
        p = _regel_projekt(scheduling_mode=SchedulingMode.WEEKLY_FOCUS)
        self.assertIn("active_zero_budget", self._ids(p))

    def test_mit_planungsmodus_und_budget_kein_befund(self):
        """Gegenprobe: mit Budget schweigt sie wieder."""
        p = _regel_projekt(
            scheduling_mode=SchedulingMode.WEEKLY_FOCUS, weekly_time_budget_minutes=120
        )
        self.assertNotIn("active_zero_budget", self._ids(p))

    def test_nicht_aktiv_feuert_nie(self):
        """Ein eingefrorenes Projekt mit Modus bleibt aussen vor."""
        p = _regel_projekt(
            status=ProjectStatus.FROZEN, scheduling_mode=SchedulingMode.WEEKLY_FOCUS
        )
        self.assertNotIn("active_zero_budget", self._ids(p))

    def test_die_uebrigen_regeln_bleiben_unberuehrt(self):
        """Positivkontrolle: die Nachbarregel feuert noch, der Aufruf traegt."""
        p = _regel_projekt(next_action=None)
        self.assertIn("active_without_next_action", self._ids(p))
