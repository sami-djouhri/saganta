from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from saganta_dienst import loeschen as loesch_mechanik
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten
from sqlalchemy import text

from .auth import verify_jwt
from .config import settings
from .db import Base, engine, get_db, init_db
from .konto import PLAN as LOESCHPLAN
from .routes import router

konto_router = loesch_mechanik.baue_router(LOESCHPLAN, Base.metadata, get_db, verify_jwt)

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()
zugriffslog_einrichten()


@asynccontextmanager
async def lebenszyklus(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info("aufgaben-api.startup", cors=settings.cors_origins, kalender=settings.kalender_bff_url)
    yield


app = FastAPI(
    title="Saganta Aufgaben-API",
    version="0.1.0",
    description=(
        "Der eine Ort, an dem Aufgaben liegen. Eine Aufgabe steht fuer sich und "
        "kann an einen Tag oder einen Termin geheftet werden. Freie Zeit, "
        "Kapazitaet und Tagesziele kommen aus dem Kalender."
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
    return {"ok": True, "service": "saganta-aufgaben-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "service": "saganta-aufgaben-api", "db": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "service": "saganta-aufgaben-api", "db": "error", "error": str(exc)[:200]},
            status_code=503,
        )


app.include_router(router, prefix="/api", tags=["aufgaben"])
app.include_router(konto_router, prefix="/api/konto", tags=["konto"])
