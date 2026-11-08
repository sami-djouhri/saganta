"""Datenmodell der Aufgaben.

Festgelegt in der dritten bis fuenften Fragerunde (`docs/RICHTUNG.md`), in den
Worten des Owners: „Aufgabe ist erstmal nur eine Aufgabe. Aufgabe kann einem
Kalendertag oder direkt einem Termin angeheftet werden." Daraus folgt:

* Nichts ist Pflicht ausser dem Titel. Kein Projekt, kein Tag, kein Termin.
* Angeheftet wird an einen **Tag** (`tag`) oder einen **Termin** (`termin_id`,
  die Kennung im Kalender), wahlweise beides.
* Eine geplante Zeit (`start`/`ende`) entsteht aus dem Vorschlag des Kalenders
  und liegt **hier**, nicht im Kalender. Der Kalender ist Konsument und haelt
  keine Kopie.
* Prioritaet ist ein Wort in drei Stufen, nicht eine Zahl.

Seit der sechsten Fragerunde (04.11.) gehoert eine Aufgabe **einem Projekt
ODER einer Liste** oder keinem von beiden („Nicht zugeordnet"). Projekte liegen
im ProjectDeck und werden ueber ihren Slug genannt, wie bei den Notizen; Listen
liegen hier. Dazu drei Arten Bedingung: wo und womit, wartet auf, Zeitfenster
und Tageszeit. Bewusst **kein** Feld „wer": eine Aufgabe ist eine Aufgabe, ohne
Zustaendigkeit.

Bewusst nicht hier: Tagesziele und Gewohnheiten. Sie bleiben im Kalender, weil
dort der Gewohnheits-Planer samt Benachrichtigung haengt.
"""
from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import JSON, Boolean, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def jetzt() -> datetime:
    return datetime.now(timezone.utc)


def neue_id() -> str:
    return str(uuid4())


class Aufgabe(Base):
    __tablename__ = "aufgaben"
    __table_args__ = (
        Index("ix_aufgaben_owner_erledigt", "owner_sub", "erledigt"),
        Index("ix_aufgaben_owner_projekt", "owner_sub", "projekt"),
        #: Der Umzug aus dem ProjectDeck ist wiederholbar, weil jede Zeile ihre
        #: Herkunft traegt; eine zweite mit derselben Herkunft gibt es nicht.
        Index("uq_aufgaben_herkunft", "owner_sub", "herkunft", unique=True),
    )

    #: UUID. Keine fortlaufende Zahl: die Notizen verknuepfen ueber den Typ
    #: `aufgabe` und eine Kennung, und eine 7 laege im selben Namensraum wie die
    #: Aufgabe 7 des ProjectDecks.
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_id)
    owner_sub: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    titel: Mapped[str] = mapped_column(String(500), nullable=False)
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: hoch | mittel | niedrig
    prioritaet: Mapped[str] = mapped_column(String(10), nullable=False, default="mittel")
    #: Frist. Ohne Frist liegt die Aufgabe im Vorrat und ist nie ueberfaellig.
    faellig: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Angeheftet an einen Kalendertag ("an dem Tag angehen").
    tag: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Angeheftet an einen Termin des Kalenders (dessen Kennung).
    termin_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Geplante Zeit, entsteht aus „Tag planen". Naive Berliner Wanduhrzeit,
    #: dieselbe Konvention wie im Kalender: was mit Offset hereinkommt, wird beim
    #: Speichern nach Berlin umgerechnet (`schemas.berlin_naiv`).
    start: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ende: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    dauer_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: niedrig | mittel | hoch: wie viel Kraft sie kostet. Der Planer legt
    #: Anstrengendes nicht auf geschonte Tage.
    energie: Mapped[str | None] = mapped_column(String(10), nullable=True)

    #: Slug des ProjectDeck-Projekts. Nicht zusammen mit ``liste_id``: eine
    #: Aufgabe steht an genau einem Ort (Entscheid 04.11.).
    projekt: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: Kennung einer Liste dieses Dienstes. Kein Fremdschluessel: SQLite prueft
    #: hier keine (kein ``foreign_keys``-Pragma), das Aufloesen einer Liste
    #: leert die Spalte deshalb ausdruecklich in der Route.
    liste_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    #: rechner | telefon | unterwegs | ort; bei ``ort`` nennt ``ort_name`` ihn.
    #: „Tag planen" legt ``unterwegs`` und ``ort`` nie selbst in den Tag
    #: (Entscheid 05.11.): der Planer weiss nicht, wo man gerade ist.
    wo: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ort_name: Mapped[str | None] = mapped_column(String(100), nullable=True)

    #: Wartet bis zu einem Datum, auf eine andere Aufgabe, oder (nur Grund)
    #: bis jemand den Grund leert. Wartende stehen ausgegraut am Ende und
    #: werden nicht geplant. Ausgewertet in ``wartet_noch``.
    wartet_bis: Mapped[date | None] = mapped_column(Date, nullable=True)
    wartet_auf_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    wartet_grund: Mapped[str | None] = mapped_column(String(300), nullable=True)

    #: Wann sie ueberhaupt geht, z. B. Oeffnungszeiten einer Praxis:
    #: ``[{"tage": [0, 1, 2, 3, 4], "von": "08:00", "bis": "12:00"}]``,
    #: 0 ist Montag. Leer heisst immer.
    zeitfenster: Mapped[list | None] = mapped_column(JSON, nullable=True)
    #: Checkliste, eine Ebene (Owner 2026-11-06): ``[{"text": ..., "erledigt": bool}]``.
    unteraufgaben: Mapped[list | None] = mapped_column(JSON, nullable=True)
    #: morgens | mittags | nachmittags | abends (Grenzen in ``TAGESZEITEN``).
    tageszeit: Mapped[str | None] = mapped_column(String(12), nullable=True)

    #: Woher sie kam, z. B. ``projectdeck:42``. Macht den Umzug wiederholbar.
    herkunft: Mapped[str | None] = mapped_column(String(64), nullable=True)

    erledigt: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Berliner Wanduhrzeit wie `start`, damit „erledigt Di 03.11." am richtigen Tag steht.
    erledigt_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    #: Wie oft sie verschoben wurde. Ab drei steht sie unter „Bleibt liegen".
    #: Waechst nur ueber den eigenen Weg `verschieben`, nie ueber ein stilles
    #: Aendern des Tages: sonst liesse sie sich beliebig oft schieben, ohne
    #: dass es je auffaellt (dieselbe Regel wie im Kalender).
    verschoben: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=jetzt)
    geaendert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=jetzt, onupdate=jetzt
    )


class Liste(Base):
    """Eine eigene Liste fuer Aufgaben ohne Projekt (Arbeit, Homelab, ...)."""
    __tablename__ = "listen"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=neue_id)
    owner_sub: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=jetzt)


class ListenAngelegt(Base):
    """Merker: die Startlisten sind fuer dieses Konto schon angelegt.

    Ohne ihn kaemen sie wieder, sobald jemand alle Listen aufloest: „keine
    Liste" ist dann kein Zeichen fuer „noch nie angelegt".
    """
    __tablename__ = "listen_angelegt"

    owner_sub: Mapped[str] = mapped_column(String(128), primary_key=True)
    am: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=jetzt)
