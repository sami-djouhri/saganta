"""Briefing-Modelle (Multiuser). Alle User-Daten sind `sub`-gescoped: jede
Query MUSS nach sub filtern (Cross-Tenant-Leck-Lesson, Memory
project_saganta_auth_incidents_2026-07-06). Globale Feed-Daten (FeedItem/
FeedSource) liegen in models.py; hier nur das Personalisierungs-/Delivery-Layer.
"""
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BriefingProfile(Base):
    """Interessen + Präferenzen eines Users. Steuert die Assembly."""

    __tablename__ = "briefing_profiles"

    sub: Mapped[str] = mapped_column(String(128), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # Freemium-Tarif: "free" | "pro". Steuert Feature-Gating serverseitig.
    plan: Mapped[str] = mapped_column(String(16), default="free")
    # Stripe-Anbindung (Self-Service-Payment). Leer/None solange kein Abo gekauft.
    # Der Webhook setzt plan=pro + persistiert customer/subscription für spätere Events.
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # "active" | "canceled" | None: Spiegel des Stripe-Subscription-Status.
    plan_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # interests: [{"tag": "security", "weight": 1.5}, ...], Gewicht 0..3.
    interests: Mapped[list] = mapped_column(JSON, default=list)
    # free_topics: ["heimserver", "solaranlage"], Freitext-Themen (Keyword-Match).
    free_topics: Mapped[list] = mapped_column(JSON, default=list)
    # slugs von FeedSource, die dieser User NICHT im Briefing will.
    feed_optout: Mapped[list] = mapped_column(JSON, default=list)
    # kurz | mittel | lang → steuert briefing_max_items-Anteil.
    length: Mapped[str] = mapped_column(String(8), default="mittel")
    audio_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    voice: Mapped[str] = mapped_column(String(64), default="")  # "" => Default-Stimme
    # HH:MM (Berlin-Ortszeit), Wunschzeit: der per-User-Scheduler (briefing_sched)
    # generiert + liefert das Briefing ab dieser Uhrzeit (einmal pro Tag).
    delivery_time: Mapped[str] = mapped_column(String(5), default="06:30")
    # Ort für die Wettervorhersage im Briefing. Leer/None => Fallback aus den
    # Settings (weather_default_*). Bewusst pro User, nicht global: das Briefing
    # ist ein Multiuser-Produkt.
    weather_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    weather_place: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class UserBriefing(Base):
    """Ein generiertes Briefing pro (sub, Datum). content = strukturiertes JSON."""

    __tablename__ = "user_briefings"
    __table_args__ = (UniqueConstraint("sub", "briefing_date", name="uq_briefing_sub_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sub: Mapped[str] = mapped_column(String(128), index=True)
    briefing_date: Mapped[datetime] = mapped_column(Date, index=True)
    content: Mapped[dict] = mapped_column(JSON, default=dict)
    # Pfad zur gerenderten Audio-Datei (im audio_dir), None solange nicht/oder kein Audio.
    audio_path: Mapped[str | None] = mapped_column(String(400), nullable=True)
    audio_mime: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class BriefingFeedback(Base):
    """Like/Dislike auf einen Artikel-Link: fließt in künftiges Scoring ein."""

    __tablename__ = "briefing_feedback"
    __table_args__ = (UniqueConstraint("sub", "item_link", name="uq_feedback_sub_link"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sub: Mapped[str] = mapped_column(String(128), index=True)
    item_link: Mapped[str] = mapped_column(String(1000))
    # +1 like, -1 dislike.
    signal: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class DeliveryConfig(Base):
    """Zustell-Konfiguration pro User: Podcast-Feed-Token + optionaler Webhook."""

    __tablename__ = "briefing_delivery"

    sub: Mapped[str] = mapped_column(String(128), primary_key=True)
    # Unguessable Token für die öffentliche Podcast-Feed-URL (kein Login-Credential).
    feed_token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Opt-in Outbound-Webhook (Power-User, eigenes HA/ntfy). Leer => aus.
    webhook_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    webhook_secret: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
