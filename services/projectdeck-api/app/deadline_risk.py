"""Deadline-Risk-Engine.

Berechnet pro Projekt den Druck. Mit Kalenderdaten (verfügbare planbare Minuten
bis zur Deadline) ist die Rechnung präzise, ohne fällt sie auf
days-until-deadline zurück. Reine Funktionen → leicht testbar.

**Was hier am 2026-10-16 behoben wurde, und warum es die irreführendste
Einzelauskunft der Suite war.** Gemessen: ein Projekt mit Deadline in 5 Tagen
und einer überfälligen Aufgabe ergab ``risk_level: relaxed``,
``deadline_pressure: 0.0``, und ``/ai/deadline-plan`` sagte wörtlich "im grünen
Bereich". Zwei unabhängige Ursachen trafen zusammen:

1. **Keine Schätzung wurde als keine Arbeit gelesen.**
   ``schedulable_remaining_minutes`` summiert ``remaining_minutes`` oder
   ``estimated_minutes``; sind beide ``None``, zählt die Aufgabe 0 Minuten. Bei
   lauter unschätzten Aufgaben ist die Summe 0, der Druck 0, und 0 fällt in die
   entspannteste Schwelle. "Ich weiß nicht, wie viel Arbeit das ist" und "es ist
   keine Arbeit" sind aber verschiedene Aussagen, und nur die zweite ist
   entspannt. Dafür gibt es jetzt ``RiskLevel.UNKNOWN``.

2. **Termine an Aufgaben und Meilensteinen zählten überhaupt nicht.** Gerechnet
   wurde allein mit ``project.deadline_date``. Ein Projekt ohne eigene Deadline,
   aber mit einem neun Monate überfälligen Meilenstein, erschien im
   Deadline-Center gar nicht.

Die Rollenverteilung der Stufen bleibt: ``OVERDUE`` gehört der **eigenen**
Deadline des Projekts. Ist etwas im Projekt überfällig, das Projekt selbst aber
nicht, ist das ``CRITICAL`` -- ein echtes Signal, aber nicht dasselbe wie eine
gerissene Projekt-Deadline.
"""

from datetime import date as date_type

from .enums import RiskLevel, TaskStatus
from .models import Project
from .schemas import DeadlineRiskOut
from .util import today

#: Schwere der Stufen, aufsteigend. Gebraucht, um zu eskalieren statt zu
#: überschreiben: ein überfälliger Meilenstein darf ein ``impossible`` nicht
#: nach ``critical`` entschärfen.
#:
#: Die Reihenfolge ist dieselbe wie die Sortierung im Deadline-Center, nur
#: umgedreht. Sie steht bewusst hier und nicht dort: zwei Listen derselben
#: Ordnung laufen auseinander.
SCHWERE = {
    RiskLevel.RELAXED: 0,
    RiskLevel.UNKNOWN: 1,
    RiskLevel.WATCH: 2,
    RiskLevel.TIGHT: 3,
    RiskLevel.CRITICAL: 4,
    RiskLevel.IMPOSSIBLE: 5,
    RiskLevel.OVERDUE: 6,
}

#: Meilenstein-Zustände, die als abgeschlossen gelten. Das Modell führt
#: ``status`` als freien Text mit Vorgabe ``open``; eine Liste ist deshalb
#: ehrlicher als ein Vergleich auf einen einzigen Wert.
MEILENSTEIN_FERTIG = {"done", "erreicht", "abgeschlossen", "erledigt"}


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


def offene_ohne_schaetzung(project: Project) -> int:
    """Offene, planbare Aufgaben, deren Aufwand niemand beziffert hat.

    Sie sind der Grund, aus dem eine Summe von 0 Minuten nichts über den Druck
    sagt. Solange es sie gibt, ist die Rechnung grundlos, nicht entspannt.
    """
    return sum(
        1
        for t in project.tasks
        if t.status != TaskStatus.DONE
        and t.can_schedule
        and t.remaining_minutes is None
        and t.estimated_minutes is None
    )


def ueberfaellige_aufgaben(project: Project, stichtag: date_type | None = None) -> int:
    """Offene Aufgaben mit einem Termin in der Vergangenheit."""
    tag = stichtag or today()
    return sum(
        1
        for t in project.tasks
        if t.status != TaskStatus.DONE and t.deadline is not None and t.deadline < tag
    )


def ueberfaellige_meilensteine(project: Project, stichtag: date_type | None = None) -> int:
    """Nicht erreichte Meilensteine mit einem Zieldatum in der Vergangenheit.

    ⚠️ Meilensteine lassen sich heute nicht ändern (es gibt kein PATCH/PUT), ihr
    ``status`` bleibt also ``open``, auch wenn sie erreicht wurden. Diese Zahl
    kann deshalb zu hoch sein -- aber zu hoch ist die Richtung, in der sie
    jemanden hinsehen lässt, und das ist die bessere Richtung.
    """
    tag = stichtag or today()
    return sum(
        1
        for m in project.milestones
        if m.target_date is not None
        and m.target_date < tag
        and (m.status or "open").lower() not in MEILENSTEIN_FERTIG
    )


def _level_from_pressure(
    pressure: float | None, days_until: int | None, ohne_schaetzung: int = 0
) -> RiskLevel:
    if days_until is not None and days_until < 0:
        return RiskLevel.OVERDUE
    # Vor dem 2026-10-16 war beides hier RELAXED. Ohne Bezifferung gibt es
    # keine Grundlage, und "keine Grundlage" ist keine Entspannung.
    if pressure is None:
        return RiskLevel.UNKNOWN if ohne_schaetzung else RiskLevel.RELAXED
    if pressure == 0 and ohne_schaetzung:
        return RiskLevel.UNKNOWN
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
    unschaetzt = offene_ohne_schaetzung(project)
    spaete_aufgaben = ueberfaellige_aufgaben(project)
    spaete_meilensteine = ueberfaellige_meilensteine(project)
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

    level = _level_from_pressure(pressure, days_until, unschaetzt)

    # Eskalieren, nicht überschreiben: ein überfälliger Meilenstein darf ein
    # `impossible` nicht nach `critical` entschärfen.
    if spaete_aufgaben or spaete_meilensteine:
        if SCHWERE[RiskLevel.CRITICAL] > SCHWERE[level]:
            level = RiskLevel.CRITICAL

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
        overdue_tasks=spaete_aufgaben,
        overdue_milestones=spaete_meilensteine,
        open_tasks_without_estimate=unschaetzt,
    )
