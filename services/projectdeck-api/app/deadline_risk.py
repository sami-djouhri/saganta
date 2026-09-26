"""Deadline-Risk-Engine.

Berechnet pro Projekt mit Deadline den Druck. Mit Kalenderdaten (verfügbare
planbare Minuten bis zur Deadline) ist die Rechnung präzise, ohne fällt sie auf
days-until-deadline zurück. Reine Funktionen → leicht testbar.
"""

from .enums import RiskLevel, TaskStatus
from .models import Project
from .schemas import DeadlineRiskOut
from .util import today


def schedulable_remaining_minutes(project: Project) -> int:
    """Σ verbleibende Minuten offener, planbarer Tasks (Fallback estimated)."""
    total = 0
    for t in project.tasks:
        if t.status == TaskStatus.DONE:
            continue
        if not t.can_schedule:
            continue
        mins = t.remaining_minutes if t.remaining_minutes is not None else t.estimated_minutes
        if mins:
            total += mins
    return total


def has_schedulable_tasks(project: Project) -> bool:
    return any(
        t.can_schedule and t.status != TaskStatus.DONE for t in project.tasks
    )


def _level_from_pressure(pressure: float | None, days_until: int | None) -> RiskLevel:
    if days_until is not None and days_until < 0:
        return RiskLevel.OVERDUE
    if pressure is None:
        return RiskLevel.RELAXED
    if pressure > 1.5:
        return RiskLevel.IMPOSSIBLE
    if pressure > 1.0:
        return RiskLevel.CRITICAL
    if pressure > 0.75:
        return RiskLevel.TIGHT
    if pressure > 0.4:
        return RiskLevel.WATCH
    return RiskLevel.RELAXED


def compute_risk(
    project: Project, available_minutes: int | None = None
) -> DeadlineRiskOut:
    remaining = schedulable_remaining_minutes(project)
    days_until: int | None = None
    if project.deadline_date:
        days_until = (project.deadline_date - today()).days

    pressure: float | None = None
    if project.deadline_date:
        if available_minutes is not None and available_minutes > 0:
            pressure = remaining / available_minutes
        elif days_until is not None and days_until > 0:
            # Grob: ohne Kalenderdaten Minuten gegen verbleibende Tage.
            pressure = remaining / (days_until * 1.0)
            # In "Tag-Einheiten" normiert auf eine realistische Tageskapazität (180 min/Tag),
            # damit der Wert mit der kalendergestützten Variante vergleichbar bleibt.
            capacity = days_until * 180
            pressure = remaining / capacity if capacity else None
        elif days_until is not None and days_until <= 0:
            pressure = float("inf") if remaining > 0 else 0.0

    level = _level_from_pressure(pressure, days_until)

    return DeadlineRiskOut(
        project_id=project.id,
        slug=project.slug,
        name=project.name,
        deadline_date=project.deadline_date,
        deadline_type=project.deadline_type,
        days_until_deadline=days_until,
        total_remaining_minutes=remaining,
        available_scheduling_minutes=available_minutes,
        deadline_pressure=None if pressure == float("inf") else pressure,
        risk_level=level.value,
        has_schedulable_tasks=has_schedulable_tasks(project),
    )
