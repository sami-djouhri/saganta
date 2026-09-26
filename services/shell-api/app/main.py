import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten

from .config import settings
from .db import Base, engine
from .routes_gate import router as gate_router
from .routes_me import router as me_router

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Erfolgreiche Health-Pruefungen nicht ins Zugriffsprotokoll, sie stellten
# zuletzt 98-100 % aller Zeilen und machten echte Ereignisse unauffindbar.
# Fehlgeschlagene Pruefungen bleiben sichtbar.
zugriffslog_einrichten()

app = FastAPI(
    title="Saganta Shell-API",
    version="0.1.0",
    description="User-Settings, App-Registry, Audit-Log für die Saganta-Suite.",
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
    Base.metadata.create_all(engine)
    log.info("shell-api.startup", cors=settings.cors_origins)


Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "saganta-shell-api"}


@app.get("/health/ready")
def health_ready() -> JSONResponse:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return JSONResponse({"ok": True, "service": "saganta-shell-api", "db": "ok"})
    except Exception as exc:
        return JSONResponse(
            {"ok": False, "service": "saganta-shell-api", "db": "error", "error": str(exc)[:200]},
            status_code=503,
        )


app.include_router(me_router, prefix="/api", tags=["me"])
app.include_router(gate_router, prefix="/api", tags=["gate"])
