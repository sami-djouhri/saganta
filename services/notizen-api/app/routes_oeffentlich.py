"""Der oeffentliche Pfad: eine Freigabe abrufen, ohne Konto.

Hier gilt eine andere Hausordnung als im Rest des Dienstes. Vier Entscheidungen
tragen ihn:

**Ansehen und Oeffnen sind zwei Schritte.** ``GET`` sagt nur, ob sich hier etwas
oeffnen laesst und was dafuer noetig ist, der Inhalt kostet ein ausdrueckliches
``POST``. Der Grund ist handfest: Messenger und Chatgruppen holen jeden
geteilten Link automatisch fuer die Vorschau. Wuerde ``GET`` den Inhalt
liefern, waere eine „einmal lesen"-Notiz verbraucht, bevor der Empfaenger sie
ueberhaupt gesehen hat, und die Vorschau haette sie dem Messenger-Betreiber
gezeigt. Genau daran krankt die Gattung.

**Der Zaehler wird bedingt hochgesetzt, nicht gelesen und dann geschrieben.**
Zwei gleichzeitige Abrufe wuerden sonst beide „noch nicht verbraucht" sehen und
beide den Text bekommen. Bei „einmal lesen" ist das kein Schoenheitsfehler,
sondern der Bruch der einen Zusage, die diese Betriebsart macht.

**Verbraucht heisst geloescht.** Ist der letzte Abruf getan, verschwindet das
Chiffrat aus der Zeile.

**Es gibt keine Auskunft ueber den Absender.** Kein Titel, kein Konto, kein
Hinweis auf die Notiz, bis der Inhalt tatsaechlich ausgeliefert wird.
"""

import time

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from . import drossel
from .db import get_db
from .models import Anhang, Freigabe
from .routes_notizen import datei_antwort
from .schein import ausstellen, gueltig
from .schemas import (
    OeffentlicherAnhang,
    OeffentlicherInhalt,
    OeffentlicherZustand,
    OeffnenAn,
)
from .util import jetzt, passwort_stimmt

router = APIRouter()

# Zugriffe je Minute und Quelle. Ansehen darf haeufiger sein als Oeffnen:
# ein Empfaenger laedt die Seite schon mal neu, probiert aber keine zwanzig
# Passwoerter.
_GRENZE_ANSEHEN = 60
_GRENZE_OEFFNEN = 20
_GRENZE_ANHANG = 60

_ZUSTAND_MELDUNG = {
    "widerrufen": "Diese Notiz wurde vom Absender zurueckgezogen.",
    "abgelaufen": "Der Link ist abgelaufen.",
    "verbraucht": "Diese Notiz wurde bereits geoeffnet und ist nicht mehr abrufbar.",
    "gesperrt": "Zu viele Fehlversuche, der Link ist gesperrt.",
    "quelle_weg": "Die zugehoerige Notiz existiert nicht mehr.",
}


def _quelle(request: Request) -> str:
    """Anfragende Quelle fuer die Bremse.

    Der Dienst ist nur im internen Netz erreichbar und steht hinter dem
    dev-portal, die echte Adresse steht deshalb in ``X-Forwarded-For``.
    Kaeme jemand am Rand vorbei direkt an den Container, koennte er sich den
    Wert ausdenken; das waere aber schon fuer sich das groessere Problem und
    wird nicht hier geloest, sondern durch das Netz davor.
    """
    weitergereicht = request.headers.get("x-forwarded-for", "")
    if weitergereicht:
        return weitergereicht.split(",")[0].strip()[:60]
    return (request.client.host if request.client else "unbekannt")[:60]


def _bremsen(request: Request, grenze: int, zweck: str) -> None:
    if not drossel.erlaubt(f"{zweck}:{_quelle(request)}", grenze, time.monotonic()):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Zu viele Anfragen. Bitte kurz warten.",
            headers={"Retry-After": "60"},
        )


def _freigabe_laden(db: Session, merkmal: str) -> Freigabe:
    freigabe = db.scalar(select(Freigabe).where(Freigabe.merkmal == merkmal))
    if freigabe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Dieser Link existiert nicht.")
    return freigabe


@router.get("/{merkmal}", response_model=OeffentlicherZustand)
def zustand(
    merkmal: str,
    request: Request,
    db: Session = Depends(get_db),
) -> OeffentlicherZustand:
    _bremsen(request, _GRENZE_ANSEHEN, "ansehen")
    freigabe = _freigabe_laden(db, merkmal)
    verbleibend = (
        None if freigabe.max_abrufe is None else max(freigabe.max_abrufe - freigabe.abrufe, 0)
    )
    return OeffentlicherZustand(
        modus=freigabe.modus,
        zustand=freigabe.zustand(),
        braucht_passwort=bool(freigabe.passwort_hash) or freigabe.schluessel_quelle == "passwort",
        einmalig=freigabe.max_abrufe == 1,
        verbleibende_abrufe=verbleibend,
        ablauf_am=freigabe.ablauf_am,
        schluessel_quelle=freigabe.schluessel_quelle,
        algo=freigabe.algo,
        kdf_salz=freigabe.kdf_salz,
        kdf_iterationen=freigabe.kdf_iterationen,
    )


