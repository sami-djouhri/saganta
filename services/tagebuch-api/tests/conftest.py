import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="tagebuch-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-testsuite")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


def token_fuer(sub: str) -> str:
    """Ein Token, wie der BFF es stempeln wuerde."""
    from time import time

    jetzt_s = int(time())
    return jwt.encode(
        {
            "iss": "saganta",
            "sub": sub,
            "email": f"{sub}@example.invalid",
            "groups": [],
            "aud": "tagebuch-api",
            "iat": jetzt_s,
            "exp": jetzt_s + 300,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def frische_datenbank():
    Base.metadata.drop_all(engine)
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def kopf():
    return {"Authorization": f"Bearer {token_fuer('nutzer-eins')}"}


@pytest.fixture
def kopf_zwei():
    return {"Authorization": f"Bearer {token_fuer('nutzer-zwei')}"}


@pytest.fixture
def tresor_daten():
    """Ein vollstaendiger Tresor, wie der Browser ihn erzeugt.

    Die Werte sind Platzhalter: der Dienst rechnet nichts damit nach, er
    verwahrt sie. Genau das soll die Testsuite auch zeigen.
    """
    return {
        "kdf": "PBKDF2-SHA256",
        "kdf_iterationen": 310_000,
        "salz_passphrase": "c2FseC1wYXNz",
        "wrap_passphrase": "dmVycGFja3Rlci1kZWs=",
        "wrap_passphrase_iv": "aXYtcGFzcw==",
        "salz_wiederherstellung": "c2FseC1yZWNvdmVy",
        "wrap_wiederherstellung": "dmVycGFja3Rlci1kZWstMg==",
        "wrap_wiederherstellung_iv": "aXYtcmVjb3Zlcg==",
    }
