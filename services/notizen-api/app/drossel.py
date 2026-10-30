"""Einfache Zugriffsbremse fuer den oeffentlichen Freigabe-Pfad.

Der Zweck ist eng: verhindern, dass jemand Merkmale oder Passwoerter im
Sekundentakt durchprobiert. Sie ersetzt keinen Schutz am Rand (der nginx
davor hat seine eigene Begrenzung), aber sie wirkt auch dann, wenn der Dienst
einmal ohne diesen Rand erreicht wird.

Absichtlich im Arbeitsspeicher: ein Neustart setzt die Zaehler zurueck, und das
ist verkraftbar. Ein zweiter Datenspeicher fuer eine Bremse waere mehr
bewegliche Teile als Gewinn. Der Dienst laeuft als eine Instanz, bei mehreren
Prozessen zaehlte jeder fuer sich, dann muesste das hier umziehen.
"""

import threading
from collections import defaultdict, deque

_FENSTER_SEKUNDEN = 60.0
_sperre = threading.Lock()
_spuren: dict[str, deque[float]] = defaultdict(deque)
# Ab so vielen bekannten Quellen wird aufgeraeumt, damit die Bremse nicht
# selbst zum Speicherleck wird.
_AUFRAEUMEN_AB = 4000


def erlaubt(schluessel: str, grenze: int, jetzt_s: float) -> bool:
    """Zaehlt einen Zugriff und sagt, ob er noch im Rahmen liegt."""
    with _sperre:
        spur = _spuren[schluessel]
        while spur and spur[0] <= jetzt_s - _FENSTER_SEKUNDEN:
            spur.popleft()
        if len(_spuren) > _AUFRAEUMEN_AB:
            _aufraeumen(jetzt_s)
        if len(spur) >= grenze:
            return False
        spur.append(jetzt_s)
        return True


def _aufraeumen(jetzt_s: float) -> None:
    """Quellen vergessen, die im Fenster nichts mehr getan haben."""
    tot = [k for k, v in _spuren.items() if not v or v[-1] <= jetzt_s - _FENSTER_SEKUNDEN]
    for k in tot:
        _spuren.pop(k, None)


def zuruecksetzen() -> None:
    """Nur fuer Tests."""
    with _sperre:
        _spuren.clear()
