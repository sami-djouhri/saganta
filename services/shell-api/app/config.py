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
    # Override per env CORS_ORIGINS="https://a,https://b", sonst Default greift.
    cors_origins: Annotated[list[str], NoDecode] = [
        "https://shell.home.arpa",
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
