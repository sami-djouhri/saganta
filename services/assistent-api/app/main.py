import structlog
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten

from .config import settings
from .routes import router

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()
zugriffslog_einrichten()

app = FastAPI(
    title="Saganta Assistent-API",
    version="0.1.0",
    description=(
        "Ein Chat fuer alle Saganta-Apps. Das Modell versteht, Regeln rechnen, "
        "zurueck kommen Vorschlagskarten; ausgefuehrt wird erst in der App nach einem Tipp."
    ),
)

Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
def healthz() -> dict[str, object]:
    # Ohne Gateway kann der Dienst nichts beantworten; das soll man hier sehen,
    # statt erst an einer 503 der App.
    return {
        "ok": True,
        "service": "saganta-assistent-api",
        "modell": bool(settings.llm_gateway_url and settings.llm_gateway_key),
    }


app.include_router(router, tags=["assistent"])
