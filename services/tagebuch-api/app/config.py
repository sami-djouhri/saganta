import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/tagebuch.db"

    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth). Die Daten sind mandantenstreng, jede Zeile
    # traegt owner_sub. Die Allowlist ist deshalb eine zusaetzliche Tuer, keine
    # tragende Wand. Leer = offen.
    allowed_subs: Annotated[list[str], NoDecode] = []

    cors_origins: Annotated[list[str], NoDecode] = [
        "https://tagebuch.home.arpa",
        "https://tagebuch.saganta.de",
    ]

    # --- Eintraege ------------------------------------------------------
    # Groesse des Chiffrats je Tag (Base64). Der Dienst kann den Inhalt nicht
    # pruefen, also begrenzt er wenigstens die Menge. 1 MiB Base64 sind rund
    # 750 kB Klartext, also etwa 100.000 Woerter an einem einzigen Tag.
    eintrag_max_chiffrat_bytes: int = 1024 * 1024
    # Groesse der verpackten Schluessel im Tresor. Ein DEK ist 32 Byte, verpackt
    # plus Base64 rund 90 Zeichen. Der Deckel faengt nur Unsinn ab.
    tresor_max_feld_bytes: int = 4096

    @field_validator("cors_origins", "allowed_subs", mode="before")
    @classmethod
    def _split_liste(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()

# Fail-Fast gegen unsichere Default-Secrets, gleiche Linie wie notizen-api: ein
# Dienst mit "change-me"-JWT-Secret kann gefaelschte Tokens nicht von echten
# unterscheiden. Fuer lokale Entwicklung: ALLOW_INSECURE_SECRETS=1.
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
