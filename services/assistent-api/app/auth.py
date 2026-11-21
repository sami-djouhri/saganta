"""JWT-Pruefung am Eingang und die kurzen Token fuer die Apps dahinter.

Eingehend: das Backend-Token der App mit ``aud=assistent-api``, geprueft von
der geteilten Schicht ``saganta_dienst.auth``.

Ausgehend: dieser Dienst stempelt fuer jede App, in deren Namen er liest,
ein eigenes Token mit deren Zielgruppe und dem ``sub`` des Aufrufers, 60
Sekunden gueltig. Muster wie ``kontakte-api/app/kalender.py``. Der ``sub``
kommt ausschliesslich aus dem bereits geprueften Token der Anfrage, nie aus
einem Parameter; damit liest der Assistent nie mehr, als die App des
Nutzers selbst lesen duerfte.
"""
import time

from fastapi import Depends
from jose import jwt
from saganta_dienst.auth import Me, baue_pruefer

from .config import settings

# Der Name `EXPECTED_AUDIENCE` ist Absicht: `scripts/dienst-token.py` sucht ihn.
EXPECTED_AUDIENCE = "assistent-api"

verify_jwt = baue_pruefer(zielgruppe=EXPECTED_AUDIENCE, einstellungen=settings)

AktuellerNutzer = Depends(verify_jwt)

TOKEN_DAUER_S = 60


def token_fuer(me: Me, zielgruppe: str) -> str:
    jetzt = int(time.time())
    return jwt.encode(
        {
            "iss": "saganta",
            "sub": me.sub,
            "email": me.email,
            "aud": zielgruppe,
            "iat": jetzt,
            "exp": jetzt + TOKEN_DAUER_S,
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


__all__ = ["Me", "verify_jwt", "AktuellerNutzer", "EXPECTED_AUDIENCE", "token_fuer"]
