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
    """WAL + FK-Durchsetzung + busy_timeout (No-op bei anderen Backends).

    ``foreign_keys=ON`` ist hier nicht Kosmetik: an ihm haengt, dass Anhaenge und
    Verknuepfungen mit ihrer Notiz verschwinden und Freigaben auf NULL fallen
    statt auf eine spaeter neu vergebene ID zu zeigen.
    """
    if not settings.database_url.startswith("sqlite"):
        return
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.execute("PRAGMA busy_timeout=5000")
    cur.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Ob die Volltextsuche zur Verfuegung steht, entscheidet sich beim Start und
# wird hier gemerkt. suche.py faellt sonst auf LIKE zurueck: langsamer, aber
# nie „Suche kaputt". Ein Dienst, der ohne FTS5 gar nicht startet, waere an
# dieser Stelle die schlechtere Wahl.
FTS_AKTIV = False

_FTS_TABELLE = """
CREATE VIRTUAL TABLE notizen_fts USING fts5(
    titel, inhalt, tags,
    content='notizen', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
)
"""

# Die Trigger halten den Index an der Tabelle. Bei einer external-content-FTS
# muss das Loeschen den ALTEN Inhalt nachreichen ('delete'-Kommando), sonst
# bleiben Leichen im Index stehen und die Suche liefert Treffer auf Zeilen,
# die es nicht mehr gibt.
_FTS_TRIGGER = [
    """
    CREATE TRIGGER notizen_fts_ins AFTER INSERT ON notizen BEGIN
        INSERT INTO notizen_fts(rowid, titel, inhalt, tags)
        VALUES (new.id, new.titel, new.inhalt, new.tags);
    END
    """,
    """
    CREATE TRIGGER notizen_fts_del AFTER DELETE ON notizen BEGIN
        INSERT INTO notizen_fts(notizen_fts, rowid, titel, inhalt, tags)
        VALUES ('delete', old.id, old.titel, old.inhalt, old.tags);
    END
    """,
    """
    CREATE TRIGGER notizen_fts_upd AFTER UPDATE ON notizen BEGIN
        INSERT INTO notizen_fts(notizen_fts, rowid, titel, inhalt, tags)
        VALUES ('delete', old.id, old.titel, old.inhalt, old.tags);
        INSERT INTO notizen_fts(rowid, titel, inhalt, tags)
        VALUES (new.id, new.titel, new.inhalt, new.tags);
    END
    """,
]


def init_db() -> None:
    from . import models  # noqa: F401  (Tabellen registrieren)

    Base.metadata.create_all(engine)
    _volltextsuche_einrichten()


def _volltextsuche_einrichten() -> None:
    global FTS_AKTIV
    if not settings.database_url.startswith("sqlite"):
        return
    insp = inspect(engine)
    tabellen = set(insp.get_table_names())
    try:
        with engine.begin() as conn:
            if "notizen_fts" not in tabellen:
                conn.execute(text(_FTS_TABELLE))
                for ddl in _FTS_TRIGGER:
                    conn.execute(text(ddl))
                # Bestand nachziehen: eine frisch angelegte FTS-Tabelle ist leer,
                # auch wenn `notizen` schon Zeilen hat (Migration eines Bestands).
                conn.execute(text("INSERT INTO notizen_fts(notizen_fts) VALUES('rebuild')"))
        FTS_AKTIV = True
    except Exception:  # FTS5 nicht einkompiliert → LIKE-Rueckfall in suche.py
        FTS_AKTIV = False
