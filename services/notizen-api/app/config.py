import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/notizen.db"

    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth). Anders als bei projectdeck-api sind die
    # Daten hier mandantenstreng (jede Zeile traegt owner_sub), die Allowlist
    # ist deshalb eine zusaetzliche Tuer, keine tragende Wand. Leer = offen.
    allowed_subs: Annotated[list[str], NoDecode] = []

    cors_origins: Annotated[list[str], NoDecode] = [
        "https://notizen.home.arpa",
        "https://notizen.saganta.de",
    ]

    # --- Anhaenge -------------------------------------------------------
    anhang_verzeichnis: str = "/data/anhaenge"
    # Je Datei. 20 MiB deckt Fotos und uebliche PDF-Scans ab.
    anhang_max_bytes: int = 20 * 1024 * 1024
    # Gesamtvorrat je Nutzer. Verhindert, dass ein Konto die Platte fuellt.
    anhang_quote_bytes: int = 500 * 1024 * 1024

    # --- Freigaben ------------------------------------------------------
    # Obergrenze fuer die Lebensdauer eines Links. Ohne Deckel lebt ein
    # versehentlich geteilter Link ewig weiter.
    freigabe_max_tage: int = 365
    # Groesse des Chiffrats einer verschluesselten Freigabe (Base64). Der Server
    # kann den Inhalt nicht pruefen, also begrenzen wir wenigstens die Menge.
    freigabe_max_chiffrat_bytes: int = 4 * 1024 * 1024
    # Fehlversuche je Freigabe, bevor sie sich selbst sperrt. Schuetzt ein
    # schwaches Freigabe-Passwort gegen Durchprobieren.
    freigabe_max_fehlversuche: int = 10

    @field_validator("cors_origins", "allowed_subs", mode="before")
    @classmethod
    def _split_liste(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v


settings = Settings()

# Fail-Fast gegen unsichere Default-Secrets: gleiche Linie wie projectdeck-api:
# ein Dienst mit "change-me"-JWT-Secret kann gefaelschte Tokens nicht von echten
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
