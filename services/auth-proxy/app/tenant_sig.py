"""Echtheitsnachweis für den ``X-Saganta-Sub``-Header (Kalender-Pfad).

Gegenstück zu ``backend/tenant_auth.py`` im nativen Kalender. Dort hing die
Mandantentrennung bis 2026-08 daran, dass nur vertrauenswürdige Absender den
Dienst erreichen, wer ``kalender:8085`` direkt anspricht, konnte sich mit einem
beliebigen ``X-Saganta-Sub`` als fremder Mandant ausgeben.

Dieser Proxy schickt deshalb zusätzlich ``X-Saganta-Sub-Sig:
hex(HMAC-SHA256(secret, sub))``. Die Signatur ist an genau diesen ``sub`` gebunden,
und das Geheimnis selbst wandert nie über die Leitung.

Anders als in ``kalender-bff`` liefert dieses Modul **nur die Signatur**, den
``sub``-Header setzt der Proxy bereits selbst aus den JWT-Claims.

Ohne konfiguriertes Geheimnis: leeres Dict = exakt das bisherige Verhalten.

Bewusst stdlib-only (hmac/hashlib), keine neue Abhängigkeit.
"""

import hashlib
import hmac

from .config import settings

SIG_HEADER = "X-Saganta-Sub-Sig"


def tenant_sig_headers(sub: str | None) -> dict[str, str]:
    """Signatur-Header für einen Kalender-Aufruf. Leer, wenn nicht konfiguriert."""
    secret = settings.kalender_tenant_secret
    if not sub or not secret:
        return {}
    return {
        SIG_HEADER: hmac.new(
            secret.encode("utf-8"), sub.encode("utf-8"), hashlib.sha256
        ).hexdigest()
    }
