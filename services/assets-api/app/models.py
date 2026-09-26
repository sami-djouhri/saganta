from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (
        # ★ owner_sub gehoert in den Schluessel, nicht nur in die Tabelle. Ohne ihn
        # teilen sich zwei Nutzer, die dasselbe Lager-Element spiegeln, eine Zeile:
        # der Sync des einen ueberschreibt die Werte des anderen, und zwar ohne
        # Fehler, weil die Zeile ja existiert.
        UniqueConstraint("owner_sub", "source", "source_id", name="uq_asset_owner_source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Mandantenschluessel (better-auth-sub). Jede Abfrage filtert darauf; es gibt
    # keinen Lesepfad ohne ihn.
    owner_sub: Mapped[str] = mapped_column(String(128), index=True)
    # 'saganta' = nativ erfasst; 'lager-electronics' = Mirror aus lager
    source: Mapped[str] = mapped_column(String(50), default="saganta", index=True)
    source_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 'critical' / 'homelab_active' / 'daily_use' / 'reserve' / 'unused'
    usage_status: Mapped[str] = mapped_column(String(50), default="reserve", index=True)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    purchase_price_eur: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Markt-Cache: gesetzt durch /api/assets/{id}/market refresh
    market_value_eur: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_value_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
