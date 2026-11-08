import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp(prefix="aufgaben-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("JWT_SECRET", "test-geheimnis-nur-fuer-die-testsuite")

from fastapi.testclient import TestClient  # noqa: E402
from jose import jwt  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


def token_fuer(sub: str, aud: str = "aufgaben-api") -> str:
    from time import time

    jetzt_s = int(time())
    return jwt.encode(
        {"iss": "saganta", "sub": sub, "email": f"{sub}@example.invalid", "groups": [],
         "aud": aud, "iat": jetzt_s, "exp": jetzt_s + 300},
        settings.jwt_secret,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def frische_datenbank():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
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
