"""JWT-Pruefung fuer den angemeldeten Pfad.

Die Pruefung selbst liegt in ``saganta_dienst.auth`` und ist mit allen anderen
Saganta-Backends geteilt. Hier steht nur, was diesen Dienst ausmacht.

``current_owner_sub`` ist der Request-lokale Mandant, den ``upstream`` als
``X-Saganta-Sub`` an den nativen Kalender weiterreicht, statt headerlos auf
dessen Owner-Vorgabe zu fallen. Er heisst in der geteilten Schicht
``aktueller_sub``; der Name hier bleibt, weil die Konsumenten darauf zeigen.
"""
from fastapi import Depends
from saganta_dienst.auth import Me, aktueller_sub, baue_pruefer

from .config import settings

EXPECTED_AUDIENCE = "kalender-bff"

current_owner_sub = aktueller_sub

verify_jwt = baue_pruefer(zielgruppe=EXPECTED_AUDIENCE, einstellungen=settings)

CurrentUser = Depends(verify_jwt)

__all__ = [
    "Me",
    "verify_jwt",
    "CurrentUser",
    "EXPECTED_AUDIENCE",
    "current_owner_sub",
]
