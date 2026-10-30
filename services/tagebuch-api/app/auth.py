"""JWT-Pruefung fuer den angemeldeten Pfad.

Die Pruefung selbst liegt in ``saganta_dienst.auth`` und ist mit allen anderen
Saganta-Backends geteilt. Hier steht nur, was diesen Dienst ausmacht.

Der ``sub`` aus dem Token ist der Mandantenschluessel: jede Abfrage filtert
darauf. Es gibt in diesem Dienst keinen einzigen Pfad, der ohne
``owner_sub``-Filter liest, und anders als bei den Notizen auch keine Ausnahme
fuer oeffentliche Freigaben. Ein Tagebuch teilt man nicht.
"""
from fastapi import Depends
from saganta_dienst.auth import Me, baue_pruefer

from .config import settings

ERWARTETE_ZIELGRUPPE = "tagebuch-api"

verify_jwt = baue_pruefer(zielgruppe=ERWARTETE_ZIELGRUPPE, einstellungen=settings)

AktuellerNutzer = Depends(verify_jwt)

__all__ = ["Me", "verify_jwt", "AktuellerNutzer", "ERWARTETE_ZIELGRUPPE"]
