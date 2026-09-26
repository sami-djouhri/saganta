from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten
from sqlalchemy import text

from . import db as db_modul
from .config import settings
from .db import engine, init_db
from .routes_freigaben import router as freigaben_router
from .routes_notizbuecher import router as notizbuecher_router
from .routes_notizen import router as notizen_router
from .routes_oeffentlich import router as oeffentlich_router


structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Erfolgreiche Health-Pruefungen nicht ins Zugriffsprotokoll, sie stellten
# zuletzt 98-100 % aller Zeilen und machten echte Ereignisse unauffindbar.
# Fehlgeschlagene Pruefungen bleiben sichtbar.
zugriffslog_einrichten()

@asynccontextmanager
async def lebenszyklus(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info(
        "notizen-api.startup",
        cors=settings.cors_origins,
        volltextsuche="fts5" if db_modul.FTS_AKTIV else "like-rueckfall",
        anhang_quote_mb=settings.anhang_quote_bytes // (1024 * 1024),
    )
    if not db_modul.FTS_AKTIV:
        # Sichtbar machen statt still schlechter arbeiten: die Suche laeuft,
        # aber ueber LIKE, bei vielen Notizen merkt man das.
        log.warning("notizen-api.fts5_fehlt", hinweis="Volltextsuche laeuft im LIKE-Rueckfall")
    yield


app = FastAPI(
    title="Saganta Notizen-API",
    version="0.1.0",
    description=(
        "Notizbuecher, Markdown-Notizen mit Anhaengen, Verknuepfungen zu Terminen, "
        "Aufgaben, Projekten, Kontakten und Briefen, und teilbare Freigaben, "
        "wahlweise offen oder Ende-zu-Ende-verschluesselt."
    ),
    lifespan=lebenszyklus,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "saganta-notizen-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse(
            {
                "ok": True,
                "service": "saganta-notizen-api",
                "db": "ok",
                "volltextsuche": "fts5" if db_modul.FTS_AKTIV else "like",
            }
        )
    except Exception as exc:
        return JSONResponse(
            {
                "ok": False,
                "service": "saganta-notizen-api",
                "db": "error",
                "error": str(exc)[:200],
            },
            status_code=503,
        )


app.include_router(notizbuecher_router, prefix="/api/notizbuecher", tags=["notizbuecher"])
app.include_router(notizen_router, prefix="/api/notizen", tags=["notizen"])
app.include_router(freigaben_router, prefix="/api/freigaben", tags=["freigaben"])
# Ohne /api-Vorsatz und ohne Token: der Weg, den ein Empfaenger geht.
app.include_router(oeffentlich_router, prefix="/oeffentlich", tags=["oeffentlich"])
