import os
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Upstream nativer kalender-Container (cc-core). LAN-Fallback: host:8085.
    kalender_base_url: str = "http://kalender:8085"
    kalender_timeout_seconds: float = 5.0

    # `kalender_feed_token` ist am 2026-10-16 entfallen und wird bewusst nicht
    # als unbenutztes Feld weitergeführt. Der Upstream-Client meldete sich damit
    # per `token-login` an, und dieser Token gehört dem OWNER: die Sitzung jedes
    # Mandanten war damit die des Owners (siehe app/upstream.py). Die Anmeldung
    # läuft jetzt über `gate-login` mit dem signierten Mandanten. Eine Zeile
    # `KALENDER_FEED_TOKEN=` in der .env stört nicht, unbekannte Variablen werden
    # ignoriert; sie trägt nur nichts mehr.

    # Echtheitsnachweis für X-Saganta-Sub (siehe app/tenant_sig.py und
    # backend/tenant_auth.py im nativen Kalender).
    #
    # ⚠️ Seit dem 2026-10-16 ist leer hier NICHT mehr „wie bisher": die Anmeldung
    # am nativen Dienst (`gate-login`) hängt an der Signatur. Ohne Geheimnis
    # antwortet der BFF mit 503 statt headerlos auf den Owner zu fallen.
    # Muss identisch zu KALENDER_TENANT_SECRET dort sein.
    kalender_tenant_secret: str = ""

    # `kalender_owner_sub` ist am 2026-10-16 entfallen. Er trug den Owner-Riegel
    # vor GET /api/feed-token, und der war nötig, solange der native Endpunkt
    # jedem denselben Token gab. Seit dem 2026-09-27 hat dort jeder Mandant seinen
    # eigenen (`mandant_einstellungen`), und seit dem Umbau von `token-login` auf
    # `gate-login` in app/upstream.py gehört die Sitzung auch dem richtigen.
    # Belegt am laufenden Dienst, siehe app/routes_mobile.py.

    # LLM-Gateway (LiteLLM, OpenAI-Format) fuer POST /api/chat. Leer => der
    # Endpunkt antwortet mit 503 statt still nichts zu koennen. Das Modell muss
    # in `routes_chat.ERLAUBTE_MODELLE` stehen: die Termine dieses Hauses gehen
    # an keinen fremden Dienst, und das Gateway koennte auch dorthin vermitteln.
    llm_gateway_url: str = ""
    llm_gateway_key: str = ""
    llm_model: str = "homelab-fast"
    # Jemand wartet auf diese Antwort, anders als beim naechtlichen Briefing in
    # news-api. Laenger als eine halbe Minute ist keine Antwort mehr.
    llm_timeout_seconds: float = 30.0

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
