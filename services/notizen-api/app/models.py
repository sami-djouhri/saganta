"""Datenmodell.

Jede Tabelle traegt ``owner_sub``. Das ist keine Doppelung der Beziehung
Notiz→Notizbuch, sondern Absicht: so kann *jede* Abfrage direkt auf den
Mandanten filtern, ohne vorher joinen zu muessen. Ein vergessener Join ist die
haeufigste Art, aus Mandantentrennung ein Leck zu machen.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .util import jetzt

# Verknuepfbare Gegenstuecke. Der Dienst speichert nur Typ + Kennung + Beschriftung
# und faellt damit *nicht* in eine Abhaengigkeit zu Kalender, ProjectDeck oder
# Briefkasten: aufgeloest wird im BFF, der die Quellen ohnehin kennt. Ein neuer
# Typ kostet hier nichts ausser einem Eintrag.
VERKNUEPFUNGS_TYPEN = {
    "termin",   # Kalender-Event (uuid)
    "aufgabe",  # Kalender-Todo
    "ziel",     # Kalender-Goal
    "projekt",  # ProjectDeck-Projekt (slug)
    "kontakt",  # Kalender-Kontakt
    "brief",    # Briefkasten-Brief
}

FREIGABE_MODI = {"offen", "chiffriert"}


class Notizbuch(Base):
    __tablename__ = "notizbuecher"
    __table_args__ = (UniqueConstraint("owner_sub", "name", name="uq_notizbuch_owner_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(120))
    farbe: Mapped[str | None] = mapped_column(String(20), default=None)
    sortierung: Mapped[int] = mapped_column(Integer, default=0)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt, onupdate=jetzt)

    notizen: Mapped[list["Notiz"]] = relationship(back_populates="notizbuch")


class Notiz(Base):
    __tablename__ = "notizen"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(String(128), index=True)
    notizbuch_id: Mapped[int | None] = mapped_column(
        ForeignKey("notizbuecher.id", ondelete="SET NULL"), default=None, index=True
    )
    titel: Mapped[str] = mapped_column(String(300), default="")
    inhalt: Mapped[str] = mapped_column(Text, default="")
    tags: Mapped[str] = mapped_column(String(400), default="")
    angeheftet: Mapped[bool] = mapped_column(Boolean, default=False)
    archiviert: Mapped[bool] = mapped_column(Boolean, default=False)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt, onupdate=jetzt)

    notizbuch: Mapped[Notizbuch | None] = relationship(back_populates="notizen")
    anhaenge: Mapped[list["Anhang"]] = relationship(
        back_populates="notiz", cascade="all, delete-orphan"
    )
    verknuepfungen: Mapped[list["Verknuepfung"]] = relationship(
        back_populates="notiz", cascade="all, delete-orphan"
    )
    freigaben: Mapped[list["Freigabe"]] = relationship(back_populates="notiz")


class Anhang(Base):
    __tablename__ = "anhaenge"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(String(128), index=True)
    notiz_id: Mapped[int] = mapped_column(
        ForeignKey("notizen.id", ondelete="CASCADE"), index=True
    )
    dateiname: Mapped[str] = mapped_column(String(200))
    mime: Mapped[str] = mapped_column(String(100))
    groesse: Mapped[int] = mapped_column(Integer, default=0)
    # Name in der Ablage, eine UUID, nie der hochgeladene Dateiname. Damit ist
    # der Pfad unabhaengig davon, was im Namen steht.
    ablage: Mapped[str] = mapped_column(String(80), unique=True)
    pruefsumme: Mapped[str] = mapped_column(String(64), default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt)

    notiz: Mapped[Notiz] = relationship(back_populates="anhaenge")


class Verknuepfung(Base):
    __tablename__ = "verknuepfungen"
    __table_args__ = (
        UniqueConstraint("notiz_id", "typ", "ref", name="uq_verknuepfung_notiz_ziel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    owner_sub: Mapped[str] = mapped_column(String(128), index=True)
    notiz_id: Mapped[int] = mapped_column(
        ForeignKey("notizen.id", ondelete="CASCADE"), index=True
    )
    typ: Mapped[str] = mapped_column(String(20), index=True)
    ref: Mapped[str] = mapped_column(String(200), index=True)
    # Beschriftung zum Zeitpunkt des Verknuepfens. Bewusst eine Kopie: benennt
    # jemand den Termin um, zeigt die Notiz weiter, worauf sie sich bezog, und
    # die Liste bleibt lesbar, auch wenn die Quelle gerade nicht erreichbar ist.
    label: Mapped[str] = mapped_column(String(300), default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt)

    notiz: Mapped[Notiz] = relationship(back_populates="verknuepfungen")


class Freigabe(Base):
    """Ein teilbarer Link auf eine Notiz.

    Zwei Betriebsarten, und der Unterschied ist grundsaetzlich:

    * ``offen``, der Link zeigt die Notiz *live*. Aendert sich die Notiz,
      aendert sich, was der Empfaenger sieht. Der Server kann mitlesen.
    * ``chiffriert``, der Link traegt einen *Schnappschuss* als Chiffrat. Der
      Schluessel entsteht im Browser und erreicht den Server nie (er steht im
      URL-Fragment, das nicht mitgesendet wird, oder wird aus einem Passwort
      abgeleitet). Der Server kann nicht mitlesen, und deshalb kann er auch
      nicht live spiegeln, eine spaetere Aenderung der Notiz erreicht diesen
      Link nicht mehr.
    """

    __tablename__ = "freigaben"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    merkmal: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    owner_sub: Mapped[str] = mapped_column(String(128), index=True)
    # SET NULL statt CASCADE: ein verschluesselter Schnappschuss soll die
    # Loeschung der Notiz ueberleben duerfen. Offene Freigaben laufen dann ins
    # Leere und melden das ehrlich (410), statt auf eine fremde Zeile zu zeigen.
    notiz_id: Mapped[int | None] = mapped_column(
        ForeignKey("notizen.id", ondelete="SET NULL"), default=None, index=True
    )
    modus: Mapped[str] = mapped_column(String(20), default="offen")

    # --- nur bei modus='chiffriert' -------------------------------------
    chiffrat: Mapped[str | None] = mapped_column(Text, default=None)
    iv: Mapped[str | None] = mapped_column(String(64), default=None)
    kdf_salz: Mapped[str | None] = mapped_column(String(64), default=None)
    kdf_iterationen: Mapped[int | None] = mapped_column(Integer, default=None)
    algo: Mapped[str | None] = mapped_column(String(40), default=None)
    # 'fragment' = Schluessel steht hinter dem # der Adresse;
    # 'passwort'  = Empfaenger leitet ihn aus einem vereinbarten Passwort ab.
    schluessel_quelle: Mapped[str | None] = mapped_column(String(20), default=None)

    # --- nur bei modus='offen' ------------------------------------------
    passwort_hash: Mapped[str | None] = mapped_column(String(64), default=None)
    passwort_salz: Mapped[str | None] = mapped_column(String(32), default=None)
    mit_anhaengen: Mapped[bool] = mapped_column(Boolean, default=True)

    # --- Lebenszyklus ----------------------------------------------------
    ablauf_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    max_abrufe: Mapped[int | None] = mapped_column(Integer, default=None)
    abrufe: Mapped[int] = mapped_column(Integer, default=0)
    fehlversuche: Mapped[int] = mapped_column(Integer, default=0)
    widerrufen_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    letzter_abruf_am: Mapped[datetime | None] = mapped_column(DateTime, default=None)
    notiz_titel_kopie: Mapped[str] = mapped_column(String(300), default="")
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt)

    notiz: Mapped[Notiz | None] = relationship(back_populates="freigaben")

    # --- abgeleiteter Zustand -------------------------------------------
    @property
    def verbraucht(self) -> bool:
        return self.max_abrufe is not None and self.abrufe >= self.max_abrufe

    @property
    def abgelaufen(self) -> bool:
        return self.ablauf_am is not None and self.ablauf_am <= jetzt()

    @property
    def gesperrt(self) -> bool:
        """Zu oft falsches Passwort, die Freigabe macht dicht."""
        from .config import settings

        return self.fehlversuche >= settings.freigabe_max_fehlversuche

    def zustand(self) -> str:
        if self.widerrufen_am is not None:
            return "widerrufen"
        if self.gesperrt:
            return "gesperrt"
        if self.abgelaufen:
            return "abgelaufen"
        if self.verbraucht:
            return "verbraucht"
        if self.modus == "offen" and self.notiz_id is None:
            return "quelle_weg"
        return "aktiv"
