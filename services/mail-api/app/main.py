import asyncio

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten

from .config import settings
from .db import Base, engine, leichte_migrationen
from .routes_mail import router as mail_router
from .routes_oauth import router as oauth_router
from .sync import poll_loop


structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Erfolgreiche Health-Pruefungen nicht ins Zugriffsprotokoll, sie stellten
# zuletzt 98-100 % aller Zeilen und machten echte Ereignisse unauffindbar.
# Fehlgeschlagene Pruefungen bleiben sichtbar.
zugriffslog_einrichten()

app = FastAPI(
    title="Saganta Mail-API",
    version="0.1.0",
    description="Aggregator-Inbox: bündelt externe IMAP-Konten der Mitglieder, Versand via Origin-SMTP.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    Base.metadata.create_all(engine)
    # Fehlende Spalten an bestehenden Tabellen nachziehen. `create_all` legt nur
    # fehlende TABELLEN an; ohne diesen Schritt startet der Dienst gruen und
    # scheitert bei der ersten Abfrage an einer unbekannten Spalte.
    leichte_migrationen()
    asyncio.create_task(poll_loop())
    log.info("mail-api.startup", cors=settings.cors_origins, sync=settings.sync_interval_seconds)


Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "saganta-mail-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "service": "saganta-mail-api", "db": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "service": "saganta-mail-api", "db": "error", "error": str(exc)[:200]},
            status_code=503,
        )


app.include_router(mail_router, prefix="/api/mail", tags=["mail"])
app.include_router(oauth_router, prefix="/api/mail", tags=["mail-oauth"])
