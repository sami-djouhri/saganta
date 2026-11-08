from datetime import date as date_type  # Pydantic-Feld `date` verschattet sonst den Typ
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from saganta_dienst.eingang import Eingang


# ---------- Project ----------
class ProjectIn(Eingang):
    name: str = Field(..., max_length=200)
    slug: str | None = Field(None, max_length=120)  # auto aus name, wenn leer
    description: str | None = None
    type: str = "private"
    status: str = "idea"
    visibility: str = "private"
    target_visibility: str | None = None
    scheduling_mode: str = "none"
    priority: int = Field(3, ge=1, le=5)

    client_id: str | None = Field(None, max_length=100)
    domain: str | None = Field(None, max_length=200)
    repo_url: str | None = Field(None, max_length=300)
    deployment_url: str | None = Field(None, max_length=300)

    weekly_time_budget_minutes: int = Field(0, ge=0)
    minimum_weekly_minutes: int | None = Field(None, ge=0)
    maximum_weekly_minutes: int | None = Field(None, ge=0)

    next_action: str | None = Field(None, max_length=500)

    deadline_date: date_type | None = None
    deadline_type: str | None = None
    deadline_confidence: float | None = Field(None, ge=0, le=1)
    review_date: date_type | None = None
    review_interval_days: int | None = Field(None, ge=1)
    sunset_date: date_type | None = None
    public_target_date: date_type | None = None
    maintenance_interval_days: int | None = Field(None, ge=1)

    energy_level_required: str | None = None
    focus_level_required: str | None = None
    can_auto_schedule: bool = True

    promised_scope: str | None = None
    communication_notes: str | None = None
    maintenance_mode: str | None = None
    handover_status: str | None = None


class ProjectPatch(Eingang):
    name: str | None = Field(None, max_length=200)
    description: str | None = None
    type: str | None = None
    status: str | None = None
    visibility: str | None = None
    target_visibility: str | None = None
    scheduling_mode: str | None = None
    priority: int | None = Field(None, ge=1, le=5)
    client_id: str | None = None
    domain: str | None = None
    repo_url: str | None = None
    deployment_url: str | None = None
    weekly_time_budget_minutes: int | None = Field(None, ge=0)
    minimum_weekly_minutes: int | None = Field(None, ge=0)
    maximum_weekly_minutes: int | None = Field(None, ge=0)
    next_action: str | None = None
    deadline_date: date_type | None = None
    deadline_type: str | None = None
    deadline_confidence: float | None = Field(None, ge=0, le=1)
    review_date: date_type | None = None
    review_interval_days: int | None = Field(None, ge=1)
    sunset_date: date_type | None = None
    public_target_date: date_type | None = None
    maintenance_interval_days: int | None = Field(None, ge=1)
    energy_level_required: str | None = None
    focus_level_required: str | None = None
    can_auto_schedule: bool | None = None
    promised_scope: str | None = None
    communication_notes: str | None = None
    maintenance_mode: str | None = None
    handover_status: str | None = None


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner: str
    slug: str
    name: str
    description: str | None
    type: str
    status: str
    visibility: str
    target_visibility: str | None
    scheduling_mode: str
    priority: int
    client_id: str | None
    domain: str | None
    repo_url: str | None
    deployment_url: str | None
    weekly_time_budget_minutes: int
    minimum_weekly_minutes: int | None
    maximum_weekly_minutes: int | None
    next_action: str | None
    deadline_date: date_type | None
    deadline_type: str | None
    deadline_confidence: float | None
    review_date: date_type | None
    review_interval_days: int | None
    sunset_date: date_type | None
    public_target_date: date_type | None
    maintenance_interval_days: int | None
    energy_level_required: str | None
    focus_level_required: str | None
    can_auto_schedule: bool
    score: float | None
    promised_scope: str | None
    communication_notes: str | None
    maintenance_mode: str | None
    handover_status: str | None
    last_reviewed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    # Zahl der nicht erledigten Aufgaben. Die Kachel in der Uebersicht zeigt
    # sie, damit man ein Projekt mit offenen Punkten von einem ohne
    # unterscheiden kann, ohne es zu oeffnen. Vorgabe 0, weil das Feld nicht
    # aus dem ORM-Objekt kommt, sondern in der Listenroute gesetzt wird: ein
    # Aufruf je Projekt waere bei siebzehn Projekten siebzehn Nachfragen.
    open_tasks: int = 0
    #: Davon mit Prioritaet hoch (Aufgaben-Dienst, `/api/projekte/zaehlung`).
    open_high: int = 0


