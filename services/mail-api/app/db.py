from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    """WAL + FK-Enforcement + busy_timeout fuer SQLite (No-op bei anderen Backends)."""
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


# (Spalte, DDL) je Tabelle. Additiv erweiterbar bei spaeteren Feldern.
#
# ★★ Ohne diese Nachziehung waeren die OAuth2-Spalten in einer **bestehenden**
# Datenbank nie entstanden: `Base.metadata.create_all()` legt fehlende Tabellen
# an, aber keine fehlenden Spalten. Der Dienst waere gestartet, gesund gemeldet
# und bei der ersten Abfrage mit „no such column: mail_accounts.auth_typ"
# gescheitert, also erst im Betrieb und mit einer Meldung, die nach einem
# kaputten Deploy aussieht.
#
# Dasselbe Muster wie in `projectdeck-api/app/db.py` und im nativen Kalender.
_LEICHTE_MIGRATIONEN: dict[str, list[tuple[str, str]]] = {
    "mail_accounts": [
        # Vorgabewert 'passwort': jedes bestehende Konto bleibt damit genau das,
        # was es war, und laeuft ohne Zutun weiter.
        (
            "auth_typ",
            "ALTER TABLE mail_accounts ADD COLUMN auth_typ VARCHAR(20) "
            "NOT NULL DEFAULT 'passwort'",
        ),
        ("oauth_anbieter", "ALTER TABLE mail_accounts ADD COLUMN oauth_anbieter VARCHAR(40)"),
        ("oauth_zugriff_cipher", "ALTER TABLE mail_accounts ADD COLUMN oauth_zugriff_cipher TEXT"),
        ("oauth_laeuft_ab", "ALTER TABLE mail_accounts ADD COLUMN oauth_laeuft_ab DATETIME"),
    ],
}


def leichte_migrationen() -> None:
    """Fehlende Spalten additiv nachziehen, jede ueber die Live-Spaltenliste geschuetzt."""
    if not settings.database_url.startswith("sqlite"):
        return
    pruefer = inspect(engine)
    vorhandene_tabellen = set(pruefer.get_table_names())
    with engine.begin() as conn:
        for tabelle, spalten in _LEICHTE_MIGRATIONEN.items():
            if tabelle not in vorhandene_tabellen:
                continue
            da = {c["name"] for c in pruefer.get_columns(tabelle)}
            for spalte, ddl in spalten:
                if spalte not in da:
                    conn.execute(text(ddl))


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
