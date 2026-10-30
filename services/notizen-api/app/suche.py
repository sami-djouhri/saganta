"""Volltextsuche ueber die eigenen Notizen.

Zwei Wege, gleiche Antwortform: FTS5, wenn SQLite es mitbringt, sonst LIKE.
Der Rueckfall ist bewusst *kein* Fehlerpfad, er ist langsamer und schlechter
sortiert, aber er liefert.

**Der Mandantenfilter sitzt in beiden Wegen im SQL, nicht dahinter.** Ein
FTS-Treffer ist nur eine rowid; ohne den Join auf ``notizen.owner_sub`` waere
die Suche das eine Loch, durch das fremde Notizen sichtbar werden.
"""

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from . import db

# Ausschnitt-Laenge in Tokens fuer die Trefferzeile.
_AUSSCHNITT_TOKEN = 16


def _fts_ausdruck(q: str) -> str | None:
    """Nutzereingabe in einen FTS5-Ausdruck uebersetzen.

    Jedes Wort wird in Anfuehrungszeichen gesetzt, damit koennen Zeichen wie
    ``-``, ``*`` oder ``OR`` aus der Eingabe die Abfragesprache nicht mehr
    steuern. Nur das letzte Wort bekommt Praefix-Suche, weil man dort noch
    tippt.
    """
    woerter = [w for w in re.split(r"\s+", q.strip()) if w]
    if not woerter:
        return None
    teile: list[str] = []
    for i, w in enumerate(woerter[:12]):
        sauber = w.replace('"', '""')
        letztes = i == len(woerter[:12]) - 1
        teile.append(f'"{sauber}"*' if letztes and len(sauber) >= 2 else f'"{sauber}"')
    return " ".join(teile)


def suchen(
    session: Session,
    owner_sub: str,
    q: str,
    *,
    notizbuch_id: int | None = None,
    archivierte: bool = False,
    limit: int = 50,
) -> list[tuple[int, str]]:
    """Liefert ``[(notiz_id, ausschnitt)]`` nach Relevanz.

    Der Ausschnitt ist reiner Text ohne Auszeichnung; hervorgehoben wird in der
    Oberflaeche, die die Suchbegriffe ohnehin kennt. So kann aus einem
    Suchtreffer kein HTML werden.
    """
    ausdruck = _fts_ausdruck(q)
    if not ausdruck:
        return []

    bedingungen = ["n.owner_sub = :sub"]
    parameter: dict[str, object] = {"sub": owner_sub, "limit": limit}
    if notizbuch_id is not None:
        bedingungen.append("n.notizbuch_id = :buch")
        parameter["buch"] = notizbuch_id
    if not archivierte:
        bedingungen.append("n.archiviert = 0")
    wo = " AND ".join(bedingungen)

    if db.FTS_AKTIV:
        parameter["q"] = ausdruck
        sql = text(
            f"""
            SELECT n.id,
                   snippet(notizen_fts, 1, '', '', '…', {_AUSSCHNITT_TOKEN}) AS ausschnitt
            FROM notizen_fts
            JOIN notizen n ON n.id = notizen_fts.rowid
            WHERE notizen_fts MATCH :q AND {wo}
            ORDER BY bm25(notizen_fts, 4.0, 1.0, 2.0)
            LIMIT :limit
            """
        )
        try:
            return [(r[0], r[1] or "") for r in session.execute(sql, parameter)]
        except Exception:
            # Ein kaputter Ausdruck darf die Suche nicht abstuerzen lassen.
            # Weiter unten im LIKE-Weg.
            pass

    woerter = [w for w in re.split(r"\s+", q.strip()) if w][:6]
    like_bedingungen = []
    for i, w in enumerate(woerter):
        schluessel = f"w{i}"
        parameter[schluessel] = f"%{w.lower()}%"
        like_bedingungen.append(
            f"(lower(n.titel) LIKE :{schluessel} OR lower(n.inhalt) LIKE :{schluessel}"
            f" OR lower(n.tags) LIKE :{schluessel})"
        )
    parameter.pop("q", None)
    sql = text(
        f"""
        SELECT n.id, substr(n.inhalt, 1, 200)
        FROM notizen n
        WHERE {wo} AND {' AND '.join(like_bedingungen)}
        ORDER BY n.geaendert_am DESC
        LIMIT :limit
        """
    )
    return [(r[0], r[1] or "") for r in session.execute(sql, parameter)]
