"""Verweise zwischen Notizen (seit 2026-11-20).

Zwei Arten, und beide zeigen sich an jeder Notiz:

* **Verbunden**: von Hand gesetzt, ungerichtet, eine Zeile in
  ``notiz_verweise``. Mehrere Notizen auf einmal verbinden heisst: jede mit
  jeder (``POST /verbinden``).
* **``[[Titel]]`` im Text**: wird beim Lesen aus dem Text bestimmt und nicht
  gespeichert. Die Notiz zeigt, worauf sie verweist (``verweist_auf``), die
  Zielnotiz, wo sie erwaehnt wird (``erwaehnt_in``).

Aufgeloest wird ueber den Titel, ohne Gross- und Kleinschreibung. Tragen zwei
Notizen denselben Titel, gewinnt die zuletzt geaenderte; ein Verweis auf einen
Titel, den es nicht gibt, kommt mit ``id`` None zurueck, damit die Oberflaeche
ihn zum Anlegen anbieten kann statt ihn wortlos als Text zu zeigen.
"""

import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .auth import Me, verify_jwt
from .db import get_db
from .helfer import ausschnitt, notiz_holen
from .models import Notiz, NotizVerweis
from .schemas import (
    GesamtKante,
    GesamtKnoten,
    GesamtNetzAus,
    NetzAus,
    TitelTreffer,
    NotizVerweisAus,
    TextVerweisAus,
    VerbindenAn,
    VerbindenAus,
    VerbundenAn,
)

router = APIRouter()

# [[Titel]] oder [[Titel|Anzeige]], wie in Obsidian. Kein Zeilenumbruch und keine
# eckige Klammer im Titel; dieselbe Regel steht in apps/notizen/src/lib/markdown.ts.
TEXT_VERWEIS = re.compile(r"\[\[([^\[\]|\n]{1,300})(?:\|[^\[\]\n]{0,300})?\]\]")


def _schluessel(titel: str) -> str:
    return " ".join(titel.split()).casefold()


def text_verweise(inhalt: str) -> list[str]:
    """Die ``[[Titel]]`` eines Texts, in Reihenfolge, jeder Titel einmal.

    Inline-Code und Codebloecke zaehlen nicht mit: dort ist ``[[x]]`` Beispiel,
    nicht Verweis, und die Oberflaeche zeigt es dort auch nicht als Link.
    """
    ohne_code = re.sub(r"```.*?(```|\Z)", " ", inhalt or "", flags=re.DOTALL)
    ohne_code = re.sub(r"`[^`\n]*`", " ", ohne_code)
    gesehen: set[str] = set()
    aus: list[str] = []
    for treffer in TEXT_VERWEIS.finditer(ohne_code):
        titel = " ".join(treffer.group(1).split())
        if titel and _schluessel(titel) not in gesehen:
            gesehen.add(_schluessel(titel))
            aus.append(titel)
    return aus


def _kurz(n: Notiz) -> NotizVerweisAus:
    return NotizVerweisAus(
        id=n.id, titel=n.titel, ausschnitt=ausschnitt(n.inhalt),
        notizbuch_id=n.notizbuch_id, archiviert=n.archiviert,
    )


def _paar(x: int, y: int) -> tuple[int, int]:
    return (x, y) if x < y else (y, x)


def verbundene_ids(db: Session, sub: str, notiz_id: int) -> list[int]:
    zeilen = db.execute(
        select(NotizVerweis.a_id, NotizVerweis.b_id).where(
            NotizVerweis.owner_sub == sub,
            or_(NotizVerweis.a_id == notiz_id, NotizVerweis.b_id == notiz_id),
        )
    ).all()
    return [b if a == notiz_id else a for a, b in zeilen]


def verbinden_paare(db: Session, sub: str, ids: list[int]) -> tuple[int, int]:
    """Jede der Notizen mit jeder verbinden; gibt (neu, vorhanden) zurueck.

    Die Kennungen muessen vorher geprueft sein (Mandant). Bestehende Paare
    bleiben, wie sie sind, ein zweiter Aufruf aendert nichts.
    """
    eindeutig = sorted(set(ids))
    vorhanden = set(
        db.execute(
            select(NotizVerweis.a_id, NotizVerweis.b_id).where(
                NotizVerweis.owner_sub == sub,
                NotizVerweis.a_id.in_(eindeutig),
                NotizVerweis.b_id.in_(eindeutig),
            )
        ).all()
    )
    neu = 0
    for i, a in enumerate(eindeutig):
        for b in eindeutig[i + 1:]:
            if (a, b) in vorhanden:
                continue
            db.add(NotizVerweis(owner_sub=sub, a_id=a, b_id=b))
            neu += 1
    return neu, len(vorhanden)


