import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/shell.db"
    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth): nur diese better-auth-subs dürfen zugreifen.
    # Single-User-Suite → fremde Accounts gehören nicht auf private Daten.
    # Leer = offen (Rückwärtskompatibilität).
    allowed_subs: Annotated[list[str], NoDecode] = []
    # better-auth-Service für das nginx-auth_request-Gate (Cookie-Session-Validierung).
    auth_service_url: str = "http://saganta-auth:3000"

    # Mandanten-Geheimnisse der nativen Dienste hinter dem Gate.
    #
    # Das Gate beantwortete bis 2026-09-27 nur, OB jemand angemeldet ist. Dahinter
    # meldete ein statischer Auto-Login-Token jeden Aufrufer als Owner an: jeder
    # angemeldete Saganta-Nutzer landete im Kalender und im Postfach des Owners.
    # Damit das Gate stattdessen sagen kann, WER da ist, signiert es den Mandanten
    # mit dem Geheimnis des jeweiligen Zieldienstes.
    #
    # WELCHES Ziel gemeint ist, sagt nginx im Subrequest (`X-Saganta-Ziel`), es
    # wird NICHT aus dem Hostnamen geraten. Ein Selbsthoster mit eigenen Namen
    # braucht deshalb keine Codeänderung, und die Zuordnung steht dort, wo auch
    # `proxy_pass` steht: an einer Stelle, statt an zwei, die auseinanderlaufen
    # können.
    kalender_tenant_secret: str = ""
    postfach_tenant_secret: str = ""

    # Ziele, deren Dienst seine Mandantentrennung BELEGT hat. Nur dort darf ein
    # zweites Konto hinter das Gate. Alles andere sieht nur der Owner.
    #
    # Ohne diese Liste war das Gate der eine Weg, der die Mandantentrennung
    # umgeht. Gemessen am 2026-09-27: `ALLOWED_SUBS` ist für diesen Dienst **nicht
    # gesetzt**, also offen, und in der Anmelde-Datenbank liegen neben dem Owner
    # **zwei** weitere Konten. Beide hätten über `mail.saganta.*` das Postfach des
    # Owners geöffnet, mit HTTP 200 und ohne Spur, weil das Gate nur beantwortete,
    # ob jemand angemeldet ist. Die Allowlists der Dienste selbst greifen dort
    # nicht: hinter dem Gate meldet ein statischer Auto-Login-Token an.
    #
    # Die Liste nennt bewusst die ERLAUBTEN, nicht die gesperrten. Eine
    # Sperrliste hängt daran, dass nginx das Ziel nennt: wer beim Anschließen eines
    # neuen Vhosts `X-Saganta-Ziel` vergisst, bekäme ein unbekanntes Ziel und damit
    # freien Durchgang. So herum ist Vergessen der sichere Fall.
    #
    # Ein Eintrag kommt hier dazu, wenn der Dienst dahinter seine Trennung belegen
    # kann: `kalender` seit dem 2026-09-27 (`tests/test_gate_anmeldung.py` und
    # `tests/test_feed_token_mandant.py` im Kalender-Repo).
    ziele_mit_mandanten: Annotated[list[str], NoDecode] = ["kalender"]
    # Wer der Owner ist. Leer = die Bremse wirkt nicht, und dann sagt das auch der
    # Startlauf: ein stiller Rückfall auf "offen für alle" wäre genau der Fehler,
    # den die Liste verhindern soll.
    owner_sub: str = ""
    # Override per env CORS_ORIGINS="https://a,https://b", sonst Default greift.
    cors_origins: Annotated[list[str], NoDecode] = [
        "https://shell.home.arpa",
    ]

    @field_validator("cors_origins", "allowed_subs", "ziele_mit_mandanten", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    def tenant_geheimnis(self, ziel: str) -> str:
        """Geheimnis des Zieldienstes, oder leer wenn er keines hat.

        Leer heisst hier nicht "kaputt", sondern "dieser Dienst kennt keine
        Mandanten". `nachrichten` ist genau so ein Fall: die Artikel sind fuer alle
        gleich, gewichtet werden die Themen in der Saganta-App, nicht in der Engine.
        Das Gate schickt dorthin deshalb bewusst keinen Mandanten.
        """
        return {
            "kalender": self.kalender_tenant_secret,
            "postfach": self.postfach_tenant_secret,
        }.get(ziel, "")


settings = Settings()

# Fail-Fast gegen unsichere Default-Secrets: ein Service mit "change-me"-JWT-Secret
# kann fremde Tokens nicht von echten unterscheiden → Boot abbrechen statt still
# unsicher laufen. Für lokale Entwicklung: ALLOW_INSECURE_SECRETS=1. (2026-06-28)
_INSECURE_SECRETS = {
    "change-me-shared-with-auth-proxy",
    "change-me",
    "change-me-in-production",
}
if (
    settings.jwt_secret in _INSECURE_SECRETS
    and os.environ.get("ALLOW_INSECURE_SECRETS") != "1"
):
    raise RuntimeError(
        "FATAL: jwt_secret ist ein unsicherer Default-Wert. Echtes Secret via "
        ".env (JWT_SECRET=...) setzen oder ALLOW_INSECURE_SECRETS=1 für lokale Dev."
    )
