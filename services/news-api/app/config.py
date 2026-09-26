import os
import json
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


# Neutrale öffentliche Default-Feeds. Über SEED_FEEDS (JSON) überschreibbar.
# Breite Themenabdeckung, damit die Briefing-Assembly für alle Interessen genug Pool
# hat (Owner-Ziel „mindestens mein Niveau"). Fehlende Slugs werden bei jedem Start
# additiv ergänzt (seed_sources ist idempotent). Alle URLs 2026-07-11 verifiziert.
DEFAULT_SEED_FEEDS: list[dict[str, str]] = [
    {"slug": "tagesschau", "name": "Tagesschau", "feed_url": "https://www.tagesschau.de/index~rss2.xml"},
    {"slug": "tagesschau-wirtschaft", "name": "Tagesschau Wirtschaft", "feed_url": "https://www.tagesschau.de/wirtschaft/index~rss2.xml"},
    {"slug": "tagesschau-inland", "name": "Tagesschau Inland", "feed_url": "https://www.tagesschau.de/inland/index~rss2.xml"},
    {"slug": "tagesschau-ausland", "name": "Tagesschau Ausland", "feed_url": "https://www.tagesschau.de/ausland/index~rss2.xml"},
    {"slug": "dlf-nachrichten", "name": "Deutschlandfunk", "feed_url": "https://www.deutschlandfunk.de/nachrichten-100.rss"},
    {"slug": "dw", "name": "Deutsche Welle", "feed_url": "https://rss.dw.com/rdf/rss-de-all"},
    {"slug": "heise", "name": "heise online", "feed_url": "https://www.heise.de/rss/heise-atom.xml"},
    {"slug": "heise-security", "name": "heise Security", "feed_url": "https://www.heise.de/security/feed.xml"},
    {"slug": "t3n", "name": "t3n", "feed_url": "https://t3n.de/rss.xml"},
    {"slug": "netzpolitik", "name": "netzpolitik.org", "feed_url": "https://netzpolitik.org/feed/"},
    {"slug": "sportschau", "name": "Sportschau", "feed_url": "https://www.sportschau.de/index~rss2.xml"},
    {"slug": "wissenschaft", "name": "wissenschaft.de", "feed_url": "https://wissenschaft.de/feed.xml"},
    # Forschung/Wissenschaft/KI/Medizin (2026-07-24 verifiziert, dt.): vertieft den
    # Pool für die Interessen-Tags ki/wissenschaft/gesundheit, damit das Briefing
    # neue Erkenntnisse aus KI, Technologie und Medizin aufnehmen kann.
    {"slug": "the-decoder", "name": "The Decoder (KI)", "feed_url": "https://the-decoder.de/feed/"},
    {"slug": "spektrum", "name": "Spektrum der Wissenschaft", "feed_url": "https://www.spektrum.de/alias/rss/spektrum-de-rss-feed/996406"},
    {"slug": "dlf-forschung", "name": "Deutschlandfunk Forschung aktuell", "feed_url": "https://www.deutschlandfunk.de/forschung-aktuell-100.rss"},
    {"slug": "scinexx", "name": "scinexx (Wissen & Medizin)", "feed_url": "https://www.scinexx.de/feed/"},
    {"slug": "tagesschau-wissen", "name": "Tagesschau Wissen", "feed_url": "https://www.tagesschau.de/wissen/index~rss2.xml"},
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:////data/news.db"

    # Ingest-Poller
    poll_interval_seconds: int = 900
    feed_fetch_timeout: float = 10.0
    default_feed_page_size: int = 30
    max_feed_page_size: int = 100

    # Seed-Quellen (JSON-Liste von {slug,name,feed_url}); leer => DEFAULT_SEED_FEEDS
    seed_feeds: Annotated[list[dict[str, str]], NoDecode] = []

    jwt_secret: str = "change-me-shared-with-auth-proxy"
    jwt_algorithm: str = "HS256"

    # Owner-Gate (Defense-in-Depth): nur diese better-auth-subs dürfen zugreifen.
    # Single-User-Suite → fremde Accounts gehören nicht auf private Daten.
    # Leer = offen (Rückwärtskompatibilität).
    allowed_subs: Annotated[list[str], NoDecode] = []

    # Wer darf Tarife setzen (Pro vergeben)? Bis Stripe live ist, vergibt der Owner
    # Pro manuell. Leer = niemand (Set-Plan-Endpoint aus).
    admin_subs: Annotated[list[str], NoDecode] = []

    # Interne Adresse des auth-service. Dorthin geht der Tarif, denn er gehoert
    # ans Konto und nicht in briefing_profiles (services/tarif_konto.py).
    # Bewusst als Vorgabe im Code und nicht in der .env: das ist eine
    # Container-Adresse im cc-core-Netz, kein Geheimnis. Leer schaltet den
    # Kontoweg ab, dann bleibt nur der Spiegel in der eigenen Datenbank.
    auth_service_url: str = "http://saganta-auth:3000"

    cors_origins: Annotated[list[str], NoDecode] = [
        "https://shell.home.arpa",
        "https://news.home.arpa",
    ]

    # ── Briefing (Multiuser) ────────────────────────────────────────────────
    # Öffentliche Basis-URL des news-Frontends (für absolute Enclosure-URLs im
    # Podcast-Feed). Leer => relative URLs (funktioniert nur In-App).
    public_base_url: str = ""
    # Tägliche Generierung (in-Process Scheduler), Stunde UTC. 2 UTC = 04:00 CEST,
    # bewusst VOR dem typischen Morgen-Playback (05:00-08:00), damit das MP3 fertig ist.
    briefing_generate_hour_utc: int = 2
    briefing_retention_days: int = 7
    # Zeitfenster, aus dem Artikel für ein Briefing gezogen werden.
    briefing_window_hours: int = 30
    # Max Artikel je Briefing (über alle Sektionen).
    briefing_max_items: int = 12
    briefing_max_same_source: int = 2
    # Wie viele Sprachfassungen ein Scheduler-Durchlauf hoechstens erzeugt.
    # XTTS arbeitet single-threaded und braucht 20 bis 40 Sekunden je Briefing,
    # und die Standard-Wunschzeit ist bei allen 06:30. Ohne Deckel arbeitet der
    # Tick alle faelligen Profile nacheinander ab und belegt den TTS-Dienst um
    # 06:30 fuer Minuten, waehrend Saganta und life-ops denselben brauchen.
    # Ueberzaehlige bekommen ihren Text sofort, die Sprachfassung zieht der
    # naechste Tick nach (der laeuft jede Minute). Das glaettet die Spitze,
    # statt jemanden auszulassen.
    briefing_audio_max_per_tick: int = 2

    # LLM-Gateway (LiteLLM, OpenAI-Format /v1/chat/completions). Leer => keine
    # LLM-Zusammenfassung, Briefing fällt auf Roh-Feed-Summaries zurück (Soft-Fail).
    llm_gateway_url: str = ""
    llm_gateway_key: str = ""
    llm_model: str = "homelab-fast"
    # 90 s reichten nicht: die Narration (max_tokens=600) braucht auf dem lokalen
    # Gemma-3-4B gemessen ~95 s und lief deshalb JEDEN Morgen in den Timeout, das
    # Briefing fiel still auf den deterministischen Text zurück. Der Aufruf liegt
    # ausschliesslich im Hintergrund-Renderpfad (briefing_service.render_audio),
    # niemand wartet darauf.
    llm_timeout: float = 300.0

    # TTS (Coqui XTTS auf ProDesk-LXC .16:5002). Leer => kein Audio (Soft-Fail).
    # tts_speaker = registrierter speaker_wav des XTTS-Servers (NICHT der Wyoming-
    # Bridge-Name "Sofia Hellen", der ergibt am /api/tts-Endpunkt 500).
    tts_url: str = ""
    tts_speaker: str = "stimme-de-frau.wav"
    tts_language: str = "de"
    tts_timeout: float = 180.0
    # Schreibbares Verzeichnis für gerenderte Briefing-Audios (liegt im /data-Volume,
    # da der Container read_only rootfs hat).
    audio_dir: str = "/data/briefing_audio"

    # Outbound-Webhook (opt-in pro User): Timeout für Zustell-POST.
    webhook_timeout: float = 10.0

    # ── Wetter ("Heute" im Briefing) ────────────────────────────────────────
    # Open-Meteo: kein API-Key, keine Registrierung, kein Homelab-Bezug, damit
    # auch für fremde Nutzer tragfähig. Leerer Wert => Wetter aus (Soft-Fail wie
    # tts_url/llm_gateway: ein fehlendes Wetter darf ein Briefing nie verhindern).
    weather_url: str = "https://api.open-meteo.com/v1/forecast"
    weather_timeout: float = 8.0
    # Neutraler Fallback (geografische Mitte Deutschlands), falls ein Profil noch
    # keinen eigenen Ort hinterlegt hat. Bewusst KEINE echte Wohnadresse im Code:
    # der persönliche Ort gehört ins Profil, nicht ins Repo.
    weather_default_lat: float = 51.16
    weather_default_lon: float = 10.45
    weather_default_place: str = "Deutschland"

    # ── Kalender-Kopplung ("Dein Tag" im Briefing) ──────────────────────────
    # Nativer kalender:8085, angesprochen über die öffentlichen feed_token-Endpunkte
    # (/api/day-type/{today,events,goals,sessions}) wie HA sie nutzt. Leer => "Dein
    # Tag" wird weggelassen (Soft-Fail; das Briefing bleibt gültig). Für Multiuser
    # scoped der optionale X-Saganta-Sub-Header pro User (Owner = DEFAULT_OWNER_SUB).
    kalender_url: str = "http://kalender:8085"
    kalender_feed_token: str = ""
    kalender_timeout: float = 6.0
    # Echtheitsnachweis für X-Saganta-Sub (app/services/tenant_sig.py). Leer = wie
    # bisher, nur der unsignierte Header. Muss identisch zu KALENDER_TENANT_SECRET
    # im nativen Kalender sein.
    kalender_tenant_secret: str = ""

    # ── Stripe (Self-Service-Payment für Pro) ───────────────────────────────
    # Leerer stripe_secret_key => Stripe AUS (Checkout gibt 503, Owner vergibt Pro
    # weiter manuell via /admin/set-plan). Soft-Fail wie tts_url/llm_gateway.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_price_id_pro: str = ""
    # Wohin Stripe nach Checkout zurückleitet (absolute URLs im news-Frontend).
    stripe_success_url: str = ""
    stripe_cancel_url: str = ""

    @field_validator("cors_origins", "allowed_subs", "admin_subs", mode="before")
    @classmethod
    def _split_cors(cls, v: object) -> object:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @field_validator("seed_feeds", mode="before")
    @classmethod
    def _parse_seed(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            return json.loads(v) if v else []
        return v

    def effective_seed_feeds(self) -> list[dict[str, str]]:
        return self.seed_feeds or DEFAULT_SEED_FEEDS


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
