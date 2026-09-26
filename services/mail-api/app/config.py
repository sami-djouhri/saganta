import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# Provider-Presets: füllen IMAP/SMTP-Host+Port automatisch, wenn der Nutzer nur seine
# E-Mail + App-Passwort angibt. Erweiterbar; unbekannte Provider => manuelle Eingabe.
PROVIDER_PRESETS: dict[str, dict[str, object]] = {
    "gmail": {
        "imap_host": "imap.gmail.com", "imap_port": 993,
        "smtp_host": "smtp.gmail.com", "smtp_port": 465,
        "note": "App-Passwort nötig (2FA) oder OAuth2 (später).",
    },
    "gmx": {
        "imap_host": "imap.gmx.net", "imap_port": 993,
        "smtp_host": "mail.gmx.net", "smtp_port": 465,
        "note": "IMAP/SMTP in den GMX-Einstellungen aktivieren.",
    },
    "web.de": {
        "imap_host": "imap.web.de", "imap_port": 993,
        "smtp_host": "smtp.web.de", "smtp_port": 587,
        "note": "IMAP/SMTP in den web.de-Einstellungen aktivieren.",
    },
    "outlook": {
        "imap_host": "outlook.office365.com", "imap_port": 993,
        "smtp_host": "smtp.office365.com", "smtp_port": 587,
        "note": "App-Passwort/OAuth2 nötig.",
    },
    "icloud": {
        "imap_host": "imap.mail.me.com", "imap_port": 993,
        "smtp_host": "smtp.mail.me.com", "smtp_port": 587,
        "note": "App-spezifisches Passwort nötig.",
    },
    "djouhri": {
        "imap_host": "mail.djouhri.de", "imap_port": 993,
        "smtp_host": "mail.djouhri.de", "smtp_port": 465,
        "note": "Eigenes Mailcow-Postfach.",
    },
    "saganta": {
        "imap_host": "mail.saganta.de", "imap_port": 993,
        "smtp_host": "mail.saganta.de", "smtp_port": 465,
        "note": "saganta.de-Postfach (z. B. kontakt@) auf dem eigenen Mailcow.",
    },
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/mail.db"

    # IMAP-Sync-Poller
    sync_interval_seconds: int = 300
    imap_fetch_timeout: float = 20.0
    sync_max_messages: int = 200
    default_page_size: int = 50
    max_page_size: int = 200

    # Verschlüsselung der Account-Passwörter at-rest (Fernet, urlsafe-base64, 32 Byte)
    fernet_key: str = "change-me-generate-a-real-fernet-key"

    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth): nur diese better-auth-subs dürfen zugreifen.
    # Single-User-Suite → fremde Accounts gehören nicht auf private Daten.
    # Leer = offen (Rückwärtskompatibilität).
    allowed_subs: Annotated[list[str], NoDecode] = []

    # ★★ `post.`, nicht `postfach.` (2026-09-12). Hier stand die Adresse von
    # `apps/mail`, und das ist das brachliegende Frontend: es hat keinen
    # Compose-Dienst und keinen Vhost. Die Oberflaeche, die dieses Backend
    # wirklich benutzt, ist `apps/post` unter `post.<domaene>`. Aufgefallen ist
    # es nie, weil sie serverseitig anfragt und CORS dabei keine Rolle spielt.
    # Der erste Aufruf aus dem Browser waere daran gescheitert, und zwar mit
    # einer Meldung, die nach einem Fehler der Oberflaeche aussieht.
    cors_origins: Annotated[list[str], NoDecode] = [
        "https://shell.home.arpa",
        "https://post.home.arpa",
    ]

    # ── OAuth2 fuer Mailkonten ──────────────────────────────────────────────
    #
    # ★ Alle drei Werte sind **leer** vorbelegt, und das ist die Sicherung: ohne
    # sie gilt der jeweilige Anbieter als nicht verfuegbar, und die Oberflaeche
    # bietet ihn gar nicht erst an. Eine Vorbelegung mit einer fremden
    # Client-Kennung waere ein Knopf, der in einen Anbieter-Fehler laeuft und
    # dabei nach einem Ausfall dieser Anwendung aussieht.
    #
    # ⚠️ Die Registrierung ist ein Owner-Schritt und laesst sich hier nicht
    # ersetzen: Google-Cloud-Projekt bzw. Azure-App-Registrierung, Zustimmungs-
    # Bildschirm, und bei Google zusaetzlich eine Ueberpruefung fuer den
    # Gmail-Scope. Details in services/mail-api/OAUTH.md.
    oauth_redirect_url: str = ""
    oauth_google_client_id: str = ""
    oauth_google_client_secret: str = ""
    oauth_microsoft_client_id: str = ""
    oauth_microsoft_client_secret: str = ""
    #: Wie lange ein angefangener Verbindungsvorgang gueltig bleibt.
    oauth_state_ttl_seconds: int = 900

    @field_validator("cors_origins", "allowed_subs", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()

# Fail-Fast gegen unsichere Default-Secrets: ein Service mit "change-me"-JWT-Secret
# kann fremde Tokens nicht von echten unterscheiden → Boot abbrechen statt still
# unsicher laufen. Für lokale Entwicklung: ALLOW_INSECURE_SECRETS=1. (2026-06-28)
_INSECURE_SECRETS = {
    "change-me-shared-with-auth-proxy",
    "change-me",
    "change-me-in-production",
    "change-me-generate-a-real-fernet-key",
}
_allow_insecure = os.environ.get("ALLOW_INSECURE_SECRETS") == "1"
if settings.jwt_secret in _INSECURE_SECRETS and not _allow_insecure:
    raise RuntimeError(
        "FATAL: jwt_secret ist ein unsicherer Default-Wert. Echtes Secret via "
        ".env (JWT_SECRET=...) setzen oder ALLOW_INSECURE_SECRETS=1 für lokale Dev."
    )
# fernet_key verschlüsselt die IMAP/SMTP-Passwörter at-rest: mit dem Default-Wert
# lägen sie effektiv im Klartext (öffentlich bekannter Schlüssel). (2026-07-17)
if settings.fernet_key in _INSECURE_SECRETS and not _allow_insecure:
    raise RuntimeError(
        "FATAL: fernet_key ist ein unsicherer Default-Wert. Echtes Fernet-Secret via "
        ".env (FERNET_KEY=..., Fernet.generate_key()) setzen oder ALLOW_INSECURE_SECRETS=1."
    )
