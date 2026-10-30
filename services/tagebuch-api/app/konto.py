"""Der Loeschweg dieses Dienstes.

Die Mechanik liegt geteilt in ``saganta_dienst.loeschen``; hier steht nur, was
dieser Dienst ueber sich selbst weiss, denn nur er kennt seine
Fremdschluesselketten. Zu den zwei Einstiegen (Route fuer den Aufrufer,
Programm fuer verwaiste Bestaende) siehe den Modulkopf dort.

Beim Tagebuch ist das Loeschen zugleich der einzige Weg, der ueberhaupt etwas
vernichtet: der Server verwahrt nur Chiffrat und die verpackten Schluessel, er
kann den Inhalt nicht lesen. Faellt der Tresor, ist der Rest Rauschen, und das
ist Teil des Entwurfs und keine Nachlaessigkeit.
"""

from __future__ import annotations

from saganta_dienst import loeschen

PLAN = loeschen.Plan(
    dienst="tagebuch",
    # Keine Fremdschluessel in diesem Dienst (``db.py`` sagt es ausdruecklich),
    # die Reihenfolge ist deshalb frei. Eintraege zuerst, damit der Tresor als
    # letztes faellt: so bleibt bis zum Schluss erkennbar, zu wem sie gehoerten.
    schritte=(
        loeschen.eigene("eintraege", warum="Chiffrat der Eintraege"),
        loeschen.eigene("tresore", warum="verpackte Schluessel und Zugriffsmaske"),
    ),
)


if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
