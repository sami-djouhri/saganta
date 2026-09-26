import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten

from .config import settings
from .routes_assistant import router as assistant_router
from .routes_capture import router as capture_router
from .routes_contacts import router as contacts_router
from .routes_events import router as events_router
from .routes_feedback import router as feedback_router
from .routes_feierabend import router as feierabend_router
from .routes_habits import router as habits_router
from .routes_mobile import router as mobile_router
from .routes_tagesdecke import router as tagesdecke_router
from .routes_tasks import router as tasks_router


structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Erfolgreiche Health-Pruefungen nicht ins Zugriffsprotokoll, sie stellten
# zuletzt 98-100 % aller Zeilen und machten echte Ereignisse unauffindbar.
# Fehlgeschlagene Pruefungen bleiben sichtbar.
zugriffslog_einrichten()

app = FastAPI(
    title="Saganta Kalender-BFF",
    version="0.1.0",
    description="Proxy + Auth-Bridge zum nativen kalender:8085.",
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
    log.info(
        "kalender-bff.startup",
        cors=settings.cors_origins,
        upstream=settings.kalender_base_url,
    )


Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
@app.get("/health/ready")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "saganta-kalender-bff"}


app.include_router(events_router, prefix="/api/events", tags=["events"])
# Volle Pfade im Router (kein Prefix): ein leerer Prefix-Routenpfad ("") triggert
# einen Instrumentator-Crash ('_IncludedRouter' has no attribute 'path').
app.include_router(capture_router, tags=["capture"])
app.include_router(tasks_router, tags=["tasks"])
app.include_router(assistant_router, tags=["assistant"])
app.include_router(feedback_router, tags=["feedback"])
app.include_router(feierabend_router, tags=["feierabend"])
# Nachgezogen 2026-08-20, damit die native Kalender-App ohne eigenes Passwort
# auskommt: sie nutzt 30 Endpunkte, der BFF kannte davon 12. Kontakte und
# Gewohnheiten fehlten ganz, ebenso der Bootstrap-Aufruf des Startbildschirms.
app.include_router(contacts_router, tags=["contacts"])
app.include_router(habits_router, tags=["habits"])
app.include_router(mobile_router, tags=["mobile"])
app.include_router(tagesdecke_router, tags=["tagesdecke"])
