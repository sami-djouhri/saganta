import os
import tempfile
from pathlib import Path

import pytest

_tmp = tempfile.mkdtemp(prefix="notizen-test-")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ.setdefault("ANHANG_VERZEICHNIS", f"{_tmp}/anhaenge")
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
            "aud": "notizen-api",
            "iat": jetzt_s,
            "exp": jetzt_s + 300,
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


@pytest.fixture(autouse=True)
def frische_datenbank():
    """Jeder Test startet auf leerem Bestand.

    Die FTS-Tabelle haengt an Triggern auf `notizen`; drop_all kennt sie nicht,
    deshalb raeumen wir sie ausdruecklich mit ab, sonst zeigen die Trigger
    beim naechsten create_all auf einen Index von gestern.
    """
    from sqlalchemy import text

    with engine.begin() as conn:
        for name in ("notizen_fts_ins", "notizen_fts_del", "notizen_fts_upd"):
            conn.execute(text(f"DROP TRIGGER IF EXISTS {name}"))
        conn.execute(text("DROP TABLE IF EXISTS notizen_fts"))
    Base.metadata.drop_all(engine)
    for datei in Path(settings.anhang_verzeichnis).glob("*"):
        datei.unlink(missing_ok=True)
    yield


@pytest.fixture
def client():
    from app import drossel

    drossel.zuruecksetzen()
    with TestClient(app) as c:
        yield c


@pytest.fixture
def kopf():
    return {"Authorization": f"Bearer {token_fuer('nutzer-eins')}"}


@pytest.fixture
def kopf_zwei():
    return {"Authorization": f"Bearer {token_fuer('nutzer-zwei')}"}
