"""JWT-Pruefung fuer den angemeldeten Pfad.

Die Pruefung selbst liegt in ``saganta_dienst.auth`` und ist mit allen anderen
Saganta-Backends geteilt. Hier steht nur, was diesen Dienst ausmacht: seine
Zielgruppe und seine Konfiguration.

Der ``sub`` aus dem Token ist hier nicht nur ein Tuerschild, sondern der
Mandantenschluessel: jede Abfrage filtert darauf. Es gibt keinen Pfad, der
Notizen ohne ``owner_sub``-Filter liest, ausser dem oeffentlichen
Freigabe-Pfad, und der findet Zeilen nur ueber ein unratbares Merkmal.
"""
from fastapi import Depends
from saganta_dienst.auth import Me, baue_pruefer

from .config import settings

ERWARTETE_ZIELGRUPPE = "notizen-api"

verify_jwt = baue_pruefer(zielgruppe=ERWARTETE_ZIELGRUPPE, einstellungen=settings)

AktuellerNutzer = Depends(verify_jwt)

__all__ = ["Me", "verify_jwt", "AktuellerNutzer", "ERWARTETE_ZIELGRUPPE"]
