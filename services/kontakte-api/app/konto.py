"""Der Loeschweg dieses Dienstes (Mechanik in ``saganta_dienst.loeschen``).

Der Spiegel im Kalender faellt mit dessen Loeschweg, nicht hier.
"""
from __future__ import annotations

from saganta_dienst import loeschen

PLAN = loeschen.Plan(
    dienst="kontakte",
    schritte=(
        loeschen.eigene("kontakte", warum="Kontakte samt Telefon, Mail, Adresse, Tagen und Notiz"),
        loeschen.eigene("abgleich_offen", warum="Merker fuer einen ausstehenden Kalender-Abgleich"),
    ),
)

if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
