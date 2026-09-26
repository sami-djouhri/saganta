import httpx
import structlog
from fastapi import FastAPI, Header, HTTPException, Request, Response, status
from prometheus_fastapi_instrumentator import Instrumentator
from saganta_dienst.zugriffslog import einrichten as zugriffslog_einrichten

from .auth import authorization_header, verify_jwt
from .config import settings
from .kalender_auth import kalender_cache
from .tenant_sig import tenant_sig_headers

structlog.configure(processors=[structlog.processors.JSONRenderer()])
log = structlog.get_logger()

# Erfolgreiche Health-Pruefungen nicht ins Zugriffsprotokoll, sie stellten
# zuletzt 98-100 % aller Zeilen und machten echte Ereignisse unauffindbar.
# Fehlgeschlagene Pruefungen bleiben sichtbar.
zugriffslog_einrichten()

app = FastAPI(
    title="Saganta Auth-Proxy",
    version="0.1.0",
    description=(
        "Validiert Saganta-JWTs (HS256, iss=saganta) und proxied an Backend-Services. "
        "Mountpoints: /lifeops/, /kalender/, /briefkasten/. "
        "Backends bleiben unverändert; der Proxy stempelt deren erwarteten Bearer-Token ein."
    ),
)

HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
    "host",
    "content-length",
}


Instrumentator().instrument(app).expose(
    app, endpoint="/metrics", include_in_schema=False, tags=["observability"]
)


@app.get("/healthz")
@app.get("/health")
@app.get("/health/ready")
def healthz() -> dict[str, object]:
    return {"ok": True, "service": "saganta-auth-proxy"}


async def _resolve_backend_token(backend: str) -> tuple[str, str, str]:
    """Liefert (header_name, scheme, value) für den Backend-Auth-Header."""
    if backend == "lifeops":
        return ("Authorization", "Bearer", settings.lifeops_internal_token)
    if backend == "kalender":
        token = await kalender_cache.get()
        return ("Authorization", "Bearer", token or "")
    if backend == "briefkasten":
        return ("Authorization", "Bearer", settings.briefkasten_internal_token)
    raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown backend: {backend}")


def _backend_base_url(backend: str) -> str:
    adressen = {
        "lifeops": settings.lifeops_base_url,
        "kalender": settings.kalender_base_url,
        "briefkasten": settings.briefkasten_base_url,
    }
    if backend not in adressen:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown backend: {backend}")
    # ★★ Ein Backend ohne Adresse ist nicht konfiguriert, und das ist eine
    # Aussage, keine Stoerung (2026-09-12). Vorher trugen alle drei Adressen
    # einen Dienstnamen als Vorbelegung, auch der, den dieses Repo nicht
    # mitliefert: der Proxy versuchte dann eine Verbindung, scheiterte an der
    # Namensauflösung und meldete 502 "upstream error". Wer das Protokoll las,
    # suchte einen kaputten Dienst statt einen fehlenden Eintrag. 503 sagt
    # dagegen genau, was fehlt, und kostet keinen Verbindungsversuch.
    if not adressen[backend]:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"Backend {backend} ist nicht konfiguriert "
            f"({backend.upper()}_BASE_URL ist leer).",
        )
    return adressen[backend]


async def _proxy(backend: str, path: str, request: Request, authorization: str) -> Response:
    claims = verify_jwt(authorization, expected_audience=backend)

    base_url = _backend_base_url(backend)
    target = f"{base_url.rstrip('/')}/{path}"
    body = await request.body()

    # Die X-Saganta-*-Familie besetzt AUSSCHLIESSLICH dieser Proxy: sie ist die
    # Identitätsaussage gegenüber dem Backend und darf nie aus dem Client stammen.
    # Ohne dieses Verwerfen reichte ein mitgeschicktes X-Saganta-Sub-Sig ungeprüft
    # durch (X-Saganta-Sub selbst wurde schon immer überschrieben, die Signatur
    # nicht), der Client könnte dem Backend eine fremde Unterschrift unterschieben.
    upstream_headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in HOP_BY_HOP
        and k.lower() != "authorization"
        and not k.lower().startswith("x-saganta-")
    }

    header_name, scheme, token = await _resolve_backend_token(backend)
    if token:
        upstream_headers[header_name] = authorization_header(scheme, token)

    upstream_headers["X-Saganta-Sub"] = claims["sub"]
    upstream_headers["X-Saganta-Email"] = claims.get("email", "")
    upstream_headers["X-Saganta-Groups"] = ",".join(claims.get("groups", []) or [])
    # Echtheitsnachweis nur für den Kalender, nur dort gilt das Geheimnis, und ein
    # Backend soll keine Signatur zu sehen bekommen, die es nicht prüfen kann.
    if backend == "kalender":
        upstream_headers.update(tenant_sig_headers(claims["sub"]))

    async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
        try:
            resp = await client.request(
                request.method,
                target,
                params=request.query_params,
                content=body,
                headers=upstream_headers,
            )
        except httpx.HTTPError as e:
            log.warning("upstream.error", backend=backend, target=target, error=str(e))
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"upstream error: {e}") from e

    # Bei 401 vom Kalender: Token-Cache invalidieren, nächster Call holt neu.
    if backend == "kalender" and resp.status_code == 401:
        kalender_cache.invalidate()

    response_headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
        media_type=resp.headers.get("content-type"),
    )


@app.api_route("/lifeops/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def proxy_lifeops(path: str, request: Request, authorization: str = Header(...)) -> Response:
    return await _proxy("lifeops", path, request, authorization)


@app.api_route("/kalender/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def proxy_kalender(path: str, request: Request, authorization: str = Header(...)) -> Response:
    return await _proxy("kalender", path, request, authorization)


@app.api_route("/briefkasten/{path:path}", methods=["GET", "POST", "PATCH", "PUT", "DELETE"])
async def proxy_briefkasten(
    path: str, request: Request, authorization: str = Header(...)
) -> Response:
    return await _proxy("briefkasten", path, request, authorization)
