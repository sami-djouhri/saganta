"""Der Loeschweg dieses Dienstes.

Die Mechanik liegt geteilt in ``saganta_dienst.loeschen``; hier steht nur, was
dieser Dienst ueber sich selbst weiss. Zu den zwei Einstiegen (Route fuer den
Aufrufer, Programm fuer verwaiste Bestaende) siehe den Modulkopf dort.

``mail_messages`` traegt **keine** Mandantenspalte und haengt per
Fremdschluessel ohne ``ondelete`` an ``mail_accounts``. Das ist der einzige Fall
dieser Art in der Suite, und er ist der Grund, warum ``ueber(...)`` existiert:

* Ohne eigenen Schritt blieben die Nachrichten als Waisen stehen, mit Betreff,
  Absender und Inhalt. Bei ``NO ACTION`` **und** aktivem ``PRAGMA
  foreign_keys=ON`` (``db.py``) wuerde das Loeschen des Kontos sogar schon an
  der Datenbank scheitern, also mit einer Fehlermeldung statt mit einer Aussage.
* Die Reihenfolge ist deshalb zwingend: erst die Nachrichten ueber ihr Konto,
  dann die Konten selbst.

Die Zugangsdaten zu den Postfaechern stehen verschluesselt in
``mail_accounts`` (``crypto.py``) und fallen mit der Zeile. Ein Widerruf des
OAuth-Zugangs beim Anbieter ist damit **nicht** erfolgt; das kann dieser Dienst
nicht leisten und soll es auch nicht vortaeuschen.
"""

from __future__ import annotations

from saganta_dienst import loeschen

PLAN = loeschen.Plan(
    dienst="mail",
    schritte=(
        loeschen.ueber(
            "mail_messages", "account_id", "mail_accounts", "id",
            mandanten_spalte="sub",
            warum="abgerufene Nachrichten, haengen ohne CASCADE am Konto",
        ),
        loeschen.eigene("mail_accounts", spalte="sub", warum="Postfachzugaenge samt Geheimnis"),
    ),
)


if __name__ == "__main__":
    from . import models  # noqa: F401  (fuellt Base.metadata, sonst laufen die Pruefungen blind)
    from .db import Base, SessionLocal

    raise SystemExit(loeschen.als_programm(PLAN, Base.metadata, SessionLocal))
