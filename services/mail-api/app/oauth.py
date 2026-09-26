"""OAuth2 fuer Mailkonten: Anbieter, Autorisierungsfluss und Token-Auffrischung.

★ **Warum ueberhaupt, wenn es App-Passwoerter gibt.** Ein App-Passwort ist schon
ein eigenes, einzeln widerrufbares Geheimnis mit Zugriff nur auf Mail, und es
liegt hier Fernet-verschluesselt. Es ist also kein schlechter Weg. OAuth2 ist an
drei Stellen trotzdem besser, und alle drei zaehlen im Alltag:

1. **Es liegt gar kein Dauer-Geheimnis mehr hier.** Ein Zugriffstoken laeuft nach
   einer Stunde ab; was bleibt, ist ein Auffrischungstoken, den der Anbieter
   jederzeit entwerten kann, ohne dass der Nutzer sein Passwort aendert.
2. **Widerrufbar von der anderen Seite.** Wer den Zugriff zurueckziehen will,
   klickt ihn im Google- oder Microsoft-Konto weg. Beim App-Passwort muss er
   wissen, welches von mehreren zu dieser Anwendung gehoert.
3. **Es ueberlebt einen Passwortwechsel.** Ein App-Passwort nicht immer, und dann
   steht in der Oberflaeche ein Anmeldefehler, dessen Ursache Wochen zurueckliegt.

★★ **Fail-closed ohne Konfiguration.** Ist fuer einen Anbieter keine
Client-Kennung hinterlegt, gilt er hier als **nicht verfuegbar**, und die
Oberflaeche bietet ihn gar nicht erst an. Ein Knopf, der in einen
Anbieter-Fehler laeuft, ist schlechter als kein Knopf: er sieht aus wie ein
Ausfall der eigenen Anwendung. (Dieselbe Regel wie bei den Adressen ohne Ziel,
2026-09-12.)

⚠️ **Die Registrierung beim Anbieter ist ein Owner-Schritt und kann hier nicht
ersetzt werden.** Google verlangt fuer den Gmail-Scope zusaetzlich eine
Ueberpruefung der Anwendung, die Wochen dauern kann; bis dahin funktioniert der
Fluss nur fuer Testnutzer, die im Google-Cloud-Projekt eingetragen sind.
"""

from __future__ import annotations

import base64
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import httpx
import structlog

from .config import settings

log = structlog.get_logger()


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Anbieter:
    """Ein OAuth2-faehiger Mailanbieter."""

    schluessel: str
    name: str
    autorisierung_url: str
    token_url: str
    scopes: tuple[str, ...]
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    #: Zusaetzliche Parameter der Autorisierungs-Anfrage.
    zusatz: dict[str, str] = field(default_factory=dict)

    @property
    def client_id(self) -> str:
        return getattr(settings, f"oauth_{self.schluessel}_client_id", "") or ""

    @property
    def client_secret(self) -> str:
        return getattr(settings, f"oauth_{self.schluessel}_client_secret", "") or ""

    @property
    def verfuegbar(self) -> bool:
        """Ohne Kennung und Geheimnis gibt es diesen Weg nicht."""
        return bool(self.client_id and self.client_secret and settings.oauth_redirect_url)


ANBIETER: dict[str, Anbieter] = {
    "google": Anbieter(
        schluessel="google",
        name="Google / Gmail",
        autorisierung_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        # `https://mail.google.com/` ist der Scope, den IMAP und SMTP verlangen.
        # Die schmaleren gmail.readonly-Scopes reichen fuer IMAP NICHT aus.
        scopes=("https://mail.google.com/",),
        imap_host="imap.gmail.com",
        imap_port=993,
        smtp_host="smtp.gmail.com",
        smtp_port=465,
        # `offline` ist Pflicht, sonst kommt gar kein Auffrischungstoken, und der
        # Zugang waere nach einer Stunde tot. `consent` erzwingt ihn auch bei
        # einer wiederholten Freigabe: ohne den Schalter liefert Google beim
        # zweiten Mal nur ein Zugriffstoken, und das Konto stirbt still nach
        # einer Stunde.
        zusatz={"access_type": "offline", "prompt": "consent"},
    ),
    "microsoft": Anbieter(
        schluessel="microsoft",
        name="Microsoft / Outlook",
        autorisierung_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        # `offline_access` ist hier der Scope, der den Auffrischungstoken bringt.
        scopes=(
            "https://outlook.office.com/IMAP.AccessAsUser.All",
            "https://outlook.office.com/SMTP.Send",
            "offline_access",
        ),
        imap_host="outlook.office365.com",
        imap_port=993,
        smtp_host="smtp.office365.com",
        # ⚠️ Microsoft kann auf 465 kein implizites TLS; 587 mit STARTTLS ist der
        # einzige Weg. Wer hier 465 eintraegt, bekommt einen Zeitablauf ohne
        # Fehlermeldung.
        smtp_port=587,
    ),
}


def verfuegbare_anbieter() -> list[Anbieter]:
    return [a for a in ANBIETER.values() if a.verfuegbar]


def anbieter_holen(schluessel: str) -> Anbieter | None:
    a = ANBIETER.get(schluessel)
    return a if a and a.verfuegbar else None


class OAuthFehler(RuntimeError):
    """Der Anbieter hat den Fluss abgelehnt."""


def zustand_erzeugen() -> str:
    """Ein unerratbarer `state` gegen untergeschobene Rueckleitungen.

    Ohne ihn koennte jemand den Nutzer auf die Rueckleitung mit **seinem** Code
    schicken, und das fremde Postfach haenge danach am Konto des Opfers.
    """
    return secrets.token_urlsafe(32)


