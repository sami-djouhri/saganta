import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Derselbe Schluessel, mit dem die BFFs und der Anmeldedienst ihre
    # Backend-Token stempeln. Mit ihm prueft dieser Dienst eingehende Token
    # (aud=assistent-api) und stempelt die kurzen Token fuer die Apps, in
    # deren Namen er liest (etwa aud=mealprep-api).
    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth). Leer = offen.
    allowed_subs: Annotated[list[str], NoDecode] = []

    # Nur Modelle im Haus (Entscheid 02.11.). Das gruendliche zuerst:
    # homelab-fast traf in der Messung vom 02.11. 1 von 8.
    llm_gateway_url: str = ""
    llm_gateway_key: str = ""
    llm_model: str = "homelab-fast"
    assistent_timeout_seconds: float = 90.0

    # Die Apps, in deren Namen der Assistent liest. Ueber cc-apps erreichbar.
    mealprep_url: str = "http://mealprep:8000"

    @field_validator("allowed_subs", mode="before")
    @classmethod
    def _split_liste(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()

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
