from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten
from sqlalchemy import text

from .config import settings
from .db import engine, init_db
from .routes_eintraege import router as eintraege_router
from .routes_tresor import router as tresor_router
from .zugriffsmaske import einrichten as datumsmaske_einrichten

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Zwei Filter am selben Logger, mit verschiedenen Aufgaben:
# der geteilte nimmt das Rauschen der Health-Pruefungen heraus, der eigene
# nimmt die Datumsangaben aus den Adressen. Warum Letzteres hier zwingend ist,
# steht in zugriffsmaske.py.
zugriffslog_einrichten()
datumsmaske_einrichten()


@asynccontextmanager
async def lebenszyklus(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info(
        "tagebuch-api.startup",
        cors=settings.cors_origins,
        max_chiffrat_kb=settings.eintrag_max_chiffrat_bytes // 1024,
    )
    yield


app = FastAPI(
    title="Saganta Tagebuch-API",
    version="0.1.0",
    description=(
        "Ablage fuer Ende-zu-Ende-verschluesselte Tageseintraege. Der Dienst "
        "verwahrt Chiffrat und die verpackten Schluessel; entschluesselt wird "
        "ausschliesslich im Browser. Es gibt keine Suche und keine Auswertung, "
        "weil beides Klartext braeuchte."
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
    return {"ok": True, "service": "saganta-tagebuch-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "service": "saganta-tagebuch-api", "db": "ok"})
    except Exception as exc:
        return JSONResponse(
            {
                "ok": False,
                "service": "saganta-tagebuch-api",
                "db": "error",
                "error": str(exc)[:200],
            },
            status_code=503,
        )


app.include_router(tresor_router, prefix="/api/tresor", tags=["tresor"])
app.include_router(eintraege_router, prefix="/api/eintraege", tags=["eintraege"])
