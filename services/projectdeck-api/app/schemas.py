from datetime import date as date_type  # Pydantic-Feld `date` verschattet sonst den Typ
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------- Project ----------
class ProjectIn(BaseModel):
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


class ProjectPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
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


# ---------- Task ----------
class TaskIn(BaseModel):
    title: str = Field(..., max_length=300)
    description: str | None = None
    status: str = "open"
    priority: int = Field(3, ge=1, le=5)
    estimated_minutes: int | None = Field(None, ge=0)
    remaining_minutes: int | None = Field(None, ge=0)
    deadline: date_type | None = None
    can_schedule: bool = True
    can_split: bool = True
    min_block_minutes: int | None = Field(None, ge=0)
    max_block_minutes: int | None = Field(None, ge=0)


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str | None = Field(None, max_length=300)
    description: str | None = None
    status: str | None = None
    priority: int | None = Field(None, ge=1, le=5)
    estimated_minutes: int | None = Field(None, ge=0)
    remaining_minutes: int | None = Field(None, ge=0)
    deadline: date_type | None = None
    can_schedule: bool | None = None
    can_split: bool | None = None
    min_block_minutes: int | None = Field(None, ge=0)
    max_block_minutes: int | None = Field(None, ge=0)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    title: str
    description: str | None
    status: str
    priority: int
    estimated_minutes: int | None
    remaining_minutes: int | None
    deadline: date_type | None
    can_schedule: bool
    can_split: bool
    min_block_minutes: int | None
    max_block_minutes: int | None
    scheduled_event_id: str | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


# ---------- Asset ----------
class AssetIn(BaseModel):
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
class MilestoneIn(BaseModel):
    title: str = Field(..., max_length=300)
    description: str | None = None
    target_date: date_type | None = None
    status: str = "open"


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
class ReviewIn(BaseModel):
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


# ---------- TimeBlock ----------
class TimeBlockOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    project_id: int
    task_id: int | None
    calendar_event_id: str | None
    planned_start: datetime | None
    planned_end: datetime | None
    actual_minutes: int | None
    status: str


# ---------- Weekly Focus ----------
class WeeklyFocusIn(BaseModel):
    week_iso: str | None = None  # default = aktuelle Woche
    project_ids: list[int] = Field(default_factory=list, max_length=3)
    maintenance_project_ids: list[int] = Field(default_factory=list)


class WeeklyFocusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    owner: str
    week_iso: str
    project_ids: list[int]
    maintenance_project_ids: list[int]


# ---------- Public Readiness ----------
class ReadinessItem(BaseModel):
    done: bool = False
    note: str | None = None


class ReadinessPatch(BaseModel):
    items: dict[str, ReadinessItem]


class ReadinessOut(BaseModel):
    project_id: int
    items: dict[str, ReadinessItem]
    completed: int
    total: int


# ---------- Shutdown-Checkliste ----------
class ShutdownPatch(BaseModel):
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


# ---------- Rules / Findings ----------
class Finding(BaseModel):
    rule_id: str
    severity: str  # info/warn/critical
    project_id: int
    slug: str
    name: str
    message: str
    bucket: str  # dashboard-Kachel / Bereich


# ---------- Kalender-Integration ----------
class WorkCandidateOut(BaseModel):
    project_id: int
    task_id: int | None
    slug: str
    title: str
    estimated_minutes: int
    deadline: date_type | None
    priority: int
    scheduling_mode: str
    earliest_start: date_type | None = None
    latest_finish: date_type | None = None
    min_block_minutes: int | None = None
    max_block_minutes: int | None = None
    energy_required: str | None = None
    focus_required: str | None = None
    can_split: bool = True
    can_move: bool = True


class PlanResult(BaseModel):
    project_id: int
    pushed: int
    scheduled_blocks: int
    auto_plan_triggered: bool
    detail: str


class WorkLogIn(BaseModel):
    task_id: int | None = None
    calendar_event_id: str | None = None
    planned_minutes: int | None = None
    actual_minutes: int = Field(..., ge=0)
    completed: bool = False
    notes: str | None = None


# ---------- AI ----------
class AISuggestOut(BaseModel):
    kind: str
    source: str  # "rules" | "llm"
    summary: str
    reasoning: list[str]  # immer die Regel-Begründung
    data: dict = Field(default_factory=dict)
