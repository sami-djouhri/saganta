"""JWT-Pruefung fuer den angemeldeten Pfad.

Die Pruefung selbst liegt in ``saganta_dienst.auth`` und ist mit allen anderen
Saganta-Backends geteilt. Hier steht nur, was diesen Dienst ausmacht.
"""
from fastapi import Depends
from saganta_dienst.auth import Me, baue_pruefer

from .config import settings

EXPECTED_AUDIENCE = "news-api"

verify_jwt = baue_pruefer(zielgruppe=EXPECTED_AUDIENCE, einstellungen=settings)

CurrentUser = Depends(verify_jwt)

__all__ = ["Me", "verify_jwt", "CurrentUser", "EXPECTED_AUDIENCE"]
