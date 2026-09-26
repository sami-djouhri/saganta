"""Der Verbinden-Fluss fuer OAuth2-Mailkonten.

Drei Schritte, und der mittlere liegt beim Anbieter:

1. ``GET /oauth/anbieter``  welche Wege es hier ueberhaupt gibt
2. ``POST /oauth/start``    liefert die Adresse, auf die der Nutzer geschickt wird
3. ``POST /oauth/abschluss`` loest den zurueckgereichten Code ein und legt das Konto an

★★ **Der `state` wird hier serverseitig gefuehrt, nicht im Browser.** Er ist
nicht nur ein Wiedererkennungsmerkmal, sondern der einzige Riegel gegen eine
untergeschobene Rueckleitung: ohne ihn koennte jemand einen Nutzer auf den
Abschluss mit **seinem** Code schicken, und danach haenge ein fremdes Postfach
am Konto des Opfers. Deshalb merkt sich dieser Dienst zu jedem `state`, **wer**
ihn angefangen hat, und der Abschluss prueft das gegen den angemeldeten Nutzer.

★ Der Vorrat ist absichtlich fluechtig (im Speicher, mit Ablauf). Ein
angefangener Verbindungsvorgang ist nichts, was einen Neustart ueberleben muss;
eine Tabelle dafuer waere ein Ort mehr, an dem halbfertige Zustaende liegen
bleiben. Faellt der Dienst mittendrin neu an, beginnt man ihn eben neu.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from . import oauth
from .auth import CurrentUser, Me
from .config import settings
from .crypto import encrypt
from .db import get_db
from .models import MailAccount
from .schemas import AccountOut
from .sync import sync_account, test_oauth_verbindung

log = structlog.get_logger()
router = APIRouter()


@dataclass
class AngefangenerVorgang:
    sub: str
    anbieter: str
    laeuft_ab: datetime


_VORGAENGE: dict[str, AngefangenerVorgang] = {}


def _aufraeumen() -> None:
    jetzt = datetime.now(timezone.utc)
    for schluessel in [k for k, v in _VORGAENGE.items() if v.laeuft_ab <= jetzt]:
        _VORGAENGE.pop(schluessel, None)


class AnbieterAus(BaseModel):
    schluessel: str
    name: str


class StartAn(BaseModel):
    anbieter: str
    #: Optionale Vorbelegung des Konto-Feldes beim Anbieter.
    email: str = ""


class StartAus(BaseModel):
    url: str
    zustand: str


class AbschlussAn(BaseModel):
    zustand: str
    code: str


@router.get("/oauth/anbieter", response_model=list[AnbieterAus])
def anbieter_liste(me: Me = CurrentUser) -> list[AnbieterAus]:
    """Nur die Anbieter, fuer die wirklich eine Konfiguration hinterlegt ist.

    ★ Fail-closed: ein Eintrag ohne Client-Kennung waere ein Knopf, der beim
    Anbieter in einen Fehler laeuft und dabei nach einem Ausfall dieser Anwendung
    aussieht. Lieber gar nicht anbieten.
    """
    return [AnbieterAus(schluessel=a.schluessel, name=a.name) for a in oauth.verfuegbare_anbieter()]


@router.post("/oauth/start", response_model=StartAus)
def start(payload: StartAn, me: Me = CurrentUser) -> StartAus:
    anbieter = oauth.anbieter_holen(payload.anbieter)
    if anbieter is None:
        raise HTTPException(400, f"Für '{payload.anbieter}' ist kein OAuth2-Zugang hinterlegt.")
    _aufraeumen()
    zustand = oauth.zustand_erzeugen()
    _VORGAENGE[zustand] = AngefangenerVorgang(
        sub=me.sub,
        anbieter=anbieter.schluessel,
        laeuft_ab=datetime.now(timezone.utc)
        + timedelta(seconds=settings.oauth_state_ttl_seconds),
    )
    return StartAus(
        url=oauth.autorisierung_url(anbieter, zustand, payload.email),
        zustand=zustand,
    )


@router.post("/oauth/abschluss", response_model=AccountOut)
async def abschluss(
    payload: AbschlussAn, me: Me = CurrentUser, db: Session = Depends(get_db)
) -> AccountOut:
    _aufraeumen()
    vorgang = _VORGAENGE.get(payload.zustand)
    if vorgang is None:
        raise HTTPException(400, "Der Verbindungsvorgang ist abgelaufen. Bitte neu starten.")
    # ★ Der eigentliche Riegel: der Abschluss gehoert dem, der angefangen hat.
    # Ohne diese Pruefung koennte ein untergeschobener Code ein fremdes Postfach
    # an das eigene Konto haengen.
    if vorgang.sub != me.sub:
        log.warning("mail.oauth.fremder_abschluss", erwartet=vorgang.sub[:8], gesehen=me.sub[:8])
        raise HTTPException(400, "Dieser Verbindungsvorgang gehört zu einem anderen Konto.")
    # Der `state` ist ein Einmalwert: ohne Verbrauch liesse sich derselbe Code
    # mehrfach einloesen.
    _VORGAENGE.pop(payload.zustand, None)

    anbieter = oauth.anbieter_holen(vorgang.anbieter)
    if anbieter is None:
        raise HTTPException(400, "Der Anbieter ist nicht mehr konfiguriert.")

    try:
        satz = await asyncio.to_thread(oauth.code_einloesen, anbieter, payload.code)
    except oauth.OAuthFehler as exc:
        raise HTTPException(400, str(exc)) from exc

    adresse = (satz.email or "").strip()
    if not adresse:
        # ⚠️ Ohne Adresse laesst sich das Konto nicht anlegen: sie ist zugleich
        # der IMAP-Benutzername. Lieber hier abbrechen als ein Konto mit leerem
        # Benutzer speichern, das bei jedem Abruf scheitert.
        raise HTTPException(
            400,
            f"{anbieter.name} hat keine E-Mail-Adresse mitgeliefert. "
            "Bitte das Konto mit App-Passwort verbinden.",
        )

    vorhanden = (
        db.query(MailAccount)
        .filter(MailAccount.sub == me.sub, MailAccount.email == adresse)
        .one_or_none()
    )
    if vorhanden:
        raise HTTPException(409, "Dieses Konto ist bereits verbunden.")

    # Verbindungstest VOR dem Speichern, wie beim Passwort-Weg. Hier faellt
    # ausserdem ein zu schmaler Scope auf: der Zugang wird erteilt, IMAP lehnt
    # ihn trotzdem ab, und ohne diesen Test stuende das Konto gruen in der Liste
    # und bliebe stumm leer.
    try:
        await asyncio.to_thread(
            test_oauth_verbindung,
            anbieter.imap_host,
            anbieter.imap_port,
            adresse,
            satz.zugriff,
        )
    except Exception as exc:
        raise HTTPException(400, f"IMAP-Zugriff fehlgeschlagen: {str(exc)[:200]}") from exc

    konto = MailAccount(
        sub=me.sub,
        email=adresse,
        provider=anbieter.schluessel,
        display_name=None,
        auth_typ="oauth2",
        oauth_anbieter=anbieter.schluessel,
        # Der Auffrischungstoken liegt im selben Feld wie sonst das Passwort: es
        # ist dasselbe, naemlich das eine dauerhafte Geheimnis.
        secret_cipher=encrypt(satz.auffrischung or ""),
        oauth_zugriff_cipher=encrypt(satz.zugriff),
        oauth_laeuft_ab=satz.laeuft_ab,
        imap_host=anbieter.imap_host,
        imap_port=anbieter.imap_port,
        imap_username=adresse,
        smtp_host=anbieter.smtp_host,
        smtp_port=anbieter.smtp_port,
        smtp_username=adresse,
    )
    db.add(konto)
    db.commit()
    db.refresh(konto)
    konto_id = konto.id
    asyncio.create_task(sync_account(konto_id))
    log.info("mail.oauth.verbunden", konto=konto_id, anbieter=anbieter.schluessel)

    from .routes_mail import _account_out

    return _account_out(konto)
