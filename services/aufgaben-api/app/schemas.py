"""Ein- und Ausgabe der Aufgaben.

Eingaben erben von ``Eingang``: ein unbekannter Feldname faellt nicht wortlos
weg, sondern wird gemeldet (`docs/FELDNAMEN_BEFUND.md`). Bei einem neuen Dienst
waere ``ablehnen`` moeglich, aber dann verhielte er sich anders als alle
Schwestern, und der Schalter ist je Dienst ohnehin in der Umgebung.
"""
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from saganta_dienst.eingang import Eingang

BERLIN = ZoneInfo("Europe/Berlin")

Prioritaet = Literal["hoch", "mittel", "niedrig"]
Energie = Literal["niedrig", "mittel", "hoch"]
Wo = Literal["rechner", "telefon", "unterwegs", "ort"]
Tageszeit = Literal["morgens", "mittags", "nachmittags", "abends"]

#: Grenzen der Tageszeiten als (von, bis) in Minuten seit Mitternacht.
TAGESZEITEN: dict[str, tuple[int, int]] = {
    "morgens": (5 * 60, 11 * 60),
    "mittags": (11 * 60, 14 * 60),
    "nachmittags": (14 * 60, 18 * 60),
    "abends": (18 * 60, 23 * 60),
}

_UHRZEIT = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"


class Unteraufgabe(BaseModel):
    """Ein Punkt der Checkliste einer Aufgabe (eine Ebene, seit 2026-11-07)."""
    model_config = ConfigDict(extra="forbid")

    text: str = Field(..., min_length=1, max_length=300)
    erledigt: bool = False


class Fenster(BaseModel):
    """Ein Zeitfenster: an diesen Wochentagen (0 = Montag) von bis."""
    model_config = ConfigDict(extra="forbid")

    tage: list[int] = Field(..., min_length=1, max_length=7)
    von: str = Field(..., pattern=_UHRZEIT)
    bis: str = Field(..., pattern=_UHRZEIT)

    @field_validator("tage")
    @classmethod
    def _wochentage(cls, v: list[int]) -> list[int]:
        if any(t < 0 or t > 6 for t in v):
            raise ValueError("Wochentag ausserhalb 0 bis 6")
        return sorted(set(v))

    @model_validator(mode="after")
    def _von_vor_bis(self) -> "Fenster":
        if self.bis <= self.von:
            raise ValueError("bis liegt nicht nach von")
        return self


def berlin_naiv(wert: datetime | None) -> datetime | None:
    """Mit Offset nach Berlin umgerechnet und ohne Zone; ohne Offset unveraendert."""
    if wert is None or wert.tzinfo is None:
        return wert
    return wert.astimezone(BERLIN).replace(tzinfo=None)


