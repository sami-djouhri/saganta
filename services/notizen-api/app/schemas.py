from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import FREIGABE_MODI, VERKNUEPFUNGS_TYPEN

# --- Notizbuecher --------------------------------------------------------


class NotizbuchAn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    farbe: str | None = Field(default=None, max_length=20)
    sortierung: int = 0


class NotizbuchAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    farbe: str | None
    sortierung: int
    erstellt_am: datetime
    anzahl_notizen: int = 0


# --- Verknuepfungen ------------------------------------------------------


class VerknuepfungAn(BaseModel):
    typ: str
    ref: str = Field(min_length=1, max_length=200)
    label: str = Field(default="", max_length=300)

    @field_validator("typ")
    @classmethod
    def _typ_bekannt(cls, v: str) -> str:
        if v not in VERKNUEPFUNGS_TYPEN:
            raise ValueError(f"Unbekannter Verknuepfungstyp: {v}")
        return v


class VerknuepfungAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    typ: str
    ref: str
    label: str
    erstellt_am: datetime


# --- Anhaenge ------------------------------------------------------------


class AnhangAus(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dateiname: str
    mime: str
    groesse: int
    erstellt_am: datetime


# --- Notizen -------------------------------------------------------------


class NotizAn(BaseModel):
    titel: str = Field(default="", max_length=300)
    inhalt: str = ""
    notizbuch_id: int | None = None
    tags: list[str] = Field(default_factory=list)
    angeheftet: bool = False
    archiviert: bool = False


class NotizPatch(BaseModel):
    titel: str | None = Field(default=None, max_length=300)
    inhalt: str | None = None
    notizbuch_id: int | None = None
    # Unterscheidet „kein Notizbuch" von „Feld nicht angefasst": ohne dieses
    # Flag koennte man eine Notiz nie wieder aus ihrem Notizbuch loesen.
    notizbuch_loesen: bool = False
    tags: list[str] | None = None
    angeheftet: bool | None = None
    archiviert: bool | None = None
    # Der Stand, von dem diese Aenderung ausgeht: das ``geaendert_am`` der
    # zuletzt geladenen Fassung. Weicht er vom Bestand ab, hat inzwischen ein
    # anderes Fenster oder Geraet gespeichert, und die Antwort ist 409 statt
    # stillem Ueberschreiben. Ohne das Feld bleibt es beim bisherigen
    # Verhalten (letzter gewinnt), damit aeltere Clients weiterschreiben.
    basis_geaendert_am: datetime | None = None


class NotizKurzAus(BaseModel):
    """Listendarstellung, ohne den vollen Text, dafuer mit Ausschnitt."""

    id: int
    titel: str
    ausschnitt: str
    tags: list[str]
    notizbuch_id: int | None
    angeheftet: bool
    archiviert: bool
    anzahl_anhaenge: int
    anzahl_verknuepfungen: int
    anzahl_freigaben: int
    erstellt_am: datetime
    geaendert_am: datetime


class NotizAus(BaseModel):
    id: int
    titel: str
    inhalt: str
    tags: list[str]
    notizbuch_id: int | None
    angeheftet: bool
    archiviert: bool
    erstellt_am: datetime
    geaendert_am: datetime
    anhaenge: list[AnhangAus]
    verknuepfungen: list[VerknuepfungAus]
    freigaben: list["FreigabeAus"]


# --- Freigaben -----------------------------------------------------------


class FreigabeAn(BaseModel):
    """Wunsch nach einem teilbaren Link.

    Bei ``modus='chiffriert'`` liefert der Browser das fertige Chiffrat mit;
    ``inhalt`` und ``titel`` der Notiz erreichen den Server dann nicht.
    """

    modus: Literal["offen", "chiffriert"] = "offen"
    ablauf_tage: int | None = Field(default=7, ge=1, le=365)
    max_abrufe: int | None = Field(default=None, ge=1, le=10000)
    # Nur Modus 'offen': der Server prueft es. Bei 'chiffriert' geht das
    # Passwort nie ueber die Leitung: daraus entsteht im Browser der Schluessel.
    passwort: str | None = Field(default=None, min_length=4, max_length=200)
    mit_anhaengen: bool = True

    # --- nur Modus 'chiffriert' -----------------------------------------
    chiffrat: str | None = None
    iv: str | None = Field(default=None, max_length=64)
    kdf_salz: str | None = Field(default=None, max_length=64)
    kdf_iterationen: int | None = Field(default=None, ge=10000, le=5_000_000)
    algo: str | None = Field(default=None, max_length=40)
    schluessel_quelle: Literal["fragment", "passwort"] | None = None

    @field_validator("modus")
    @classmethod
    def _modus_bekannt(cls, v: str) -> str:
        if v not in FREIGABE_MODI:
            raise ValueError(f"Unbekannter Freigabe-Modus: {v}")
        return v


class FreigabeAus(BaseModel):
    id: int
    merkmal: str
    modus: str
    zustand: str
    ablauf_am: datetime | None
    max_abrufe: int | None
    abrufe: int
    passwortgeschuetzt: bool
    mit_anhaengen: bool
    notiz_id: int | None
    notiz_titel: str
    erstellt_am: datetime
    letzter_abruf_am: datetime | None


# --- Oeffentlicher Pfad --------------------------------------------------


class OeffentlicherZustand(BaseModel):
    """Was ein Besucher sieht, *bevor* er die Notiz oeffnet.

    Bewusst arm an Angaben: kein Titel, kein Ausschnitt, kein Hinweis auf den
    Absender. Diese Antwort beantwortet nur die Frage „laesst sich das hier
    oeffnen, und was brauche ich dafuer?", der Inhalt kostet einen zweiten,
    ausdruecklichen Schritt.
    """

    modus: str
    zustand: str
    braucht_passwort: bool
    einmalig: bool
    verbleibende_abrufe: int | None
    ablauf_am: datetime | None
    schluessel_quelle: str | None
    algo: str | None
    kdf_salz: str | None
    kdf_iterationen: int | None


class OeffentlicherAnhang(BaseModel):
    id: int
    dateiname: str
    mime: str
    groesse: int


class OeffentlicherInhalt(BaseModel):
    modus: str
    titel: str
    # Genau eins von beiden ist gesetzt: 'offen' liefert Text, 'chiffriert'
    # liefert das Chiffrat, das nur der Empfaenger aufschliessen kann.
    inhalt: str | None = None
    chiffrat: str | None = None
    iv: str | None = None
    anhaenge: list[OeffentlicherAnhang] = Field(default_factory=list)
    verbleibende_abrufe: int | None = None
    einmalig: bool = False
    # Freigabe-Zugriffsschein fuer die Anhaenge dieses Abrufs (siehe
    # routes_oeffentlich): ohne ihn ist ein Anhang nicht erreichbar.
    anhang_schein: str | None = None


class OeffnenAn(BaseModel):
    passwort: str | None = Field(default=None, max_length=200)


NotizAus.model_rebuild()
