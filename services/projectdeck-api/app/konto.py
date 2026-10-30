"""Der Loeschweg dieses Dienstes.

Die Mechanik liegt geteilt in ``saganta_dienst.loeschen``; hier steht nur, was
dieser Dienst ueber sich selbst weiss. Zu den zwei Einstiegen (Route fuer den
Aufrufer, Programm fuer verwaiste Bestaende) siehe den Modulkopf dort.

Dieser Dienst nennt seine Mandantenspalte ``owner`` und nicht ``owner_sub``.
Das ist der Grund, warum die geteilte Schicht eine Liste von Spaltennamen fuehrt
und keinen einzigen: ein Pruefer, der Eigenschaften am Namen erkennt, findet
genau das nicht, was anders benannt ist.

Sieben Tabellen tragen hier **keine** Mandantenspalte und haengen per
``ondelete="CASCADE"`` an ``projects``. Sie stehen deshalb in keinem Schritt,
und das ist kein Versehen: die Abdeckungspruefung loest diese Ketten auf und
wuerde sich melden, wenn eine davon ihr CASCADE verloere. Dass das wirklich
greift, haengt an ``PRAGMA foreign_keys=ON`` in ``db.py`` -- ohne das Pragma
setzt SQLite Fremdschluessel gar nicht durch, und die Kinder blieben als Waisen
zurueck.
"""

from __future__ import annotations

from saganta_dienst import loeschen

PLAN = loeschen.Plan(
    dienst="projectdeck",
    schritte=(
        loeschen.eigene("weekly_focus", spalte="owner", warum="Wochenfokus"),
        loeschen.eigene(
            "projects",
            spalte="owner",
            warum="Projekte, mit Aufgaben, Meilensteinen, Reviews und Zeitbloecken per CASCADE",
        ),
    ),
)


if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
