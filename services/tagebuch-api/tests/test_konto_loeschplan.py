"""Der Abdeckungs-Riegel des Loeschwegs.

Er braucht keine Daten und keine laufende Datenbank: das Soll kommt aus den
SQLAlchemy-Metadaten, also aus den Modellen dieses Dienstes. Wird er rot, ist
eine Tabelle hinzugekommen, die den Mandanten traegt, aber in keinem Schritt von
``app/konto.py`` steht -- oder ein Kind hat sein ``ondelete="CASCADE"`` verloren.

Die Antwort darauf ist nie "Test anpassen". Entweder bekommt die Tabelle einen
Schritt, oder sie wird ausdruecklich als gemeinsamer Bestand erklaert. Ohne
diesen Riegel faellt eine neue Tabelle still aus dem Loeschweg, und ein Lauf
meldet weiterhin Erfolg.
"""

from saganta_dienst import loeschen

from app import models  # noqa: F401  (fuellt Base.metadata)
from app.db import Base
from app.konto import PLAN


def test_der_loeschplan_deckt_alle_tabellen_ab():
    assert loeschen.abdeckung_pruefen(PLAN, Base.metadata) == []


def test_jeder_schritt_nennt_eine_bekannte_tabelle():
    """Ein Tippfehler im Tabellennamen trifft nie und meldet trotzdem 0 Zeilen."""
    bekannt = set(Base.metadata.tables)
    for schritt in PLAN.schritte:
        assert schritt.tabelle in bekannt, (
            f"Schritt nennt '{schritt.tabelle}', das es in den Modellen nicht gibt"
        )
