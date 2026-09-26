"""Zentrale Enum-Konstanten für ProjectDeck.

Als StrEnum gehalten (Werte == DB-Strings == API-Strings), damit Modelle, Regeln
und Pydantic-Schemas dieselbe Quelle nutzen. In der DB als String gespeichert
(Pattern wie assets-api `usage_status`).
"""

from enum import StrEnum


class ProjectType(StrEnum):
    PUBLIC = "public"
    PRIVATE = "private"
    CLIENT = "client"
    INTERNAL = "internal"
    EXPERIMENT = "experiment"
    PRODUCT_CANDIDATE = "product_candidate"
    FROZEN = "frozen"
    ARCHIVED = "archived"


class ProjectStatus(StrEnum):
    IDEA = "idea"
    PLANNED = "planned"
    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    FROZEN = "frozen"
    REVIEW = "review"
    SHUTDOWN_CANDIDATE = "shutdown_candidate"
    SHUTDOWN = "shutdown"
    ARCHIVED = "archived"


class Visibility(StrEnum):
    PRIVATE = "private"
    INTERNAL_PREVIEW = "internal_preview"
    PUBLIC_PREVIEW = "public_preview"
    PUBLIC = "public"
    CLIENT_ONLY = "client_only"


class SchedulingMode(StrEnum):
    NONE = "none"
    LOW_MAINTENANCE = "low_maintenance"
    WEEKLY_FOCUS = "weekly_focus"
    DEADLINE = "deadline"
    SPRINT = "sprint"
    EMERGENCY = "emergency"


class DeadlineType(StrEnum):
    HARD = "hard"
    SOFT = "soft"
    TARGET = "target"
    REVIEW = "review"
    SUNSET = "sunset"


class TaskStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    SCHEDULED = "scheduled"
    DONE = "done"


class RiskLevel(StrEnum):
    RELAXED = "relaxed"
    WATCH = "watch"
    TIGHT = "tight"
    CRITICAL = "critical"
    IMPOSSIBLE = "impossible"
    OVERDUE = "overdue"


# Status, die als "lebend"/aktiv im Portfolio zählen (nicht eingefroren/archiviert).
LIVE_STATUSES = {
    ProjectStatus.IDEA,
    ProjectStatus.PLANNED,
    ProjectStatus.ACTIVE,
    ProjectStatus.MAINTENANCE,
    ProjectStatus.REVIEW,
}

# Status, die niemals automatisch eingeplant werden dürfen.
NO_AUTO_SCHEDULE_STATUSES = {
    ProjectStatus.FROZEN,
    ProjectStatus.SHUTDOWN_CANDIDATE,
    ProjectStatus.SHUTDOWN,
    ProjectStatus.ARCHIVED,
}

# Items der Public-Readiness-Checkliste (Reihenfolge = UI-Reihenfolge).
PUBLIC_READINESS_ITEMS = [
    "description",
    "demo_deployment",
    "privacy_imprint",
    "no_sensitive_data",
    "stable_auth",
    "error_handling",
    "monitoring",
    "screenshot_preview",
    "changelog",
    "domain_url",
]

# Items des Shutdown-Assistenten (Reihenfolge = UI-Reihenfolge).
SHUTDOWN_CHECKLIST_ITEMS = [
    "domain_decision",
    "stop_deployment",
    "archive_repo",
    "secure_backups",
    "check_dns",
    "remove_secrets",
    "save_documentation",
    "replace_public_page",
    "end_costs",
    "remove_calendar_todo_links",
]
