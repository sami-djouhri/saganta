"""Echtheitsnachweis fuer den ``X-Saganta-Sub``-Header. Eine Stelle fuer alle.

**Was der Header leistet.** Native Dienste (Kalender, Postfach, Lager, Fitness,
MealPrep) erfahren den Mandanten eines Aufrufs ueber ``X-Saganta-Sub``. Wer den
Dienst direkt erreicht, koennte sich damit als beliebiger Mandant ausgeben --
deshalb schickt jeder Absender zusaetzlich
``X-Saganta-Sub-Sig: hex(HMAC-SHA256(geheimnis, sub))``. Die Signatur haengt an
genau diesem ``sub``, eine abgefangene laesst sich nicht umhaengen, und das
Geheimnis selbst wandert nie ueber die Leitung.

**Warum das hier liegt und nicht je Dienst.** Am 2026-09-27 gemessen lag dieselbe
HMAC-Funktion in **vier** Fassungen nebeneinander: ``auth-proxy/app/tenant_sig.py``,
``kalender-bff/app/upstream.py``, ``projectdeck-api/app/kalender_client.py`` und
``news-api/app/services/kalender_client.py``. Vier Kopien einer
Sicherheitsfunktion sind vier Orte, an denen eine Korrektur vergessen werden kann,
und ``services/_geteilt/saganta_dienst`` existierte die ganze Zeit.

Die Funktion ist absichtlich winzig und ohne Abhaengigkeiten (stdlib ``hmac``).
Der Wert liegt nicht in der Zeilenzahl, sondern darin, dass die Namen der beiden
Header und die Reihenfolge der HMAC-Argumente genau einmal festgelegt sind.
"""

import hashlib
import hmac

SUB_HEADER = "X-Saganta-Sub"
SIG_HEADER = "X-Saganta-Sub-Sig"


def signatur(sub: str, geheimnis: str) -> str:
    """Die Signatur, die ein Absender fuer diesen ``sub`` mitschicken muss."""
    return hmac.new(geheimnis.encode("utf-8"), sub.encode("utf-8"), hashlib.sha256).hexdigest()


def kopfzeilen(sub: str | None, geheimnis: str | None) -> dict[str, str]:
    """Beide Header fuer einen Aufruf im Namen dieses Mandanten.

    Leeres Dict, wenn kein ``sub`` oder kein Geheimnis vorliegt. Das ist bewusst
    kein Fehler: ohne konfiguriertes Geheimnis verhaelt sich die Kette genau wie
    vorher, und ein Dienst ohne Mandanten (headerloser CORE-Pfad) soll gar keinen
    Header bekommen, statt einen leeren.
    """
    if not sub or not geheimnis:
        return {}
    return {SUB_HEADER: sub, SIG_HEADER: signatur(sub, geheimnis)}


def stimmt(sub: str, gegeben: str, geheimnis: str) -> bool:
    """Prueft eine empfangene Signatur in konstanter Zeit."""
    if not sub or not gegeben or not geheimnis:
        return False
    return hmac.compare_digest(gegeben, signatur(sub, geheimnis))
