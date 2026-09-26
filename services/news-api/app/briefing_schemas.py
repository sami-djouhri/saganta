import datetime

from pydantic import BaseModel, Field


class InterestIn(BaseModel):
    tag: str
    weight: float = 1.0


class InterestOption(BaseModel):
    tag: str
    label: str


class ProfileOut(BaseModel):
    enabled: bool
    plan: str
    interests: list[dict]
    free_topics: list[str]
    feed_optout: list[str]
    length: str
    audio_enabled: bool
    voice: str
    delivery_time: str
    weather_lat: float | None = None
    weather_lon: float | None = None
    weather_place: str | None = None


class PlanOut(BaseModel):
    plan: str
    features: dict
    pro_benefits: list[str]
    is_pro: bool
    # Steuert das UI: True => „Jetzt upgraden"-Button (Stripe), False => mailto-Fallback.
    stripe_enabled: bool = False
    plan_status: str | None = None


class ProfilePatch(BaseModel):
    enabled: bool | None = None
    interests: list[InterestIn] | None = None
    free_topics: list[str] | None = None
    feed_optout: list[str] | None = None
    length: str | None = Field(None, pattern="^(kurz|mittel|lang)$")
    audio_enabled: bool | None = None
    voice: str | None = None
    delivery_time: str | None = None
    # Wetter-Ort. Koordinaten statt Ortsname, damit kein Geocoding-Dienst nötig ist;
    # der Name ist nur Anzeige-/Sprechtext.
    weather_lat: float | None = Field(None, ge=-90, le=90)
    weather_lon: float | None = Field(None, ge=-180, le=180)
    weather_place: str | None = Field(None, max_length=120)


class BriefingOut(BaseModel):
    date: datetime.date
    content: dict
    has_audio: bool
    audio_mime: str | None = None


class BriefingSummary(BaseModel):
    """Ein Eintrag der Archiv-Liste: genug zum Blättern, ohne jedes Briefing zu laden."""

    date: datetime.date
    item_count: int
    has_audio: bool
    top_title: str | None = None


class FeedbackIn(BaseModel):
    link: str
    signal: int = Field(ge=-1, le=1)


class DeliveryOut(BaseModel):
    feed_url: str | None
    # ★ Die Abruf-Adresse fuer eine Heim-Automation. Die Route dahinter gibt es
    # seit Langem, aber sie stand in keiner Antwort und damit in keiner
    # Oberflaeche: wer sie benutzen wollte, musste den Pfad aus dem Quelltext
    # ablesen. Ein Weg, den nichts sichtbar macht, wird nicht benutzt.
    json_url: str | None = None
    webhook_url: str | None
    webhook_configured: bool


class DeliveryPatch(BaseModel):
    webhook_url: str | None = None
    webhook_secret: str | None = None


class GenerateIn(BaseModel):
    with_audio: bool = False
    date: datetime.date | None = None
