import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from saganta_dienst import loeschen as loesch_mechanik
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten

from .config import settings
from .db import Base, engine, get_db, init_db
from .routes_dashboard import router as dashboard_router
from .routes_planning import router as planning_router
from .routes_projects import router as projects_router
from .auth import verify_jwt
from .konto import PLAN as LOESCHPLAN

konto_router = loesch_mechanik.baue_router(LOESCHPLAN, Base.metadata, get_db, verify_jwt)

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Erfolgreiche Health-Pruefungen nicht ins Zugriffsprotokoll, sie stellten
# zuletzt 98-100 % aller Zeilen und machten echte Ereignisse unauffindbar.
# Fehlgeschlagene Pruefungen bleiben sichtbar.
zugriffslog_einrichten()

app = FastAPI(
    title="Saganta ProjectDeck-API",
    version="0.1.0",
    description=(
        "Portfolio- und Entscheidungszentrale für alle Projekte: Status, Deadlines, "
        "Weekly Focus, Reviews, Shutdown, Public Pipeline und aktive Kalender-Planung."
    ),
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    log.info(
        "projectdeck-api.startup",
        cors=settings.cors_origins,
        kalender=settings.kalender_base_url,
        llm_enabled=settings.llm_enabled,
    )


Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "saganta-projectdeck-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "service": "saganta-projectdeck-api", "db": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "service": "saganta-projectdeck-api", "db": "error", "error": str(exc)[:200]},
            status_code=503,
        )


app.include_router(projects_router, prefix="/api/projects", tags=["projects"])
app.include_router(dashboard_router, prefix="/api", tags=["dashboard"])
app.include_router(planning_router, prefix="/api", tags=["planning"])
# Auskunft und Loeschung des eigenen Bestands. Der Loeschweg steht in konto.py,
# die Mechanik dahinter in saganta_dienst.loeschen.
app.include_router(konto_router, prefix="/api/konto", tags=["konto"])
