import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/projectdeck.db"

    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth): nur diese better-auth-subs dürfen zugreifen.
    # Single-User-Suite → fremde Accounts gehören nicht auf private Daten.
    # Leer = offen (Rückwärtskompatibilität).
    allowed_subs: Annotated[list[str], NoDecode] = []

    cors_origins: Annotated[list[str], NoDecode] = [
        "https://shell.home.arpa",
        "https://projectdeck.home.arpa",
    ]

    # Native Kalender (cc-apps). LAN-Fallback: http://<wirt>:8085
    kalender_base_url: str = "http://kalender:8085"
    kalender_feed_token: str = "change-me"
    kalender_timeout_seconds: float = 8.0

    # Echtheitsnachweis für X-Saganta-Sub (app/tenant_sig.py). Leer = wie bisher,
    # nur der unsignierte Header. Muss identisch zu KALENDER_TENANT_SECRET im
    # nativen Kalender sein.
    kalender_tenant_secret: str = ""

    # Optionaler KI-Layer, aus per Vorgabe. Erwartet ein OpenAI-kompatibles
    # /v1/chat/completions (llama.cpp, vLLM, Ollama und dergleichen).
    #
    # ★ Ohne Adresse vorbelegt, seit 2026-09-12. Hier stand die LAN-Adresse des
    # Rechners, auf dem dieses Projekt entstanden ist. Das ist ein
    # instanz-spezifischer Wert im Quelltext: in jeder anderen Installation
    # zeigt er auf einen fremden Rechner, und die Veroeffentlichung schreibt ihn
    # ohnehin auf eine Dokumentations-Adresse um, hinter der nie etwas steht.
    # Wer den Layer einschaltet, traegt seine eigene Adresse ein.
    llm_enabled: bool = False
    llm_base_url: str = ""
    llm_model: str = "gemma-3-4b"
    llm_timeout_seconds: float = 30.0

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
