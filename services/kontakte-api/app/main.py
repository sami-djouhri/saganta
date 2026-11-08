import asyncio
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
from . import abgleich
from .db import Base, SessionLocal, engine, get_db, init_db
from .konto import PLAN as LOESCHPLAN
from .routes import router

konto_router = loesch_mechanik.baue_router(LOESCHPLAN, Base.metadata, get_db, verify_jwt)

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()
zugriffslog_einrichten()


#: Abstand der Nachholversuche fuer einen ausstehenden Kalender-Abgleich.
NACHHOLEN_ALLE_S = 600


def _nachholen_einmal() -> None:
    db = SessionLocal()
    try:
        gelungen = abgleich.nachholen(db)
        if gelungen:
            log.info("kontakte.abgleich_nachgeholt", anzahl=gelungen)
    except Exception as exc:  # der Lauf darf den Dienst nie beenden
        log.warning("kontakte.nachholen_fehler", fehler=str(exc)[:200])
    finally:
        db.close()


async def _nachholen_schleife() -> None:
    while True:
        await asyncio.sleep(NACHHOLEN_ALLE_S)
        await asyncio.to_thread(_nachholen_einmal)


@asynccontextmanager
async def lebenszyklus(_app: FastAPI) -> AsyncIterator[None]:
    init_db()
    log.info("kontakte-api.startup", cors=settings.cors_origins, kalender=settings.kalender_bff_url)
    aufgabe = asyncio.create_task(_nachholen_schleife())
    yield
    aufgabe.cancel()


app = FastAPI(
    title="Saganta Kontakte-API",
    version="0.1.0",
    description=(
        "Der eine Ort, an dem Kontakte liegen: Telefon, Mail, Adresse, Geburtstag, "
        "Jahrestage, Gruppe und verknuepfte Termine. Der Kalender spiegelt die "
        "Tage und erinnert daran."
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
    return {"ok": True, "service": "saganta-kontakte-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "service": "saganta-kontakte-api", "db": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "service": "saganta-kontakte-api", "db": "error", "error": str(exc)[:200]},
            status_code=503,
        )


app.include_router(router, prefix="/api", tags=["kontakte"])
app.include_router(konto_router, prefix="/api/konto", tags=["konto"])