def titel_karte(db: Session, sub: str) -> dict[str, int]:
    """Titel → Notiz, die zuletzt geaenderte gewinnt bei Gleichstand."""
    nach_titel: dict[str, int] = {}
    for nid, titel in db.execute(
        select(Notiz.id, Notiz.titel)
        .where(Notiz.owner_sub == sub, Notiz.titel != "")
        .order_by(Notiz.geaendert_am.asc())
    ):
        nach_titel[_schluessel(titel)] = nid
    return nach_titel


def _eigene_pruefen(db: Session, sub: str, ids: set[int]) -> None:
    gefunden = set(db.scalars(select(Notiz.id).where(Notiz.owner_sub == sub, Notiz.id.in_(ids))))
    if gefunden != ids:
        # Eine fremde Kennung meldet sich wie eine fehlende: ob es sie bei
        # jemand anderem gibt, geht den Aufrufer nichts an.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notiz nicht gefunden")


@router.get("/titel", response_model=list[TitelTreffer])
def titel_suchen(
    q: str = Query(default="", max_length=300),
    limit: int = Query(default=8, ge=1, le=30),
    ohne: int | None = None,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> list[TitelTreffer]:
    """Notiztitel fuer die Vorschlaege beim Tippen von ``[[``.

    Erst die Titel, die mit der Eingabe beginnen, dann die, die sie enthalten,
    je zuletzt geaenderte zuerst. Verglichen wird in Python mit ``casefold``:
    SQLites ``lower`` kennt nur ASCII, "Ärger" faende "ärg" dort nicht.
    """
    eingabe = _schluessel(q)
    vorne: list[TitelTreffer] = []
    mitte: list[TitelTreffer] = []
    gesehen: set[str] = set()
    for nid, titel, archiviert in db.execute(
        select(Notiz.id, Notiz.titel, Notiz.archiviert)
        .where(Notiz.owner_sub == me.sub, Notiz.titel != "")
        .order_by(Notiz.geaendert_am.desc())
    ):
        schluessel = _schluessel(titel)
        # Gleichnamige zeigen sich einmal: der Verweis fuehrt ohnehin zur
        # zuletzt geaenderten, und genau die steht hier zuerst.
        if nid == ohne or not schluessel or schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        treffer = TitelTreffer(id=nid, titel=" ".join(titel.split()), archiviert=archiviert)
        if schluessel.startswith(eingabe):
            vorne.append(treffer)
        elif eingabe in schluessel:
            mitte.append(treffer)
        if len(vorne) >= limit:
            break
    return (vorne + mitte)[:limit]


@router.get("/netz", response_model=GesamtNetzAus)
def gesamtnetz(
    archivierte: bool = False,
    me: Me = Depends(verify_jwt),
    db: Session = Depends(get_db),
) -> GesamtNetzAus:
    """Alle eigenen Notizen und ihre Verweise, fuer die Netzansicht.

    Eine Kante je Paar: ist ein Paar von Hand verbunden UND per ``[[ ]]``
    verwiesen, gilt die Hand (``art`` "verbunden"). Ein ``[[Titel]]`` ohne
    Zielnotiz ergibt keine Kante, sondern zaehlt bei ``offene_verweise`` der
    Quelle mit.
    """
    anfrage = select(Notiz.id, Notiz.titel, Notiz.notizbuch_id, Notiz.archiviert, Notiz.angeheftet).where(
        Notiz.owner_sub == me.sub
    )
    if not archivierte:
        anfrage = anfrage.where(Notiz.archiviert.is_(False))
    zeilen = db.execute(anfrage.order_by(Notiz.geaendert_am.desc())).all()
    sichtbar = {z.id for z in zeilen}

    kanten: dict[tuple[int, int], GesamtKante] = {}
    for a, b in db.execute(
        select(NotizVerweis.a_id, NotizVerweis.b_id).where(NotizVerweis.owner_sub == me.sub)
    ):
        if a in sichtbar and b in sichtbar:
            kanten[(a, b)] = GesamtKante(a=a, b=b, art="verbunden")

    nach_titel = titel_karte(db, me.sub)
    offen: dict[int, int] = {}
    for nid, inhalt in db.execute(
        select(Notiz.id, Notiz.inhalt).where(Notiz.owner_sub == me.sub, Notiz.inhalt.contains("[["))
    ):
        if nid not in sichtbar:
            continue
        for titel in text_verweise(inhalt):
            ziel = nach_titel.get(_schluessel(titel))
            if ziel is None:
                offen[nid] = offen.get(nid, 0) + 1
            elif ziel != nid and ziel in sichtbar and _paar(nid, ziel) not in kanten:
                # Gerichtet: a verweist auf b. Die Rueckrichtung als eigene
                # Kante zu fuehren, zeichnete dieselbe Linie zweimal.
                kanten[_paar(nid, ziel)] = GesamtKante(a=nid, b=ziel, art="text")

    grad: dict[int, int] = {}
    for k in kanten.values():
        grad[k.a] = grad.get(k.a, 0) + 1
        grad[k.b] = grad.get(k.b, 0) + 1
    return GesamtNetzAus(
        knoten=[
            GesamtKnoten(
                id=z.id, titel=z.titel, notizbuch_id=z.notizbuch_id, archiviert=z.archiviert,
                angeheftet=z.angeheftet, grad=grad.get(z.id, 0), offene_verweise=offen.get(z.id, 0),
            )
            for z in zeilen
        ],
        kanten=list(kanten.values()),
    )


@router.get("/{notiz_id}/netz", response_model=NetzAus)
def netz(notiz_id: int, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> NetzAus:
    """Alles, was mit dieser Notiz verbunden ist: von Hand, per ``[[ ]]`` hin und zurueck."""
    notiz = notiz_holen(db, me.sub, notiz_id)

    ids = verbundene_ids(db, me.sub, notiz.id)
    verbunden = db.scalars(
        select(Notiz).where(Notiz.owner_sub == me.sub, Notiz.id.in_(ids))
        .order_by(Notiz.geaendert_am.desc())
    ).all() if ids else []

    nach_titel = titel_karte(db, me.sub)

    verweist_auf = [
        TextVerweisAus(text=t, id=nach_titel.get(_schluessel(t)))
        for t in text_verweise(notiz.inhalt)
    ]

    erwaehnt_in: list[NotizVerweisAus] = []
    eigener = _schluessel(notiz.titel) if notiz.titel.strip() else None
    # Nur wenn dieser Titel auch wirklich auf diese Notiz aufloest: bei zwei
    # gleichnamigen gehoeren die Erwaehnungen der, auf die der Link fuehrt.
    if eigener and nach_titel.get(eigener) == notiz.id:
        kandidaten = db.scalars(
            select(Notiz).where(
                Notiz.owner_sub == me.sub, Notiz.id != notiz.id, Notiz.inhalt.contains("[[")
            ).order_by(Notiz.geaendert_am.desc())
        ).all()
        for k in kandidaten:
            if any(_schluessel(t) == eigener for t in text_verweise(k.inhalt)):
                erwaehnt_in.append(_kurz(k))

    return NetzAus(
        verbunden=[_kurz(n) for n in verbunden],
        erwaehnt_in=erwaehnt_in,
        verweist_auf=verweist_auf,
    )


@router.post("/verbinden", response_model=VerbindenAus)
def verbinden(daten: VerbindenAn, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)) -> VerbindenAus:
    """Mehrere Notizen miteinander verbinden, jede mit jeder, in einem Schritt.

    Ganz oder gar nicht: ist eine Kennung unbekannt, entsteht keine Verbindung.
    """
    ids = set(daten.ids)
    if len(ids) < 2:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Mindestens zwei verschiedene Notizen")
    _eigene_pruefen(db, me.sub, ids)
    neu, vorhanden = verbinden_paare(db, me.sub, list(ids))
    try:
        db.commit()
    except IntegrityError:
        # Ein paralleler Aufruf hat dasselbe Paar eben angelegt; der zweite
        # Versuch sieht es als vorhanden.
        db.rollback()
        neu, vorhanden = verbinden_paare(db, me.sub, list(ids))
        db.commit()
    return VerbindenAus(neu=neu, vorhanden=vorhanden)


@router.post("/{notiz_id}/verbunden", response_model=list[NotizVerweisAus], status_code=status.HTTP_201_CREATED)
def verbunden_setzen(
    notiz_id: int, daten: VerbundenAn, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)
) -> list[NotizVerweisAus]:
    """Diese Notiz mit einer weiteren verbinden; Antwort ist die neue Liste der verbundenen."""
    if daten.mit == notiz_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Eine Notiz kann nicht mit sich selbst verbunden werden")
    _eigene_pruefen(db, me.sub, {notiz_id, daten.mit})
    verbinden_paare(db, me.sub, [notiz_id, daten.mit])
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    ids = verbundene_ids(db, me.sub, notiz_id)
    return [_kurz(n) for n in db.scalars(
        select(Notiz).where(Notiz.owner_sub == me.sub, Notiz.id.in_(ids)).order_by(Notiz.geaendert_am.desc())
    )]


@router.delete("/{notiz_id}/verbunden/{mit}", status_code=status.HTTP_204_NO_CONTENT)
def verbunden_loesen(
    notiz_id: int, mit: int, me: Me = Depends(verify_jwt), db: Session = Depends(get_db)
) -> None:
    a, b = _paar(notiz_id, mit)
    ergebnis = db.execute(
        delete(NotizVerweis).where(
            NotizVerweis.owner_sub == me.sub, NotizVerweis.a_id == a, NotizVerweis.b_id == b
        )
    )
    if ergebnis.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Verbindung nicht gefunden")
    db.commit()
