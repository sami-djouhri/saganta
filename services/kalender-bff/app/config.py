import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Upstream nativer kalender-Container (cc-core). LAN-Fallback: host:8085.
    kalender_base_url: str = "http://kalender:8085"
    kalender_feed_token: str = "change-me"
    kalender_timeout_seconds: float = 5.0

    # Echtheitsnachweis für X-Saganta-Sub (siehe app/tenant_sig.py und
    # backend/tenant_auth.py im nativen Kalender). Leer = wie bisher, nur der
    # unsignierte Header. Muss identisch zu KALENDER_TENANT_SECRET dort sein.
    kalender_tenant_secret: str = ""

    # Der better-auth-sub des Kalender-Eigentümers (= DEFAULT_OWNER_SUB im nativen
    # Dienst). Braucht GET /api/feed-token: der Feed-Token liegt in der bewusst
    # NICHT mandantengetrennten Setting-Tabelle, ist also für alle derselbe, und
    # wer ihn hat, ist Owner. Leer = die Route antwortet 503 statt zu raten
    # (fail-closed). Siehe app/routes_mobile.py.
    kalender_owner_sub: str = ""

    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth): nur diese better-auth-subs dürfen zugreifen.
    # Der Kalender ist nicht user-isoliert → ohne Gate sähe jeder eingeloggte
    # Account die privaten Termine. Leer = offen (Rückwärtskompatibilität).
    allowed_subs: Annotated[list[str], NoDecode] = []

    cors_origins: Annotated[list[str], NoDecode] = [
        "https://shell.home.arpa",
        "https://calendar.home.arpa",
    ]

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
}
if (
    settings.jwt_secret in _INSECURE_SECRETS
    and os.environ.get("ALLOW_INSECURE_SECRETS") != "1"
):
    raise RuntimeError(
        "FATAL: jwt_secret ist ein unsicherer Default-Wert. Echtes Secret via "
        ".env (JWT_SECRET=...) setzen oder ALLOW_INSECURE_SECRETS=1 für lokale Dev."
    )
