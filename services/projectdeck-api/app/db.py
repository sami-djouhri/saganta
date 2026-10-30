from sqlalchemy import create_engine, inspect, text, event
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


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """create_all + idempotente leichte ALTER-Guards (Kalender-/Native-Pattern).

    Neue Spalten an bestehenden Tabellen werden hier additiv nachgezogen, ohne
    Alembic. Jede ALTER-Anweisung ist über die Live-Spaltenliste geschützt.
    """
    from . import models  # noqa: F401  (Tabellen registrieren)

    Base.metadata.create_all(engine)
    _run_light_migrations()


# (Spalte, DDL): additiv erweiterbar bei späteren Feldern.
_LIGHT_MIGRATIONS: dict[str, list[tuple[str, str]]] = {
    # "projects": [("new_col", "ALTER TABLE projects ADD COLUMN new_col TEXT")],
}


def _run_light_migrations() -> None:
    if not settings.database_url.startswith("sqlite"):
        return
    insp = inspect(engine)
    existing_tables = set(insp.get_table_names())
    with engine.begin() as conn:
        for table, cols in _LIGHT_MIGRATIONS.items():
            if table not in existing_tables:
                continue
            present = {c["name"] for c in insp.get_columns(table)}
            for col, ddl in cols:
                if col not in present:
                    conn.execute(text(ddl))
