import asyncio
import os

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten

from . import briefing_models  # noqa: F401  (registriert Briefing-Tabellen auf Base.metadata)
from .briefing_sched import briefing_loop
from .config import settings
from .db import Base, SessionLocal, engine
from .ingest import poll_loop, seed_sources
from .routes_briefing import router as briefing_router
from .routes_news import router as news_router


structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Erfolgreiche Health-Prüfungen nicht ins Zugriffsprotokoll, sie stellten
# zuletzt 98-100 % aller Zeilen und machten echte Ereignisse unauffindbar.
# Fehlgeschlagene Prüfungen bleiben sichtbar.
zugriffslog_einrichten()

app = FastAPI(
    title="Saganta News-API",
    version="0.1.0",
    description="Multiuser Familien-News aus öffentlichen RSS/Atom-Feeds (Stage 1).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_schema() -> None:
    """Idempotente Mini-Migrationen für additive Spalten (create_all ändert keine
    bestehenden Tabellen). Fehlt die Spalte, wird sie ergänzt; sonst still ignoriert."""
    from sqlalchemy import text as _text

    migrations = [
        "ALTER TABLE briefing_profiles ADD COLUMN plan VARCHAR(16) DEFAULT 'free'",
        "ALTER TABLE briefing_profiles ADD COLUMN stripe_customer_id VARCHAR(64)",
        "ALTER TABLE briefing_profiles ADD COLUMN stripe_subscription_id VARCHAR(64)",
        "ALTER TABLE briefing_profiles ADD COLUMN plan_status VARCHAR(16)",
        "ALTER TABLE briefing_profiles ADD COLUMN weather_lat FLOAT",
        "ALTER TABLE briefing_profiles ADD COLUMN weather_lon FLOAT",
        "ALTER TABLE briefing_profiles ADD COLUMN weather_place VARCHAR(120)",
    ]
    with engine.begin() as conn:
        for stmt in migrations:
            try:
                conn.execute(_text(stmt))
            except Exception:
                pass  # Spalte existiert bereits


@app.on_event("startup")
async def on_startup() -> None:
    Base.metadata.create_all(engine)
    _ensure_schema()
    db = SessionLocal()
    try:
        seed_sources(db)
    finally:
        db.close()
    os.makedirs(settings.audio_dir, exist_ok=True)
    asyncio.create_task(poll_loop())
    asyncio.create_task(briefing_loop())
    log.info("news-api.startup", cors=settings.cors_origins, poll=settings.poll_interval_seconds)


Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "saganta-news-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "service": "saganta-news-api", "db": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "service": "saganta-news-api", "db": "error", "error": str(exc)[:200]},
            status_code=503,
        )


app.include_router(news_router, prefix="/api/news", tags=["news"])
app.include_router(briefing_router, prefix="/api/news/briefing", tags=["briefing"])
