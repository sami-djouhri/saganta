"""JWT-Pruefung fuer den Auth-Proxy.

Die Pruefung selbst liegt in ``saganta_dienst.auth`` und ist mit allen anderen
Saganta-Backends geteilt. Der Proxy weicht in einem Punkt ab: er bedient keine
eigenen Routen, sondern reicht an wechselnde Backends weiter. Die Zielgruppe
steht deshalb nicht fest, sondern kommt je Anfrage herein, und zurueck geht die
rohe Nutzlast statt eines ``Me``.

Ein Owner-Gate gibt es hier bewusst nicht: der Proxy entscheidet nicht, wer
wohin darf, das tut das Backend hinter ihm mit seiner eigenen Liste.
"""
from saganta_dienst.auth import pruefe_bearer

from .config import settings


def verify_jwt(authorization: str, expected_audience: str) -> dict:
    return pruefe_bearer(
        authorization,
        geheimnis=settings.jwt_secret,
        algorithmus=settings.jwt_algorithm,
        zielgruppe=expected_audience,
    )


def authorization_header(scheme: str, token: str) -> str:
    return f"{scheme} {token}".strip()
