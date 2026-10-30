"""Der Loeschweg dieses Dienstes: welche Tabelle in welcher Reihenfolge faellt.

Die Mechanik (Vorschau, Bericht, Abdeckungs- und Restpruefung) liegt geteilt in
``saganta_dienst.loeschen``. Hier steht nur das, was dieser Dienst ueber sich
selbst weiss, denn nur er kennt seine Fremdschluesselketten.

ZWEI EINSTIEGE, EIN PLAN
========================

* **Die Route** (``routes_konto``) loescht den Mandanten aus dem Token, also
  immer den Aufrufer selbst. Sie kann konstruktionsbedingt keinen fremden
  Bestand treffen.
* **Dieses Modul als Programm** (``python -m app.konto``) loescht einen
  genannten Mandanten. Das ist der Weg fuer **verwaiste** Bestaende, deren Konto
  schon weg ist: fuer die laesst sich kein Token mehr ausstellen.

Die Trennung ist Absicht. Eine Netzroute, die einen beliebigen ``sub``
entgegennimmt, waere eine Fernbedienung zum Loeschen fremder Daten, und sie
muesste genau einmal falsch abgesichert sein. Der Betreiberweg verlangt
stattdessen Zugriff auf den Wirt, den hat ohnehin nur, wer die Platte auch so
loeschen koennte.
"""

from __future__ import annotations

from pathlib import Path

from saganta_dienst import loeschen
from sqlalchemy import text

from .config import settings


def _anhang_dateien(db, sub: str) -> list[Path]:
    """Die Dateien in der Ablage, die diesem Mandanten gehoeren.

    Wird vor den Loeschschritten gerufen: danach gibt es die Zeilen nicht mehr,
    die die Dateinamen nennen. ``ablage`` ist eine UUID, nie der hochgeladene
    Name, deshalb ist hier kein Pfad-Zusammenbau aus Nutzereingabe im Spiel.
    """
    namen = db.execute(
        text("SELECT ablage FROM anhaenge WHERE owner_sub = :sub"), {"sub": sub}
    ).scalars().all()
    verzeichnis = Path(settings.anhang_verzeichnis)
    return [verzeichnis / name for name in namen if name]


PLAN = loeschen.Plan(
    dienst="notizen",
    # Kinder vor Eltern. ``anhaenge`` und ``verknuepfungen`` haengen zwar per
    # CASCADE an ``notizen`` und fielen auch so, stehen hier aber ausdruecklich:
    # sie tragen eine eigene ``owner_sub``-Spalte, und ein Eintrag, dessen
    # Mandant von dem der Notiz abweicht, wuerde sonst unbemerkt liegenbleiben.
    schritte=(
        loeschen.eigene("freigaben", warum="Freigabe-Chiffrat und Merkmal"),
        loeschen.eigene("anhaenge", warum="Metadaten der Anhaenge"),
        loeschen.eigene("verknuepfungen", warum="Bezuege auf Termine, Aufgaben, Briefe"),
        loeschen.eigene("notizen", warum="die Notizen selbst, samt FTS-Index ueber Trigger"),
        loeschen.eigene("notizbuecher", warum="die Notizbuecher"),
    ),
    # Der Volltextindex ist hier kein Nebenschauplatz: eine external-content-
    # FTS5 haelt Titel, Inhalt und Tags im Klartext. Er wird nicht vergessen,
    # sondern vom Trigger ``notizen_fts_del`` mitgefuehrt, der bei jedem DELETE
    # auf ``notizen`` feuert (``db.py``). Deshalb steht er hier und nicht in
    # ``gemeinsam``: bedacht, nicht gemeinsam.
    per_trigger=frozenset({"notizen_fts"}),
    dateien=_anhang_dateien,
)


if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
