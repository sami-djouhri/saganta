from datetime import date, datetime

from pydantic import BaseModel, Field


class AssetIn(BaseModel):
    name: str = Field(..., max_length=200)
    category: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=100)
    usage_status: str = Field("reserve", max_length=50)
    purchase_date: date | None = None
    purchase_price_eur: float | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=500)


class AssetPatch(BaseModel):
    name: str | None = Field(None, max_length=200)
    category: str | None = Field(None, max_length=100)
    location: str | None = Field(None, max_length=100)
    usage_status: str | None = Field(None, max_length=50)
    purchase_date: date | None = None
    purchase_price_eur: float | None = Field(None, ge=0)
    notes: str | None = Field(None, max_length=500)


class AssetOut(BaseModel):
    id: int
    source: str
    source_id: str | None
    name: str
    category: str | None
    location: str | None
    usage_status: str
    purchase_date: date | None
    purchase_price_eur: float | None
    market_value_eur: float | None
    market_value_at: datetime | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    # Verkaufsempfehlung (abgeleitet, nicht persistiert)
    resale_recommended: bool = False
    resale_reason: str | None = None


class SyncResult(BaseModel):
    source: str
    added: int
    updated: int
    skipped: int


class MarketUpdate(BaseModel):
    asset_id: int
    market_value_eur: float | None
    market_value_at: datetime | None
    samples: int
