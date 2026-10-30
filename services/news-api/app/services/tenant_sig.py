"""Echtheitsnachweis für den ``X-Saganta-Sub``-Header.

Gegenstück zu ``backend/tenant_auth.py`` im nativen Kalender. Dort hing die
gesamte Mandantentrennung bis 2026-08 an der Annahme, dass dieser BFF der einzige
Weg zu ``kalender:8085`` ist, wer den Dienst direkt erreicht, konnte sich mit
einem beliebigen ``X-Saganta-Sub`` als fremder Mandant ausgeben.

Wir schicken deshalb zusätzlich ``X-Saganta-Sub-Sig: hex(HMAC-SHA256(secret, sub))``.
Die Signatur ist an genau diesen ``sub`` gebunden, eine abgefangene Signatur lässt
sich nicht auf einen fremden ``sub`` umhängen, und das Geheimnis selbst wandert nie
über die Leitung.

Ohne konfiguriertes Geheimnis verhält sich das Modul **exakt wie vorher** (nur der
``sub``-Header, keine Signatur). Das ist die Voraussetzung dafür, das Geheimnis
ausrollen zu können, ohne dass Absender und Prüfer im selben Moment umschalten
müssen.

Bewusst stdlib-only (hmac/hashlib), keine neue Abhängigkeit.
"""

import hashlib
import hmac

from ..config import settings

SUB_HEADER = "X-Saganta-Sub"
SIG_HEADER = "X-Saganta-Sub-Sig"


def tenant_headers(sub: str | None) -> dict[str, str]:
    """Mandanten-Header für einen Aufruf an den nativen Kalender.

    Leeres Dict bei ``sub=None``, das ist der headerlose CORE-Pfad, der beim
    Kalender bewusst auf ``DEFAULT_OWNER_SUB`` fällt.
    """
    if not sub:
        return {}
    headers = {SUB_HEADER: sub}
    secret = settings.kalender_tenant_secret
    if secret:
        headers[SIG_HEADER] = hmac.new(
            secret.encode("utf-8"), sub.encode("utf-8"), hashlib.sha256
        ).hexdigest()
    return headers
