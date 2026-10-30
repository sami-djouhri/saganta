"""Der Loeschweg dieses Dienstes.

Die Mechanik liegt geteilt in ``saganta_dienst.loeschen``; hier steht nur, was
dieser Dienst ueber sich selbst weiss. Zu den zwei Einstiegen (Route fuer den
Aufrufer, Programm fuer verwaiste Bestaende) siehe den Modulkopf dort.

Bilder und Marktdaten zu einem Gegenstand liegen nicht hier, sondern in
``marktwatch`` auf node1 (``upstream.py``). Was dieser Dienst haelt, ist die
Zuordnung "wem gehoert was", und genau die faellt hier.
"""

from __future__ import annotations

from saganta_dienst import loeschen

PLAN = loeschen.Plan(
    dienst="assets",
    schritte=(
        loeschen.eigene("assets", warum="die Gegenstaende des Mandanten"),
    ),
)


if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
