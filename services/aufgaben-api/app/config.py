import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/aufgaben.db"
    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth). Die Daten sind mandantenstreng, jede Zeile
    # traegt owner_sub. Leer = offen.
    allowed_subs: Annotated[list[str], NoDecode] = []
    cors_origins: Annotated[list[str], NoDecode] = ["https://aufgaben.home.arpa"]

    # Der Kalender kennt die freie Zeit, die Kapazitaet und die Tagesziele.
    # Dieser Dienst spricht ihn im Namen des Aufrufers an, mit einem eigenen
    # kurzlebigen Token fuer `kalender-bff`, gestempelt mit demselben
    # Schluessel, mit dem die BFFs ihre Token stempeln (`jwt_secret`).
    kalender_bff_url: str = "http://saganta-kalender-bff:8000"

    @field_validator("cors_origins", "allowed_subs", mode="before")
    @classmethod
    def _split_liste(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()

# Fail-Fast gegen unsichere Default-Secrets, gleiche Linie wie die Schwestern.
_UNSICHERE_SECRETS = {
    "change-me-shared-with-auth-proxy",
    "change-me",
    "change-me-in-production",
}
if settings.jwt_secret in _UNSICHERE_SECRETS and os.environ.get("ALLOW_INSECURE_SECRETS") != "1":
    raise RuntimeError(
        "FATAL: jwt_secret ist ein unsicherer Default-Wert. Echtes Secret via "
        ".env (JWT_SECRET=...) setzen oder ALLOW_INSECURE_SECRETS=1 fuer lokale Dev."
    )