class AufgabeNeu(Eingang):
    titel: str = Field(..., min_length=1, max_length=500)
    notiz: str | None = Field(default=None, max_length=5000)
    prioritaet: Prioritaet = "mittel"
    faellig: date | None = None
    tag: date | None = None
    termin_id: str | None = Field(default=None, max_length=64)
    dauer_min: int | None = Field(default=None, ge=1, le=1440)
    energie: Energie | None = None
    projekt: str | None = Field(default=None, min_length=1, max_length=120)
    liste_id: str | None = Field(default=None, max_length=36)
    wo: Wo | None = None
    ort_name: str | None = Field(default=None, min_length=1, max_length=100)
    wartet_bis: date | None = None
    wartet_auf_id: str | None = Field(default=None, max_length=36)
    wartet_grund: str | None = Field(default=None, max_length=300)
    zeitfenster: list[Fenster] | None = Field(default=None, max_length=14)
    unteraufgaben: list[Unteraufgabe] | None = Field(default=None, max_length=50)
    tageszeit: Tageszeit | None = None
    #: Nur fuer den Umzug: Herkunft und, bei schon Erledigten, wann.
    herkunft: str | None = Field(default=None, min_length=1, max_length=64)
    erledigt_am: datetime | None = None

    @field_validator("titel")
    @classmethod
    def _titel_nicht_leer(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Titel ist leer")
        return v


class AufgabeAenderung(Eingang):
    """Teilaenderung. Ein nicht geschicktes Feld bleibt, ein ``null`` leert es.

    Die Route liest ``model_fields_set``; ``exclude_none`` haette ein Leeren
    unmoeglich gemacht, genau der Fehler, den der kalender-bff bis zum
    13.09. hatte.
    """
    titel: str | None = Field(default=None, min_length=1, max_length=500)
    notiz: str | None = Field(default=None, max_length=5000)
    prioritaet: Prioritaet | None = None
    faellig: date | None = None
    tag: date | None = None
    termin_id: str | None = Field(default=None, max_length=64)
    start: datetime | None = None
    ende: datetime | None = None
    dauer_min: int | None = Field(default=None, ge=1, le=1440)
    energie: Energie | None = None
    projekt: str | None = Field(default=None, min_length=1, max_length=120)
    liste_id: str | None = Field(default=None, max_length=36)
    wo: Wo | None = None
    ort_name: str | None = Field(default=None, min_length=1, max_length=100)
    wartet_bis: date | None = None
    wartet_auf_id: str | None = Field(default=None, max_length=36)
    wartet_grund: str | None = Field(default=None, max_length=300)
    zeitfenster: list[Fenster] | None = Field(default=None, max_length=14)
    unteraufgaben: list[Unteraufgabe] | None = Field(default=None, max_length=50)
    tageszeit: Tageszeit | None = None


class Verschieben(Eingang):
    """``tag`` leer heisst: zurueck in den Vorrat."""
    tag: date | None = None


class PlanAnfrage(Eingang):
    datum: date
    festlegen: bool = False


class AufgabeAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    titel: str
    notiz: str | None
    prioritaet: str
    faellig: date | None
    tag: date | None
    termin_id: str | None
    start: datetime | None
    ende: datetime | None
    dauer_min: int | None
    energie: str | None
    erledigt: bool
    erledigt_am: datetime | None
    verschoben: int
    projekt: str | None
    liste_id: str | None
    wo: str | None
    ort_name: str | None
    wartet_bis: date | None
    wartet_auf_id: str | None
    wartet_grund: str | None
    zeitfenster: list[Fenster] | None
    unteraufgaben: list[Unteraufgabe] | None = None
    tageszeit: str | None
    herkunft: str | None
    geaendert_am: datetime | None = None
    #: Ausgewertet beim Lesen: wartet sie heute noch (Datum, Aufgabe, Grund)?
    wartet: bool = False


class ListeNeu(Eingang):
    name: str = Field(..., min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def _name_nicht_leer(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name ist leer")
        return v


class ListeAenderung(Eingang):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    position: int | None = Field(default=None, ge=0, le=10000)


class ListeAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    position: int
    #: offene Aufgaben darin
    offen: int = 0


class PlanVorschlag(BaseModel):
    aufgabe_id: str
    titel: str
    start: datetime
    ende: datetime
    minuten: int
    grund: str | None = None


class PlanZurueck(BaseModel):
    aufgabe_id: str
    titel: str
    #: energie | kapazitaet (so begruendet es der Planer des Kalenders), dazu
    #: zeitfenster | tageszeit, wenn dieser Dienst den Vorschlag verwirft
    grund: str


class Plan(BaseModel):
    datum: date
    festgelegt: bool
    minuten: int
    vorschlaege: list[PlanVorschlag]
    zurueck: list[PlanZurueck]
    #: Aufgaben aus dem Vorrat, fuer die kein freies Fenster lang genug war.
    #: Der Planer des Kalenders nennt sie nicht; ohne diese Zeile saehe ein
    #: zu voller Tag aus wie ein leerer Vorrat.
    ohne_fenster: list[str]


class Kapazitaet(BaseModel):
    stufe: str | None = None
    grund: str | None = None
    deckel_min: int | None = None


class Ziel(BaseModel):
    id: str
    titel: str
    prioritaet: str
    status: str


class TagAus(BaseModel):
    """Was der Kalender zum Tag beitraegt. Fehlt er, sind die Felder leer."""
    datum: date
    kalender_erreichbar: bool
    kapazitaet: Kapazitaet | None = None
    frei_min: int | None = None
    ziele: list[Ziel] = []


class ZielNeu(Eingang):
    titel: str = Field(..., min_length=1, max_length=300)
    datum: date
    prioritaet: Literal["A", "B", "C"] = "B"


class ZielAenderung(Eingang):
    titel: str | None = Field(default=None, min_length=1, max_length=300)
    prioritaet: Literal["A", "B", "C"] | None = None
    #: erreicht ist `achieved`, wieder offen ist `planned`, wie im Kalender
    status: Literal["planned", "achieved"] | None = None
