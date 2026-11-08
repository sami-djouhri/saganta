"""JWT-Pruefung fuer den angemeldeten Pfad.

Die Pruefung liegt geteilt in ``saganta_dienst.auth``. Der ``sub`` aus dem Token
ist der Mandantenschluessel: jede Abfrage filtert darauf.
"""
from fastapi import Depends
from saganta_dienst.auth import Me, baue_pruefer

from .config import settings

# Der Name `EXPECTED_AUDIENCE` ist Absicht: `scripts/dienst-token.py` sucht ihn.
EXPECTED_AUDIENCE = "kontakte-api"
ERWARTETE_ZIELGRUPPE = EXPECTED_AUDIENCE

verify_jwt = baue_pruefer(zielgruppe=ERWARTETE_ZIELGRUPPE, einstellungen=settings)

AktuellerNutzer = Depends(verify_jwt)

__all__ = ["Me", "verify_jwt", "AktuellerNutzer", "ERWARTETE_ZIELGRUPPE"]