# ---------- Asset ----------
class AssetIn(Eingang):
    type: str = Field(..., max_length=40)
    label: str = Field(..., max_length=200)
    value: str = Field(..., max_length=500)
    url: str | None = Field(None, max_length=500)
    visibility: str = "private"


class AssetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    type: str
    label: str
    value: str
    url: str | None
    visibility: str
    created_at: datetime
    updated_at: datetime


# ---------- Milestone ----------
class MilestoneIn(Eingang):
    title: str = Field(..., max_length=300)
    description: str | None = None
    target_date: date_type | None = None
    status: str = "open"


class MilestonePatch(Eingang):
    """Teilaenderung eines Meilensteins.

    Unbekannte Feldnamen behandelt ``Eingang`` nach ``SAGANTA_FREMDFELDER``
    (melden oder ablehnen), siehe docs/FELDNAMEN_BEFUND.md.
    """

    title: str | None = Field(None, max_length=300)
    description: str | None = None
    target_date: date_type | None = None
    status: str | None = None


class MilestoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    title: str
    description: str | None
    target_date: date_type | None
    status: str
    created_at: datetime
    updated_at: datetime


# ---------- Review ----------
class ReviewIn(Eingang):
    review_date: date_type | None = None  # default = heute
    decision: str = Field(..., max_length=60)
    notes: str | None = None
    next_action: str | None = Field(None, max_length=500)
    new_status: str | None = None
    new_priority: int | None = Field(None, ge=1, le=5)
    new_weekly_budget_minutes: int | None = Field(None, ge=0)


class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    review_date: date_type
    decision: str
    notes: str | None
    next_action: str | None
    new_status: str | None
    new_priority: int | None
    new_weekly_budget_minutes: int | None
    created_at: datetime


# ---------- Weekly Focus ----------
class WeeklyFocusIn(Eingang):
    week_iso: str | None = None  # default = aktuelle Woche
    project_ids: list[int] = Field(default_factory=list, max_length=3)
    maintenance_project_ids: list[int] = Field(default_factory=list)


class WeeklyFocusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    #: ``None``, solange fuer diese Woche noch nichts gespeichert wurde. Ein
    #: GET legt seit dem 2026-10-16 nichts mehr an (siehe app/focus.py), also
    #: gibt es die Zeile erst nach dem ersten PUT. Wer hier wieder ``int``
    #: schreibt, macht aus dem Lesen zwangslaeufig ein Schreiben.
    id: int | None = None
    owner: str
    week_iso: str
    project_ids: list[int]
    maintenance_project_ids: list[int]


# ---------- Public Readiness ----------
class ReadinessItem(Eingang):
    done: bool = False
    note: str | None = None


class ReadinessPatch(Eingang):
    items: dict[str, ReadinessItem]


class ReadinessOut(BaseModel):
    project_id: int
    items: dict[str, ReadinessItem]
    completed: int
    total: int


# ---------- Shutdown-Checkliste ----------
class ShutdownPatch(Eingang):
    items: dict[str, ReadinessItem]


class ShutdownOut(BaseModel):
    project_id: int
    items: dict[str, ReadinessItem]
    completed: int
    total: int


# ---------- Deadline Risk ----------
class DeadlineRiskOut(BaseModel):
    project_id: int
    slug: str
    name: str
    deadline_date: date_type | None
    deadline_type: str | None
    days_until_deadline: int | None
    total_remaining_minutes: int
    available_scheduling_minutes: int | None
    deadline_pressure: float | None
    risk_level: str
    has_schedulable_tasks: bool
    #: Offene Aufgaben mit einem Termin in der Vergangenheit. Zaehlten bis zum
    #: 2026-10-16 ueberhaupt nicht mit, obwohl sie am Modell stehen.
    overdue_tasks: int = 0
    #: Nicht erreichte Meilensteine mit Zieldatum in der Vergangenheit.
    overdue_milestones: int = 0
    #: Offene, planbare Aufgaben ohne Aufwandsangabe. Solange es sie gibt, ist
    #: `deadline_pressure` ohne Grundlage, nicht guenstig.
    open_tasks_without_estimate: int = 0


# ---------- Rules / Findings ----------
class Finding(BaseModel):
    rule_id: str
    severity: str  # info/warn/critical
    project_id: int
    slug: str
    name: str
    message: str
    bucket: str  # dashboard-Kachel / Bereich


# ---------- AI ----------
class AISuggestOut(BaseModel):
    kind: str
    source: str  # "rules" | "llm"
    summary: str
    reasoning: list[str]  # immer die Regel-Begründung
    data: dict = Field(default_factory=dict)
