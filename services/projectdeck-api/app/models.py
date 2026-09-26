from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .enums import (
    DeadlineType,
    ProjectStatus,
    ProjectType,
    SchedulingMode,
    TaskStatus,
    Visibility,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # owner = JWT sub (user-scoped); slug = stabiler Schlüssel für Kalender-Mirror.
    owner: Mapped[str] = mapped_column(String(100), index=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    type: Mapped[str] = mapped_column(String(40), default=ProjectType.PRIVATE, index=True)
    status: Mapped[str] = mapped_column(String(40), default=ProjectStatus.IDEA, index=True)
    visibility: Mapped[str] = mapped_column(String(40), default=Visibility.PRIVATE)
    target_visibility: Mapped[str | None] = mapped_column(String(40), nullable=True)
    scheduling_mode: Mapped[str] = mapped_column(String(40), default=SchedulingMode.NONE)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1 = höchste

    client_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    repo_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    deployment_url: Mapped[str | None] = mapped_column(String(300), nullable=True)

    weekly_time_budget_minutes: Mapped[int] = mapped_column(Integer, default=0)
    minimum_weekly_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    maximum_weekly_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    next_action: Mapped[str | None] = mapped_column(String(500), nullable=True)

    deadline_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    deadline_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    deadline_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    review_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sunset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    public_target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    maintenance_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    energy_level_required: Mapped[str | None] = mapped_column(String(20), nullable=True)
    focus_level_required: Mapped[str | None] = mapped_column(String(20), nullable=True)

    can_auto_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Kunden-Felder
    promised_scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    communication_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    maintenance_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    handover_status: Mapped[str | None] = mapped_column(String(40), nullable=True)

    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    tasks: Mapped[list["ProjectTask"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    assets: Mapped[list["ProjectAsset"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    milestones: Mapped[list["ProjectMilestone"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    reviews: Mapped[list["ProjectReview"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    time_blocks: Mapped[list["ProjectTimeBlock"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    readiness: Mapped["PublicReadiness | None"] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    shutdown_checklist: Mapped["ShutdownChecklist | None"] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )


class ProjectTask(Base):
    __tablename__ = "project_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default=TaskStatus.OPEN, index=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)

    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    remaining_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    can_schedule: Mapped[bool] = mapped_column(Boolean, default=True)
    can_split: Mapped[bool] = mapped_column(Boolean, default=True)
    min_block_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_block_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ID des im Kalender erzeugten Todos/Events (Idempotenz für Push/Readback).
    scheduled_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)

    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[Project] = relationship(back_populates="tasks")


class ProjectAsset(Base):
    __tablename__ = "project_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[str] = mapped_column(String(40))  # domain/repo/deployment/link/doc/...
    label: Mapped[str] = mapped_column(String(200))
    value: Mapped[str] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    visibility: Mapped[str] = mapped_column(String(40), default=Visibility.PRIVATE)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[Project] = relationship(back_populates="assets")


class ProjectMilestone(Base):
    __tablename__ = "project_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="open")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[Project] = relationship(back_populates="milestones")


class ProjectReview(Base):
    __tablename__ = "project_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    review_date: Mapped[date] = mapped_column(Date)
    decision: Mapped[str] = mapped_column(String(60))  # keep_active/pause/prepare_public/shutdown/...
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_action: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Anwendung der Entscheidung (optional): beim Anlegen auf das Project gespiegelt.
    new_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    new_priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    new_weekly_budget_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    project: Mapped[Project] = relationship(back_populates="reviews")


class ProjectTimeBlock(Base):
    """Aus dem Kalender zurückgemeldete geplante Arbeitsblöcke (ScheduledProjectBlock)."""

    __tablename__ = "project_time_blocks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("project_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    calendar_event_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    planned_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    planned_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    actual_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="planned")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[Project] = relationship(back_populates="time_blocks")


class WeeklyFocus(Base):
    """Max. 3 Hauptprojekte pro ISO-Woche (Schutz gegen Überplanung)."""

    __tablename__ = "weekly_focus"
    __table_args__ = (UniqueConstraint("owner", "week_iso", name="uq_focus_owner_week"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner: Mapped[str] = mapped_column(String(100), index=True)
    week_iso: Mapped[str] = mapped_column(String(10), index=True)  # "2026-W27"
    project_ids: Mapped[list[int]] = mapped_column(JSON, default=list)
    maintenance_project_ids: Mapped[list[int]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class PublicReadiness(Base):
    """Checklisten-Record pro Project (JSON-Map item -> {done, note})."""

    __tablename__ = "public_readiness"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True, index=True
    )
    items: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[Project] = relationship(back_populates="readiness")


class ShutdownChecklist(Base):
    """Persistenter Shutdown-Assistent pro Project (JSON-Map item -> {done, note}).

    Spiegelt PublicReadiness; löst die bisher rein statische Shutdown-Guidance ab.
    """

    __tablename__ = "shutdown_checklists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), unique=True, index=True
    )
    items: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    project: Mapped[Project] = relationship(back_populates="shutdown_checklist")
