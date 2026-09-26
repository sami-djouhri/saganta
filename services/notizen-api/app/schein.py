"""Kurzlebiger Zugriffsschein fuer die Anhaenge einer geoeffneten Freigabe.

Das Problem, das er loest: eine Freigabe mit „einmal lesen" ist nach dem
Oeffnen verbraucht, aber der Browser muss danach noch die Anhaenge holen.
Ohne Schein gaebe es nur schlechte Auswege: die Anhaenge vom Zaehler ausnehmen
(dann ist „einmal" gelogen, jeder mit dem Link kaeme weiter an die Dateien),
oder sie in die Antwort einbetten (bei 20 MiB je Datei keine Option).

Der Schein bindet an *diese* Freigabe und laeuft von selbst ab. Er entsteht nur
bei einem erfolgreichen Oeffnen, also genau einmal, und er ist nicht
uebertragbar, weil die Freigabe-ID mitsigniert ist.

Signiert wird mit einem aus ``jwt_secret`` abgeleiteten Schluessel. Ableiten
statt wiederverwenden: derselbe Rohschluessel in zwei Rollen ist die Art von
Abkuerzung, die spaeter niemand mehr sieht.
"""

import base64
import hashlib
import hmac

from .config import settings
from .util import jetzt

_KONTEXT = b"saganta-notizen/anhang-schein/v1"
_GUELTIG_SEKUNDEN = 900


def _schluessel() -> bytes:
    return hmac.new(settings.jwt_secret.encode("utf-8"), _KONTEXT, hashlib.sha256).digest()


def ausstellen(freigabe_id: int, gueltig_sekunden: int = _GUELTIG_SEKUNDEN) -> str:
    ablauf = int(jetzt().timestamp()) + gueltig_sekunden
    rumpf = f"{freigabe_id}.{ablauf}".encode()
    sig = hmac.new(_schluessel(), rumpf, hashlib.sha256).digest()[:16]
    return f"{ablauf}.{base64.urlsafe_b64encode(sig).decode().rstrip('=')}"


def gueltig(schein: str | None, freigabe_id: int) -> bool:
    if not schein:
        return False
    ablauf_roh, _, sig_roh = schein.partition(".")
    if not ablauf_roh.isdigit() or not sig_roh:
        return False
    ablauf = int(ablauf_roh)
    if ablauf < int(jetzt().timestamp()):
        return False
    rumpf = f"{freigabe_id}.{ablauf}".encode()
    erwartet = hmac.new(_schluessel(), rumpf, hashlib.sha256).digest()[:16]
    erwartet_str = base64.urlsafe_b64encode(erwartet).decode().rstrip("=")
    return hmac.compare_digest(erwartet_str, sig_roh)
