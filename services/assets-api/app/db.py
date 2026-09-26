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


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Tabellen anlegen und die Mandantenspalte nachziehen.

    `assets` gab es vor dem 30.08.2026 ohne `owner_sub`: jeder zugelassene Nutzer
    sah dasselbe Inventar, und nur ALLOWED_SUBS verhinderte das. Die Spalte laesst
    sich hier nicht mit einem ALTER nachruesten, weil zugleich der eindeutige
    Schluessel von (source, source_id) auf (owner_sub, source, source_id) wechselt
    und SQLite Constraints nicht aendern kann. Deshalb der uebliche Umweg:
    umbenennen, neu anlegen, umkopieren.
    """
    from . import models  # noqa: F401 - Tabellen registrieren

    insp = inspect(engine)
    if "assets" in insp.get_table_names():
        spalten = {s["name"] for s in insp.get_columns("assets")}
        if "owner_sub" not in spalten:
            _assets_auf_mandanten_umstellen(sorted(spalten))

    Base.metadata.create_all(engine)
    _reste_der_umstellung_beseitigen()


def _assets_auf_mandanten_umstellen(alte_spalten: list[str]) -> None:
    with engine.begin() as conn:
        anzahl = conn.execute(text("select count(*) from assets")).scalar() or 0
        besitzer = _backfill_sub()
        if anzahl and not besitzer:
            # Fail-closed. Die Alternative waere, die Zeilen einem beliebigen Sub
            # zuzuschlagen oder auf NULL zu lassen. Beides sieht danach aus wie
            # eine gelungene Migration und ist genau das nicht: im ersten Fall
            # gehoert fremdes Inventar jemandem, im zweiten sieht es niemand mehr.
            raise RuntimeError(
                f"assets: {anzahl} Zeile(n) ohne owner_sub, aber kein eindeutiger "
                "Besitzer bestimmbar (ALLOWED_SUBS leer oder mehrdeutig). "
                "ASSETS_BACKFILL_SUB setzen und neu starten."
            )
        # ★ Erst die Indizes weg, dann umbenennen. SQLite zieht Indizes beim
        # Umbenennen mit, ihre Namen bleiben aber belegt: `ix_assets_source` haengt
        # danach an `assets_vor_mandanten` und blockiert das Neuanlegen an der
        # neuen Tabelle. Gemessen am 30.08. genau so passiert, der Dienst kam mit
        # OperationalError nicht hoch. Die alte Tabelle wird ohnehin gleich
        # verworfen, ihre Indizes braucht niemand mehr.
        for index in inspect(conn).get_indexes("assets"):
            conn.execute(text(f'DROP INDEX IF EXISTS "{index["name"]}"'))
        conn.execute(text("ALTER TABLE assets RENAME TO assets_vor_mandanten"))
        Base.metadata.create_all(conn)
        if anzahl:
            felder = ", ".join(f'"{s}"' for s in alte_spalten)
            # ★ Die Zeitstempel sind im neuen Schema NOT NULL, in einer alten Zeile
            # koennen sie leer sein (etwa aus einem Import oder einer frueheren
            # Fassung). Eine Migration, die daran scheitert, laesst den Dienst beim
            # Start abbrechen und in einer Neustartschleife enden, also genau dort,
            # wo niemand mehr die Ursache sucht. Ein fehlender Zeitstempel ist die
            # harmlosere Ungenauigkeit als ein Dienst, der nicht hochkommt.
            werte = ", ".join(
                "COALESCE(\"{0}\", CURRENT_TIMESTAMP)".format(s)
                if s in ("created_at", "updated_at")
                else f'"{s}"'
                for s in alte_spalten
            )
            conn.execute(
                text(
                    f"INSERT INTO assets (owner_sub, {felder}) "
                    f"SELECT :besitzer, {werte} FROM assets_vor_mandanten"
                ),
                {"besitzer": besitzer},
            )
        conn.execute(text("DROP TABLE assets_vor_mandanten"))


def _reste_der_umstellung_beseitigen() -> None:
    """Raeumt einen abgebrochenen Umbau auf, statt ihn liegen zu lassen.

    Bricht die Umstellung in der Mitte ab, bleibt `assets_vor_mandanten` stehen,
    und weil `create_all` an einer vorhandenen Tabelle keine Indizes mehr anlegt,
    laeuft der Dienst danach ohne sie weiter: er funktioniert, wird aber mit jeder
    Zeile langsamer, und niemand sieht warum. Deshalb wird hier beides geprueft,
    bei jedem Start und ohne Nebenwirkung, wenn nichts zu tun ist.
    """
    insp = inspect(engine)
    tabellen = set(insp.get_table_names())
    if "assets" not in tabellen:
        return
    spalten = {s["name"] for s in insp.get_columns("assets")}
    if "owner_sub" not in spalten:
        return  # noch nicht umgestellt, hier gibt es nichts aufzuraeumen

    with engine.begin() as conn:
        if "assets_vor_mandanten" in tabellen:
            uebrig = conn.execute(text("select count(*) from assets_vor_mandanten")).scalar() or 0
            neu = conn.execute(text("select count(*) from assets")).scalar() or 0
            if uebrig and not neu:
                # Der seltene, aber teure Fall: die Daten stehen noch in der alten
                # Tabelle und die neue ist leer. Hier wird nichts verworfen.
                raise RuntimeError(
                    f"assets: Umstellung unvollstaendig, {uebrig} Zeile(n) liegen in "
                    "assets_vor_mandanten und assets ist leer. Von Hand pruefen, "
                    "bevor der Dienst weiterlaeuft."
                )
            for index in inspect(conn).get_indexes("assets_vor_mandanten"):
                conn.execute(text(f'DROP INDEX IF EXISTS "{index["name"]}"'))
            conn.execute(text("DROP TABLE assets_vor_mandanten"))

    # Fehlende Indizes des Zielschemas nachziehen (checkfirst = kein Fehler,
    # wenn sie schon da sind).
    from .models import Asset

    with engine.begin() as conn:
        for index in Asset.__table__.indexes:
            index.create(conn, checkfirst=True)


def _backfill_sub() -> str | None:
    """Wem gehoeren die Zeilen aus der Zeit vor der Mandantentrennung?

    Nur beantwortbar, wenn es genau einen Kandidaten gibt: entweder ausdruecklich
    gesetzt oder der einzige zugelassene Sub. Bei mehreren waere jede Wahl geraten.
    """
    if settings.assets_backfill_sub:
        return settings.assets_backfill_sub
    if len(settings.allowed_subs) == 1:
        return settings.allowed_subs[0]
    return None
