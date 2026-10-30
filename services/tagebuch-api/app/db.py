from sqlalchemy import create_engine, event
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
    """WAL und busy_timeout (No-op bei anderen Backends).

    ``foreign_keys`` steht hier bewusst nicht: es gibt keine Fremdschluessel.
    Eintraege und Tresor haengen nur ueber ``owner_sub`` zusammen, und zwar
    absichtlich lose. Ein Tresor, der beim Loeschen des letzten Eintrags
    mitginge, waere ein Datenverlust mit Ansage.
    """
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


def init_db() -> None:
    from . import models  # noqa: F401, registriert die Tabellen

    Base.metadata.create_all(engine)
