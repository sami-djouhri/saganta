import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/assets.db"

    lager_base_url: str = "http://lager:8095"
    lager_timeout_seconds: float = 5.0

    # ★★ Leer vorbelegt, seit 2026-09-12. Hier stand `http://marktwatch:8120`,
    # ein Dienst, den dieses Repo nicht mitliefert und den es auch im Haus, in
    # dem es entstanden ist, unter diesem Namen nicht gibt (marktwatch laeuft
    # auf einem anderen Wirt). Die Namensaufloesung scheiterte, und der
    # Marktwert-Knopf antwortete mit 502 "marktwatch unreachable": das liest
    # sich wie ein gestoerter Dienst und war eine falsche Adresse. Leer heisst
    # jetzt "keine Marktdaten-Quelle", und der Endpunkt sagt das auch.
    marktwatch_base_url: str = ""
    marktwatch_timeout_seconds: float = 8.0
    # Wert > Threshold + usage_status != critical => Verkaufsempfehlung
    resale_threshold_eur: float = 50.0
    # Cache-TTL für Live-Marktwerte
    market_cache_ttl_minutes: int = 720

    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth): nur diese better-auth-subs dürfen zugreifen.
    # Seit dem 30.08.2026 ist das eine Wahl und keine Notwendigkeit mehr: die
    # Daten tragen `owner_sub` und jede Abfrage filtert darauf. Vorher war das
    # Gate der einzige Schutz, weil jeder eingeloggte Account dasselbe Inventar
    # sah. Leer = offen für jeden angemeldeten Nutzer, jeder sieht dann seins.
    allowed_subs: Annotated[list[str], NoDecode] = []

    # Wem gehören Zeilen aus der Zeit vor der Mandantentrennung? Nur nötig, wenn
    # beim Umstieg Daten vorhanden sind und ALLOWED_SUBS nicht genau einen Sub
    # nennt. Ohne eindeutige Antwort bricht der Start ab, statt zu raten.
    assets_backfill_sub: str = ""

    cors_origins: Annotated[list[str], NoDecode] = [
        "https://shell.home.arpa",
        "https://assets.home.arpa",
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
