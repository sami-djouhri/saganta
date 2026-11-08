"""Ein Kontakt: Name, Wege zu ihm, seine Tage und woran er haengt.

Seit 2026-11-07 der eine Ort fuer Kontakte (vorher die Tabelle ``contacts`` im
Kalender, von dort mit denselben Kennungen umgezogen). Der Kalender bekommt nach
jeder Aenderung den Stand der Geburtstage und Jahrestage gespiegelt
(``abgleich.py``) und erinnert daran.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def jetzt() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def neue_kennung() -> str:
    return str(uuid.uuid4())


class Kontakt(Base):
    __tablename__ = "kontakte"
    __table_args__ = (
        Index("ix_kontakte_owner_name", "owner_sub", "name"),
        # Umzugskennung (``kalender:<id>``): eindeutig je Mandant, damit ein
        # zweiter Umzug nichts doppelt anlegt.
        Index("uq_kontakte_herkunft", "owner_sub", "herkunft", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_kennung)
    owner_sub: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(200))
    telefon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(300), nullable=True)
    adresse: Mapped[str | None] = mapped_column(String(300), nullable=True)
    geburtstag: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: ``[{"bezeichnung": "Hochzeitstag", "datum": "2020-06-20"}]``
    jahrestage: Mapped[list | None] = mapped_column(JSON, nullable=True)
    gruppe: Mapped[str | None] = mapped_column(String(60), nullable=True)
    #: Verknuepfte Termine, ``[{"ref": "<event-id>", "label": "...", "start": "..."}]``.
    #: Die Beschriftung ist eine Kopie, wie in der notizen-api: benennt jemand
    #: den Termin um, bleibt lesbar, worauf sich der Kontakt bezog.
    termine: Mapped[list | None] = mapped_column(JSON, nullable=True)
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    herkunft: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Papierkorb: gesetzt = geloescht, nach ``papierkorb_tage`` endgueltig weg.
    geloescht_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt)
    geaendert_am: Mapped[datetime] = mapped_column(DateTime, default=jetzt, onupdate=jetzt)


class AbgleichOffen(Base):
    """Merker: der Kalender hat den letzten Stand dieses Mandanten nicht bekommen.

    Faellt der Kalender beim Speichern aus, bleibt der Kontakt gespeichert, und
    der Abgleich wird nachgeholt (naechste Aenderung oder Hintergrundlauf).
    Ohne den Merker fehlte der neue Geburtstag im Kalender, ohne dass es jemand
    merkt: ein fehlender Termin sieht aus wie kein Termin.
    """
    __tablename__ = "abgleich_offen"

    owner_sub: Mapped[str] = mapped_column(String(128), primary_key=True)
    email: Mapped[str] = mapped_column(String(300), default="")
    seit: Mapped[datetime] = mapped_column(DateTime, default=jetzt)
    fehler: Mapped[str] = mapped_column(String(300), default="")
