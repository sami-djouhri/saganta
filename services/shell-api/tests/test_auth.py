"""Smoke-Tests fuer verify_jwt, die einzige Auth-Grenze der shell-api.

Deckt die kritischen Ablehnungspfade ab (fehlender/abgelaufener/manipulierter/
falsch adressierter Token, unbekannter Issuer, Owner-Gate) plus den Happy-Path.

Die Pruefung selbst liegt seit dem 02.09.2026 in ``saganta_dienst.auth`` und hat
dort ihre eigene, breitere Testsuite. Diese Datei bleibt trotzdem: sie prueft
nicht das Modul, sondern **diesen Dienst mit seiner Verdrahtung**, also die
richtige Zielgruppe, das richtige ``settings`` und sein eigenes ``Me`` aus
``schemas``. Ein gruenes Modul ohne gepruefte Konsumenten sagt wenig.
"""

import asyncio
import time
import unittest

from fastapi import HTTPException
from jose import jwt

from app.auth import EXPECTED_AUDIENCE, verify_jwt
from app.config import settings


def _ruf(authorization: str | None):
    """``verify_jwt`` ist eine async-Abhaengigkeit, siehe saganta_dienst.auth.

    Async, weil der Mandant sonst als ContextVar im Threadpool haengenbliebe und
    den Route-Handler nie erreichte. Hier im Test heisst das nur: einmal durch
    ``asyncio.run``.
    """
    return asyncio.run(verify_jwt(authorization))


def _token(**overrides) -> str:
    payload = {
        "sub": "user-123",
        "iss": "saganta",
        "aud": EXPECTED_AUDIENCE,
        "email": "sam@djouhri.de",
        "name": "Sam",
        "exp": int(time.time()) + 60,
    }
    payload.update(overrides)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _bearer(tok: str) -> str:
    return f"Bearer {tok}"


class VerifyJwtTest(unittest.TestCase):
    def setUp(self) -> None:
        # Owner-Gate pro Test kontrollierbar; Default offen.
        self._orig_subs = settings.allowed_subs
        settings.allowed_subs = []

    def tearDown(self) -> None:
        settings.allowed_subs = self._orig_subs

    def test_valid_token_returns_me(self) -> None:
        me = _ruf(_bearer(_token()))
        self.assertEqual(me.sub, "user-123")
        self.assertEqual(me.email, "sam@djouhri.de")

    def test_missing_bearer_prefix_401(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _ruf(_token())  # ohne "Bearer "
        self.assertEqual(ctx.exception.status_code, 401)

    def test_expired_token_401(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _ruf(_bearer(_token(exp=int(time.time()) - 10)))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_wrong_audience_401(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _ruf(_bearer(_token(aud="kalender-bff")))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_tampered_signature_401(self) -> None:
        forged = jwt.encode(
            {"sub": "user-123", "iss": "saganta", "aud": EXPECTED_AUDIENCE,
             "exp": int(time.time()) + 60},
            "some-other-secret",
            algorithm=settings.jwt_algorithm,
        )
        with self.assertRaises(HTTPException) as ctx:
            _ruf(_bearer(forged))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_unknown_issuer_401(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            _ruf(_bearer(_token(iss="evil")))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_owner_gate_blocks_foreign_sub_403(self) -> None:
        settings.allowed_subs = ["owner-only"]
        with self.assertRaises(HTTPException) as ctx:
            _ruf(_bearer(_token(sub="stranger")))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_owner_gate_allows_listed_sub(self) -> None:
        settings.allowed_subs = ["owner-only"]
        me = _ruf(_bearer(_token(sub="owner-only")))
        self.assertEqual(me.sub, "owner-only")


if __name__ == "__main__":
    unittest.main()
