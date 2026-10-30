"""JWT-Pruefung fuer den angemeldeten Pfad.

Die Pruefung selbst liegt in ``saganta_dienst.auth`` und ist mit allen anderen
Saganta-Backends geteilt. Hier steht nur, was diesen Dienst ausmacht.

``Me`` kommt bewusst weiter aus ``.schemas``: die Antwortmodelle dieses Dienstes
verweisen darauf, und ein Wechsel auf die geteilte Klasse waere ein Umbau der
oeffentlichen Schnittstelle ohne Gegenwert.
"""
from fastapi import Depends
from saganta_dienst.auth import baue_pruefer

from .config import settings
from .schemas import Me

EXPECTED_AUDIENCE = "shell-api"

verify_jwt = baue_pruefer(
    zielgruppe=EXPECTED_AUDIENCE,
    einstellungen=settings,
    me_klasse=Me,
)

CurrentUser = Depends(verify_jwt)

__all__ = ["Me", "verify_jwt", "CurrentUser", "EXPECTED_AUDIENCE"]
