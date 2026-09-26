"""Umwandlung Modell → Antwortform und der eine Weg, eine Notiz zu laden."""

import re

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Anhang, Freigabe, Notiz, Notizbuch, Verknuepfung
from .schemas import (
    AnhangAus,
    FreigabeAus,
    NotizAus,
    NotizbuchAus,
    NotizKurzAus,
    VerknuepfungAus,
)
from .util import tags_lesen

_AUSSCHNITT_ZEICHEN = 180


def notiz_holen(session: Session, owner_sub: str, notiz_id: int) -> Notiz:
    """Die einzige Stelle, an der eine Notiz per ID geladen wird.

    Dass der Mandantenfilter hier drin steckt, ist der Grund fuer die Funktion:
    ``session.get(Notiz, id)`` ohne ``owner_sub`` waere jederzeit einen
    Tastendruck entfernt und faellt in keinem Test auf, solange nur ein Konto
    existiert.
    """
    notiz = session.scalar(
        select(Notiz).where(Notiz.id == notiz_id, Notiz.owner_sub == owner_sub)
    )
    if notiz is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notiz nicht gefunden")
    return notiz


def ausschnitt(inhalt: str) -> str:
    """Erste Zeilen als Vorschau, ohne Markdown-Zeichen."""
    text = re.sub(r"^#{1,6}\s*|^[-*+]\s+|^>\s*|`{1,3}", "", inhalt or "", flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:_AUSSCHNITT_ZEICHEN]


def notizbuch_aus(buch: Notizbuch, anzahl: int = 0) -> NotizbuchAus:
    return NotizbuchAus(
        id=buch.id,
        name=buch.name,
        farbe=buch.farbe,
        sortierung=buch.sortierung,
        erstellt_am=buch.erstellt_am,
        anzahl_notizen=anzahl,
    )


def verknuepfung_aus(v: Verknuepfung) -> VerknuepfungAus:
    return VerknuepfungAus(id=v.id, typ=v.typ, ref=v.ref, label=v.label, erstellt_am=v.erstellt_am)


def anhang_aus(a: Anhang) -> AnhangAus:
    return AnhangAus(
        id=a.id, dateiname=a.dateiname, mime=a.mime, groesse=a.groesse, erstellt_am=a.erstellt_am
    )


def freigabe_aus(f: Freigabe) -> FreigabeAus:
    return FreigabeAus(
        id=f.id,
        merkmal=f.merkmal,
        modus=f.modus,
        zustand=f.zustand(),
        ablauf_am=f.ablauf_am,
        max_abrufe=f.max_abrufe,
        abrufe=f.abrufe,
        passwortgeschuetzt=bool(f.passwort_hash) or f.schluessel_quelle == "passwort",
        mit_anhaengen=f.mit_anhaengen,
        notiz_id=f.notiz_id,
        notiz_titel=f.notiz_titel_kopie,
        erstellt_am=f.erstellt_am,
        letzter_abruf_am=f.letzter_abruf_am,
    )


def notiz_aus(notiz: Notiz) -> NotizAus:
    return NotizAus(
        id=notiz.id,
        titel=notiz.titel,
        inhalt=notiz.inhalt,
        tags=tags_lesen(notiz.tags),
        notizbuch_id=notiz.notizbuch_id,
        angeheftet=notiz.angeheftet,
        archiviert=notiz.archiviert,
        erstellt_am=notiz.erstellt_am,
        geaendert_am=notiz.geaendert_am,
        anhaenge=[anhang_aus(a) for a in notiz.anhaenge],
        verknuepfungen=[verknuepfung_aus(v) for v in notiz.verknuepfungen],
        freigaben=[freigabe_aus(f) for f in notiz.freigaben if f.widerrufen_am is None],
    )


def notizen_kurz(
    session: Session, notizen: list[Notiz], ausschnitte: dict[int, str] | None = None
) -> list[NotizKurzAus]:
    """Listendarstellung mit den Zaehlern in *einer* Abfrage je Art.

    Ohne die Sammelzaehlung waeren das drei Abfragen je Notiz, bei 200 Notizen
    600 Roundtrips fuer drei Zahlen, die niemand einzeln braucht.
    """
    ids = [n.id for n in notizen]
    if not ids:
        return []

    def zaehlen(modell, spalte, zusatz=None) -> dict[int, int]:
        anfrage = select(spalte, func.count()).where(spalte.in_(ids))
        if zusatz is not None:
            anfrage = anfrage.where(zusatz)
        return dict(session.execute(anfrage.group_by(spalte)).all())

    anhaenge = zaehlen(Anhang, Anhang.notiz_id)
    verknuepfungen = zaehlen(Verknuepfung, Verknuepfung.notiz_id)
    freigaben = zaehlen(Freigabe, Freigabe.notiz_id, Freigabe.widerrufen_am.is_(None))

    return [
        NotizKurzAus(
            id=n.id,
            titel=n.titel,
            ausschnitt=(ausschnitte or {}).get(n.id) or ausschnitt(n.inhalt),
            tags=tags_lesen(n.tags),
            notizbuch_id=n.notizbuch_id,
            angeheftet=n.angeheftet,
            archiviert=n.archiviert,
            anzahl_anhaenge=anhaenge.get(n.id, 0),
            anzahl_verknuepfungen=verknuepfungen.get(n.id, 0),
            anzahl_freigaben=freigaben.get(n.id, 0),
            erstellt_am=n.erstellt_am,
            geaendert_am=n.geaendert_am,
        )
        for n in notizen
    ]
