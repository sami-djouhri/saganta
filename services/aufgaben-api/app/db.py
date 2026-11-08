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


#: Spalten, die nach dem ersten Ausrollen dazukamen. ``create_all`` legt nur
#: fehlende Tabellen an, nie fehlende Spalten; ohne diese Liste liefe der
#: Dienst gegen die alte Tabelle und scheiterte erst beim ersten Lesen.
_NACHZUZIEHEN: dict[str, list[tuple[str, str]]] = {
    "aufgaben": [
        ("projekt", "VARCHAR(120)"),
        ("liste_id", "VARCHAR(36)"),
        ("wo", "VARCHAR(20)"),
        ("ort_name", "VARCHAR(100)"),
        ("wartet_bis", "DATE"),
        ("wartet_auf_id", "VARCHAR(36)"),
        ("wartet_grund", "VARCHAR(300)"),
        ("zeitfenster", "JSON"),
        ("tageszeit", "VARCHAR(12)"),
        ("herkunft", "VARCHAR(64)"),
        ("unteraufgaben", "JSON"),
    ],
}


#: Spalten, die es kurz gab und nicht mehr gibt. ``wer`` stand am 05.11. eine
#: Stunde live (0 Zeilen), dann entschied der Owner dagegen.
_ENTFALLEN: dict[str, list[str]] = {"aufgaben": ["wer"]}


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
            for name in _ENTFALLEN.get(tabelle, []):
                if name in da:
                    conn.execute(text(f"ALTER TABLE {tabelle} DROP COLUMN {name}"))
        # Indizes aus ``__table_args__`` legt create_all an alten Tabellen nicht an.
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_aufgaben_owner_projekt ON aufgaben (owner_sub, projekt)"))
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_aufgaben_herkunft ON aufgaben (owner_sub, herkunft)"))


def init_db() -> None:
    from . import models  # noqa: F401, registriert die Tabellen

    Base.metadata.create_all(engine)
    _spalten_nachziehen()
