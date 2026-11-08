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
def _sqlite_pragmas(dbapi_conn, _connection_record):
    """WAL und busy_timeout (No-op bei anderen Backends)."""
    if not settings.database_url.startswith("sqlite"):
        return
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


#: Spalten, die nach dem ersten Ausrollen dazukommen. ``create_all`` legt nur
#: fehlende Tabellen an, nie fehlende Spalten.
_NACHZUZIEHEN: dict[str, list[tuple[str, str]]] = {"kontakte": []}


def _spalten_nachziehen() -> None:
    insp = inspect(engine)
    tabellen = set(insp.get_table_names())
    with engine.begin() as conn:
        for tabelle, spalten in _NACHZUZIEHEN.items():
            if tabelle not in tabellen:
                continue
            da = {c["name"] for c in insp.get_columns(tabelle)}
            for name, ddl in spalten:
                if name not in da:
                    conn.execute(text(f"ALTER TABLE {tabelle} ADD COLUMN {name} {ddl}"))


def init_db() -> None:
    from . import models  # noqa: F401, registriert die Tabellen

    Base.metadata.create_all(engine)
    _spalten_nachziehen()
