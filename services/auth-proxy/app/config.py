from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class BackendRoute(BaseModel):
    audience: str
    base_url: str
    token: str = ""
    token_header: str = "Authorization"
    token_scheme: str = "Bearer"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    # life-ops-api ist aktuell ungeschützt; wenn es Bearer-Auth bekommt, ein
    # Token hier hinterlegen.
    #
    # ★★ Leere Vorbelegung, seit 2026-09-12. Hier stand `http://life-ops-api:8000`,
    # und life-ops ist der einzige der drei Backends, den dieses Repo nicht
    # mitliefert (Kalender und Briefkasten schon). In einer Installation ohne
    # life-ops lief damit jeder Aufruf von `/lifeops/*` in einen DNS-Fehler:
    # zwei Protokollzeilen je Seitenaufruf der Schale, waehrend die Oberflaeche
    # nichts davon zeigte. Nicht konfiguriert heisst jetzt nicht konfiguriert,
    # und nicht "zeigt auf einen Namen, den es hier nicht gibt".
    lifeops_base_url: str = ""
    lifeops_internal_token: str = ""

    # Kalender (host:8085), nutzt FEED_TOKEN → /api/auth/token-login →
    # bekommt JWT-Cookie, dessen Wert als Bearer auf /api/* funktioniert.
    # Wir holen den JWT lazy und cachen ihn bis kurz vor Ablauf.
    kalender_base_url: str = "http://kalender:8085"
    kalender_feed_token: str = ""
    kalender_token_ttl_hours: int = 23  # JWT_EXPIRATION_HOURS - 1
    # Echtheitsnachweis für X-Saganta-Sub (app/tenant_sig.py). Leer = wie bisher,
    # nur der unsignierte Header. Muss identisch zu KALENDER_TENANT_SECRET im
    # nativen Kalender sein.
    kalender_tenant_secret: str = ""

    # Briefkasten (host:8101), Phase 1: deaktiviert. Internal-Search ist
    # auf Bearer, aber liefert nur Such-Snippets; volle Mail-Integration
    # braucht eine `/api/internal/*` Erweiterung am Briefkasten.
    briefkasten_base_url: str = "http://briefkasten:8000"
    briefkasten_internal_token: str = ""

    timeout_seconds: float = 10.0


settings = Settings()
