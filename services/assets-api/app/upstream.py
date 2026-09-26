import httpx

from .config import settings


def lager_client(owner_sub: str | None = None) -> httpx.AsyncClient:
    # Multiuser: den Nutzer-Sub als X-Saganta-Sub an lager propagieren, damit der
    # Electronics-Mirror den Bestand des jeweiligen Tenants zieht (statt headerlos
    # auf lagers DEFAULT_OWNER_SUB zu fallen). Vgl. mealprep/lager_adapter.
    headers = {"X-Saganta-Sub": owner_sub} if owner_sub else None
    return httpx.AsyncClient(
        base_url=settings.lager_base_url,
        timeout=settings.lager_timeout_seconds,
        headers=headers,
    )


def marktwatch_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=settings.marktwatch_base_url,
        timeout=settings.marktwatch_timeout_seconds,
    )
