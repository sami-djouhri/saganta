"""Der Loeschweg dieses Dienstes.

Die Mechanik liegt geteilt in ``saganta_dienst.loeschen``; hier steht nur, was
dieser Dienst ueber sich selbst weiss. Zu den zwei Einstiegen (Route fuer den
Aufrufer, Programm fuer verwaiste Bestaende) siehe den Modulkopf dort.

``audit_log`` faellt mit, und das ist eine Entscheidung, keine Auslassung.
Ein Zugriffsprotokoll laesst sich mit einem berechtigten Interesse begruenden,
aber hier haengt es an ``sub``, traegt also die Spur **einer** Person und keine
Abrechnung, keine Steuerunterlage und keine Nachweispflicht. Was von ihm bliebe,
waere eine Liste der Handlungen eines geloeschten Kontos: genau das, wovon der
Loeschanspruch handelt. Wer hier spaeter eine gesetzliche Aufbewahrungspflicht
einzieht, nimmt die Zeile aus den Schritten und traegt die Frist in ``gemeinsam``
ein -- mit Begruendung, denn ohne eine ist die Aufbewahrung die Ausnahme.
"""

from __future__ import annotations

from saganta_dienst import loeschen

PLAN = loeschen.Plan(
    dienst="shell",
    schritte=(
        loeschen.eigene("audit_log", spalte="sub", warum="Zugriffsprotokoll dieses Mandanten"),
        loeschen.eigene("user_settings", spalte="sub", warum="Oberflaechen-Einstellungen"),
    ),
)


if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
