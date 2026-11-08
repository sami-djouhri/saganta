from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _leer_zu_none(v: object) -> object:
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


class Jahrestag(BaseModel):
    bezeichnung: str = Field(min_length=1, max_length=80)
    datum: date

    @field_validator("bezeichnung", mode="before")
    @classmethod
    def _trimmen(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class TerminVerweis(BaseModel):
    ref: str = Field(min_length=1, max_length=120)
    label: str = Field(default="", max_length=300)
    start: str | None = Field(default=None, max_length=40)


class _Felder(BaseModel):
    telefon: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=300)
    adresse: str | None = Field(default=None, max_length=300)
    geburtstag: date | None = None
    jahrestage: list[Jahrestag] | None = Field(default=None, max_length=20)
    gruppe: str | None = Field(default=None, max_length=60)
    termine: list[TerminVerweis] | None = Field(default=None, max_length=50)
    notiz: str | None = Field(default=None, max_length=10000)

    @field_validator("telefon", "email", "adresse", "gruppe", "notiz", mode="before")
    @classmethod
    def _leer(cls, v: object) -> object:
        return _leer_zu_none(v)


class KontaktNeu(_Felder):
    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class KontaktAenderung(_Felder):
    """Nur gesetzte Felder werden geschrieben; ``null`` leert ein Feld."""
    name: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def _name(cls, v: object) -> object:
        return v.strip() if isinstance(v, str) else v


class KontaktAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    telefon: str | None = None
    email: str | None = None
    adresse: str | None = None
    geburtstag: date | None = None
    jahrestage: list[Jahrestag] = []
    gruppe: str | None = None
    termine: list[TerminVerweis] = []
    notiz: str | None = None
    herkunft: str | None = None
    geloescht_am: datetime | None = None
    erstellt_am: datetime
    geaendert_am: datetime

    @field_validator("jahrestage", "termine", mode="before")
    @classmethod
    def _liste(cls, v: object) -> object:
        return v or []


class KontaktListe(BaseModel):
    kontakte: list[KontaktAus]
    #: ``False``, wenn der Kalender den letzten Stand noch nicht hat.
    kalender_aktuell: bool = True


class Anstehend(BaseModel):
    kontakt_id: str
    name: str
    art: str  # "geburtstag" | "jahrestag"
    bezeichnung: str
    datum: date
    in_tagen: int
    #: Alter bzw. wievielter Jahrestag (0 im Jahr des Ereignisses selbst).
    zahl: int


class UmzugErgebnis(BaseModel):
    gefunden: int
    uebernommen: int
    schon_da: int