@router.post("/{merkmal}/oeffnen", response_model=OeffentlicherInhalt)
def oeffnen(
    merkmal: str,
    request: Request,
    response: Response,
    daten: OeffnenAn | None = None,
    db: Session = Depends(get_db),
) -> OeffentlicherInhalt:
    _bremsen(request, _GRENZE_OEFFNEN, "oeffnen")
    freigabe = _freigabe_laden(db, merkmal)

    lage = freigabe.zustand()
    if lage != "aktiv":
        raise HTTPException(status.HTTP_410_GONE, _ZUSTAND_MELDUNG.get(lage, "Nicht abrufbar."))

    # --- Passwort (nur Modus 'offen'; bei 'chiffriert' prueft der Browser) ---
    if freigabe.passwort_hash:
        angeboten = (daten.passwort if daten else None) or ""
        if not angeboten or not passwort_stimmt(
            angeboten, freigabe.passwort_hash, freigabe.passwort_salz or ""
        ):
            freigabe.fehlversuche += 1
            db.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Passwort stimmt nicht.")

    # --- Abruf verbuchen, bevor etwas herausgegeben wird --------------------
    # Bedingtes UPDATE: nur wer den Zaehler tatsaechlich weiterdrehen konnte,
    # bekommt den Inhalt. Zwei gleichzeitige Abrufe auf eine Einmal-Notiz
    # koennen so nicht beide gewinnen.
    #
    # Der Zeitwert geht als Zeichenkette hinein, nicht als ``datetime``: Pythons
    # eingebauter sqlite3-Wandler dafuer gilt seit 3.12 als ueberholt und
    # verschwindet. Das Format ist genau das, in dem SQLAlchemy DateTime-Spalten
    # in SQLite ablegt, nur so vergleicht das ``>`` oben das Richtige.
    jetzt_sql = jetzt().strftime("%Y-%m-%d %H:%M:%S.%f")
    verbucht = db.execute(
        text(
            """
            UPDATE freigaben
               SET abrufe = abrufe + 1, letzter_abruf_am = :jetzt
             WHERE id = :id
               AND widerrufen_am IS NULL
               AND (max_abrufe IS NULL OR abrufe < max_abrufe)
               AND (ablauf_am IS NULL OR ablauf_am > :jetzt)
            """
        ),
        {"id": freigabe.id, "jetzt": jetzt_sql},
    )
    if verbucht.rowcount != 1:
        db.rollback()
        raise HTTPException(
            status.HTTP_410_GONE, "Diese Notiz wurde soeben bereits geoeffnet."
        )
    db.commit()
    db.refresh(freigabe)

    verbleibend = (
        None if freigabe.max_abrufe is None else max(freigabe.max_abrufe - freigabe.abrufe, 0)
    )
    einmalig = freigabe.max_abrufe == 1

    if freigabe.modus == "chiffriert":
        ergebnis = OeffentlicherInhalt(
            modus="chiffriert",
            titel="",
            chiffrat=freigabe.chiffrat,
            iv=freigabe.iv,
            verbleibende_abrufe=verbleibend,
            einmalig=einmalig,
        )
    else:
        notiz = freigabe.notiz
        if notiz is None:
            raise HTTPException(status.HTTP_410_GONE, _ZUSTAND_MELDUNG["quelle_weg"])
        anhaenge = (
            [
                OeffentlicherAnhang(
                    id=a.id, dateiname=a.dateiname, mime=a.mime, groesse=a.groesse
                )
                for a in notiz.anhaenge
            ]
            if freigabe.mit_anhaengen
            else []
        )
        ergebnis = OeffentlicherInhalt(
            modus="offen",
            titel=notiz.titel,
            inhalt=notiz.inhalt,
            anhaenge=anhaenge,
            verbleibende_abrufe=verbleibend,
            einmalig=einmalig,
            anhang_schein=ausstellen(freigabe.id) if anhaenge else None,
        )

    # --- War das der letzte Abruf? Dann den Inhalt wirklich hergeben --------
    if freigabe.verbraucht and freigabe.chiffrat is not None:
        freigabe.chiffrat = None
        db.commit()

    # Diese Antwort darf nirgends liegenbleiben: nicht im Browser-Cache, nicht
    # in einem Zwischenspeicher am Weg. Bei einer Einmal-Notiz wuerde ein
    # gecachter Text die Loeschung auf dem Server wertlos machen.
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    return ergebnis


@router.get("/{merkmal}/anhang/{anhang_id}")
def anhang(
    merkmal: str,
    anhang_id: int,
    request: Request,
    schein: str = Query(default="", description="Zugriffsschein aus dem Oeffnen-Schritt"),
    db: Session = Depends(get_db),
) -> Response:
    """Anhang einer geoeffneten Freigabe.

    Der Schein aus dem Oeffnen-Schritt ist Pflicht. Ohne ihn waere der Anhang
    ueber denselben Link erreichbar wie der Text, nur ohne Zaehler, ohne
    Passwort und ohne Ablauf, weil ein ``GET`` auf eine Datei nichts davon
    kennt. Der Anhang waere damit die Hintertuer zur eigenen Freigabe.
    """
    _bremsen(request, _GRENZE_ANHANG, "anhang")
    freigabe = _freigabe_laden(db, merkmal)
    if not freigabe.mit_anhaengen or freigabe.widerrufen_am is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anhang nicht gefunden")
    if not gueltig(schein, freigabe.id):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Zugriffsschein fehlt oder ist abgelaufen: Notiz erneut oeffnen.",
        )
    datei = db.scalar(
        select(Anhang).where(Anhang.id == anhang_id, Anhang.notiz_id == freigabe.notiz_id)
    )
    if datei is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anhang nicht gefunden")
    return datei_antwort(datei)