def autorisierung_url(anbieter: Anbieter, zustand: str, login_hinweis: str = "") -> str:
    from urllib.parse import urlencode

    werte = {
        "client_id": anbieter.client_id,
        "redirect_uri": settings.oauth_redirect_url,
        "response_type": "code",
        "scope": " ".join(anbieter.scopes),
        "state": zustand,
        **anbieter.zusatz,
    }
    if login_hinweis:
        werte["login_hint"] = login_hinweis
    return f"{anbieter.autorisierung_url}?{urlencode(werte)}"


@dataclass
class TokenSatz:
    zugriff: str
    auffrischung: str | None
    laeuft_ab: datetime
    #: Vom Anbieter gemeldete Adresse, falls er sie mitschickt.
    email: str | None = None


def _ablauf(sekunden: object) -> datetime:
    """Ablaufzeitpunkt mit Sicherheitsabstand.

    ★ Die 60 Sekunden Abzug sind kein Schmuck: ohne sie gilt ein Token bis zur
    letzten Sekunde als gueltig, und eine Synchronisierung, die genau dann
    beginnt, scheitert mitten im Abruf mit einem Anmeldefehler. Der sieht aus wie
    ein entzogener Zugriff.
    """
    try:
        s = int(sekunden)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        s = 3600
    return _jetzt() + timedelta(seconds=max(60, s - 60))


def code_einloesen(anbieter: Anbieter, code: str) -> TokenSatz:
    daten = {
        "client_id": anbieter.client_id,
        "client_secret": anbieter.client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": settings.oauth_redirect_url,
    }
    with httpx.Client(timeout=20) as c:
        r = c.post(anbieter.token_url, data=daten)
    if r.status_code >= 400:
        log.warning("mail.oauth.code_abgelehnt", anbieter=anbieter.schluessel, status=r.status_code)
        raise OAuthFehler(f"{anbieter.name} hat den Zugang abgelehnt ({r.status_code}).")
    j = r.json()
    auffrischung = j.get("refresh_token")
    if not auffrischung:
        # Ohne Auffrischungstoken waere der Zugang nach einer Stunde tot, und zwar
        # ohne sichtbaren Grund. Lieber hier abbrechen und es sagen.
        raise OAuthFehler(
            f"{anbieter.name} hat keinen Auffrischungs-Token geliefert. "
            "Meist hilft es, den Zugriff im Konto zu entfernen und neu zu erlauben."
        )
    return TokenSatz(
        zugriff=j["access_token"],
        auffrischung=auffrischung,
        laeuft_ab=_ablauf(j.get("expires_in")),
        email=_email_aus_id_token(j.get("id_token")),
    )


def auffrischen(anbieter: Anbieter, auffrischungstoken: str) -> TokenSatz:
    daten = {
        "client_id": anbieter.client_id,
        "client_secret": anbieter.client_secret,
        "refresh_token": auffrischungstoken,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=20) as c:
        r = c.post(anbieter.token_url, data=daten)
    if r.status_code >= 400:
        log.warning(
            "mail.oauth.auffrischung_abgelehnt",
            anbieter=anbieter.schluessel,
            status=r.status_code,
        )
        raise OAuthFehler(
            f"{anbieter.name} hat die Auffrischung abgelehnt ({r.status_code}). "
            "Vermutlich wurde der Zugriff im Konto entzogen; bitte neu verbinden."
        )
    j = r.json()
    return TokenSatz(
        zugriff=j["access_token"],
        # ★ Manche Anbieter schicken bei der Auffrischung KEINEN neuen
        # Auffrischungstoken. Dann gilt der alte weiter; wer hier `None`
        # speichert, loescht den einzigen Dauerzugang und das Konto ist beim
        # naechsten Ablauf tot.
        auffrischung=j.get("refresh_token"),
        laeuft_ab=_ablauf(j.get("expires_in")),
    )


def _email_aus_id_token(id_token: object) -> str | None:
    """Adresse aus dem `id_token`, ohne Signaturpruefung.

    ⚠️ Bewusst **ungeprueft** und deshalb nur als **Vorbelegung** eines
    Eingabefeldes verwendbar, nie als Berechtigung. Der Wert kommt hier zwar
    direkt vom Anbieter ueber eine TLS-Verbindung, aber diese Funktion prueft das
    nicht nach, und eine Kennung, die man nicht geprueft hat, darf ueber nichts
    entscheiden.
    """
    if not isinstance(id_token, str) or id_token.count(".") != 2:
        return None
    try:
        rumpf = id_token.split(".")[1]
        rumpf += "=" * (-len(rumpf) % 4)
        import json

        daten = json.loads(base64.urlsafe_b64decode(rumpf))
        wert = daten.get("email")
        return wert if isinstance(wert, str) else None
    except Exception:
        return None


# ★ Hier stand eine selbst gebaute SASL-XOAUTH2-Zeichenkette. Sie ist wieder
# entfernt, bevor sie je benutzt wurde: `imap_tools.MailBox.xoauth2()` und
# `aiosmtplib.SMTP.auth_xoauth2()` bauen und kodieren sie beide selbst, und
# aiosmtplib behandelt zusaetzlich den Fehlerfall richtig (der Server antwortet
# bei einem abgelehnten Token mit einer Zwischenmeldung samt Grund und erwartet
# darauf eine Leerzeile). Ein Nachbau haette genau diese Auskunft verschluckt.
