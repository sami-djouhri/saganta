"""Der Loeschweg dieses Dienstes.

Die Mechanik liegt geteilt in ``saganta_dienst.loeschen``; hier steht nur, was
dieser Dienst ueber sich weiss. Drei Tabellen, keine Fremdschluessel.

Tagesziele liegen im Kalender und fallen mit dessen Loeschweg, nicht hier.
"""
from __future__ import annotations

from saganta_dienst import loeschen

PLAN = loeschen.Plan(
    dienst="aufgaben",
    schritte=(
        loeschen.eigene("aufgaben", warum="Aufgaben samt Notiztext und Planung"),
        loeschen.eigene("listen", warum="eigene Listen und ihre Namen"),
        loeschen.eigene("listen_angelegt", warum="Merker fuer die Startlisten"),
    ),
)

if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
