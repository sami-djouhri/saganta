"""Deklarative Portfolio-Regeln.

Jede Regel liefert strukturierte, erklärbare Findings (rule_id + Begründung +
Ziel-Bucket). Das ist sowohl die Grundlage für Dashboard-Warnungen als auch für
die KI-Empfehlungen (die nie ohne diese Begründung antworten).
"""

from .deadline_risk import has_schedulable_tasks
from .enums import (
    DeadlineType,
    ProjectStatus,
    ProjectType,
    Visibility,
)
from .models import Project
from .schemas import Finding
from .util import today


def _f(rule_id: str, severity: str, p: Project, message: str, bucket: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        severity=severity,
        project_id=p.id,
        slug=p.slug,
        name=p.name,
        message=message,
        bucket=bucket,
    )


def evaluate_project(p: Project) -> list[Finding]:
    out: list[Finding] = []

    # Deadline gesetzt, aber keine planbaren Tasks.
    if p.deadline_date and not has_schedulable_tasks(p):
        out.append(
            _f(
                "deadline_without_schedulable_tasks",
                "warn",
                p,
                "Deadline gesetzt, aber kein planbarer Task, der Kalender kann nichts einplanen.",
                "deadline_risks",
            )
        )

    # Active, aber keine nächste Aktion.
    if p.status == ProjectStatus.ACTIVE and not (p.next_action and p.next_action.strip()):
        out.append(
            _f(
                "active_without_next_action",
                "warn",
                p,
                "Aktiv, aber keine nächste Aktion definiert.",
                "without_next_action",
            )
        )

    # Active, aber Wochenbudget 0.
    if p.status == ProjectStatus.ACTIVE and p.weekly_time_budget_minutes == 0:
        out.append(
            _f(
                "active_zero_budget",
                "warn",
                p,
                "Aktiv, aber Wochen-Zeitbudget ist 0 Minuten.",
                "blocked",
            )
        )

    # Frozen darf nie automatisch geplant werden (informativer Guard).
    if p.status == ProjectStatus.FROZEN and p.can_auto_schedule:
        out.append(
            _f(
                "frozen_but_auto_schedule",
                "info",
                p,
                "Eingefroren, aber can_auto_schedule ist aktiv: wird beim Planen ignoriert.",
                "frozen",
            )
        )

    # Shutdown-Kandidat → Shutdown-Bereich. Überfälliges Sunset-Date eskaliert.
    sunset_overdue = bool(p.sunset_date and p.sunset_date <= today())
    if p.status == ProjectStatus.SHUTDOWN_CANDIDATE or p.sunset_date:
        out.append(
            _f(
                "shutdown_candidate",
                "warn" if sunset_overdue else "info",
                p,
                (
                    "Sunset-Date erreicht/überschritten: Abschaltung jetzt entscheiden."
                    if sunset_overdue
                    else "Abschaltung prüfen (Shutdown-Kandidat oder Sunset-Date gesetzt)."
                ),
                "shutdown",
            )
        )

    # Client + Hard Deadline → Deadline-Center-Top.
    if p.type == ProjectType.CLIENT and p.deadline_type == DeadlineType.HARD:
        out.append(
            _f(
                "client_hard_deadline",
                "critical",
                p,
                "Kundenprojekt mit harter Deadline: hat Vorrang im Deadline Center.",
                "deadline_risks",
            )
        )

    # Soll public werden, aber keine Public Readiness.
    wants_public = p.target_visibility in {Visibility.PUBLIC_PREVIEW, Visibility.PUBLIC}
    if wants_public:
        ready = p.readiness
        done = (
            sum(1 for v in (ready.items or {}).values() if isinstance(v, dict) and v.get("done"))
            if ready
            else 0
        )
        if done == 0:
            out.append(
                _f(
                    "public_target_without_readiness",
                    "info",
                    p,
                    "Soll public werden, aber Public-Readiness ist leer.",
                    "public_pipeline",
                )
            )

    # Review fällig: entweder konkretes review_date erreicht oder Intervall überschritten.
    not_terminal = p.status not in {ProjectStatus.ARCHIVED, ProjectStatus.SHUTDOWN}
    review_due_reason: str | None = None
    if p.review_date and p.review_date <= today():
        review_due_reason = "Review-Date erreicht: Entscheidung fällig (aktiv lassen, pausieren, public, abschalten?)."
    elif p.review_interval_days:
        last = p.last_reviewed_at.date() if p.last_reviewed_at else None
        if last is None or (today() - last).days >= p.review_interval_days:
            review_due_reason = "Review überfällig (review_interval_days überschritten)."
    if review_due_reason and not_terminal:
        out.append(_f("review_overdue", "warn", p, review_due_reason, "without_review"))

    return out


def evaluate_all(projects: list[Project]) -> list[Finding]:
    out: list[Finding] = []
    for p in projects:
        out.extend(evaluate_project(p))
    return out
