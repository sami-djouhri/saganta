"""Ein Zugang zu einem Mailkonto, unabhaengig davon, wie es sich anmeldet.

★ **Der Punkt dieser Datei ist, dass sync und smtp den Unterschied nicht kennen
muessen.** Beide fragen hier nach „womit melde ich mich an", und bekommen
entweder ein Passwort oder ein frisches Zugriffstoken. Ohne diese Trennung
stuende die Auffrisch-Logik zweimal im Code, und beim naechsten Anbieter waere
eine der beiden Kopien vergessen worden.

★★ Die Auffrischung schreibt in die Datenbank und braucht deshalb eine eigene
Sitzung: der Aufrufer im Hintergrund-Abgleich hat seine laengst geschlossen.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import structlog

from . import oauth
from .crypto import decrypt, encrypt
from .db import SessionLocal
from .models import MailAccount

log = structlog.get_logger()


class ZugangFehler(RuntimeError):
    """Der Zugang laesst sich nicht herstellen, mit einem Grund fuer die Oberflaeche."""


@dataclass(frozen=True)
class Anmeldung:
    """Womit man sich anmeldet."""

    benutzer: str
    #: Passwort ODER Zugriffstoken, je nach `oauth`.
    geheimnis: str
    oauth: bool


def _abgelaufen(zeitpunkt: datetime | None) -> bool:
    """Ist der Token abgelaufen oder laeuft er gleich ab?

    ⚠️ Ein aus SQLite gelesener Zeitstempel kommt je nach Treiber **ohne**
    Zeitzone zurueck. Ein Vergleich mit einem zonenbehafteten `now()` wirft dann
    `can't compare offset-naive and offset-aware datetimes`, und zwar erst zur
    Laufzeit beim ersten Abgleich. Deshalb wird ein nackter Wert hier als UTC
    gelesen: so hat ihn diese Anwendung geschrieben.
    """
    if zeitpunkt is None:
        return True
    if zeitpunkt.tzinfo is None:
        zeitpunkt = zeitpunkt.replace(tzinfo=timezone.utc)
    return zeitpunkt <= datetime.now(timezone.utc)


def anmeldung_fuer(konto_id: int) -> Anmeldung:
    """Die Anmeldedaten eines Kontos, bei OAuth2 mit frischem Token.

    Laeuft in einer eigenen Sitzung, weil sie beim Auffrischen schreibt.
    """
    db = SessionLocal()
    try:
        konto = db.get(MailAccount, konto_id)
        if konto is None:
            raise ZugangFehler("Konto nicht gefunden")

        if konto.auth_typ != "oauth2":
            return Anmeldung(
                benutzer=konto.imap_username,
                geheimnis=decrypt(konto.secret_cipher),
                oauth=False,
            )

        anbieter = oauth.anbieter_holen(konto.oauth_anbieter or "")
        if anbieter is None:
            # Der Anbieter ist nicht (mehr) konfiguriert. Fail-closed mit klarem
            # Grund: ein Anmeldeversuch ohne Zugangsdaten ergaebe beim Anbieter
            # eine nichtssagende Ablehnung.
            raise ZugangFehler(
                f"Für {konto.oauth_anbieter or 'diesen Anbieter'} ist keine "
                "OAuth2-Konfiguration hinterlegt."
            )

        if not _abgelaufen(konto.oauth_laeuft_ab) and konto.oauth_zugriff_cipher:
            return Anmeldung(
                benutzer=konto.imap_username,
                geheimnis=decrypt(konto.oauth_zugriff_cipher),
                oauth=True,
            )

        # Auffrischen. Der Auffrischungstoken liegt im selben Feld wie sonst das
        # Passwort: es ist dasselbe, naemlich das eine dauerhafte Geheimnis.
        satz = oauth.auffrischen(anbieter, decrypt(konto.secret_cipher))
        konto.oauth_zugriff_cipher = encrypt(satz.zugriff)
        konto.oauth_laeuft_ab = satz.laeuft_ab
        # ★ Nur ersetzen, wenn der Anbieter wirklich einen neuen geschickt hat.
        # Manche tun das nicht; wer dann `None` speichert, loescht den einzigen
        # Dauerzugang, und das Konto ist beim naechsten Ablauf tot.
        if satz.auffrischung:
            konto.secret_cipher = encrypt(satz.auffrischung)
        db.commit()
        log.info("mail.oauth.aufgefrischt", konto=konto_id, anbieter=anbieter.schluessel)
        return Anmeldung(benutzer=konto.imap_username, geheimnis=satz.zugriff, oauth=True)
    finally:
        db.close()
