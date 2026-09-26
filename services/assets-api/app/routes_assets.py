from datetime import datetime, timedelta, timezone

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from .auth import CurrentUser, Me
from .config import settings
from .db import get_db
from .models import Asset
from .resale import resale_recommendation
from .schemas import AssetIn, AssetOut, AssetPatch, MarketUpdate, SyncResult
from .upstream import lager_client, marktwatch_client


log = structlog.get_logger()
router = APIRouter()


def _eigenes_asset(db: Session, me: Me, asset_id: int) -> Asset:
    """Ein Asset dieses Nutzers, sonst 404.

    Bewusst nicht `db.get(Asset, id)` mit anschliessender Pruefung: der Aufruf
    ohne Mandantenfilter ist die Stelle, an der Trennung typischerweise verloren
    geht, und ein 404 verraet einem Fremden nicht einmal, dass es die Zeile gibt.
    """
    a = db.query(Asset).filter(Asset.id == asset_id, Asset.owner_sub == me.sub).one_or_none()
    if not a:
        raise HTTPException(404, "asset not found")
    return a


def _to_out(a: Asset) -> AssetOut:
    rec, reason = resale_recommendation(a)
    return AssetOut(
        id=a.id,
        source=a.source,
        source_id=a.source_id,
        name=a.name,
        category=a.category,
        location=a.location,
        usage_status=a.usage_status,
        purchase_date=a.purchase_date,
        purchase_price_eur=a.purchase_price_eur,
        market_value_eur=a.market_value_eur,
        market_value_at=a.market_value_at,
        notes=a.notes,
        created_at=a.created_at,
        updated_at=a.updated_at,
        resale_recommended=rec,
        resale_reason=reason,
    )


@router.get("", response_model=list[AssetOut])
def list_assets(
    me: Me = CurrentUser,
    source: str | None = Query(None),
    usage_status: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[AssetOut]:
    q = db.query(Asset).filter(Asset.owner_sub == me.sub)
    if source:
        q = q.filter(Asset.source == source)
    if usage_status:
        q = q.filter(Asset.usage_status == usage_status)
    return [_to_out(a) for a in q.order_by(Asset.updated_at.desc()).all()]


@router.post("", response_model=AssetOut, status_code=201)
def create_asset(
    payload: AssetIn,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> AssetOut:
    a = Asset(owner_sub=me.sub, source="saganta", **payload.model_dump())
    db.add(a)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.get("/recommendations", response_model=list[AssetOut])
def recommendations(me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[AssetOut]:
    outs = [_to_out(a) for a in db.query(Asset).filter(Asset.owner_sub == me.sub).all()]
    return [o for o in outs if o.resale_recommended]


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> AssetOut:
    a = _eigenes_asset(db, me, asset_id)
    return _to_out(a)


@router.patch("/{asset_id}", response_model=AssetOut)
def patch_asset(
    asset_id: int,
    payload: AssetPatch,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> AssetOut:
    a = _eigenes_asset(db, me, asset_id)
    if a.source != "saganta":
        raise HTTPException(409, "mirrored assets sind read-only, Quelle editieren")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    db.commit()
    db.refresh(a)
    return _to_out(a)


@router.delete("/{asset_id}", status_code=204)
def delete_asset(asset_id: int, me: Me = CurrentUser, db: Session = Depends(get_db)) -> None:
    a = _eigenes_asset(db, me, asset_id)
    if a.source != "saganta":
        raise HTTPException(409, "mirrored assets nicht löschbar")
    db.delete(a)
    db.commit()


_LAGER_SEITE = 200  # == Vorgabe-limit des Lagers, mehr nimmt es nicht an


async def _lager_electronics(owner_sub: str) -> list[dict]:
    """Holt alle Elektronik-Zeilen dieses Nutzers aus dem Lager.

    Das Lager antwortet mit einer paginierten Hülle (`items`/`total`/`offset`/
    `limit`), nicht mit einer flachen Liste. Wer das JSON direkt iteriert, läuft
    über die Schlüssel des Objekts und hält Strings in der Hand: genau daran
    brach der Spiegel, seit es ihn gibt ("'str' object has no attribute 'get'"),
    weshalb die Asset-Tabelle bis 2026-09-18 leer blieb. Eine flache Liste wird
    weiter akzeptiert, damit ein anderes oder älteres Lager nicht ausfällt.

    Geblättert wird bis `total`, weil das Lager pro Seite höchstens 200 Zeilen
    gibt: ein stilles Abschneiden wäre hier besonders unauffällig, denn ein
    Spiegel mit 200 von 300 Geräten sieht vollständig aus.
    """
    gesammelt: list[dict] = []
    offset = 0
    async with lager_client(owner_sub) as client:
        while True:
            try:
                r = await client.get(
                    "/api/electronics",
                    params={"offset": offset, "limit": _LAGER_SEITE},
                )
            except httpx.HTTPError as e:
                raise HTTPException(502, f"lager unreachable: {e}") from e
            if r.status_code >= 400:
                raise HTTPException(r.status_code, f"lager: {r.text[:200]}")
            # `or []`: ein wörtliches JSON-null (r.content vorhanden, r.json() == None)
            # würde sonst die Iteration unten mit TypeError sprengen.
            nutzlast = (r.json() if r.content else []) or []
            if not isinstance(nutzlast, dict):
                return list(nutzlast)
            seite = nutzlast.get("items") or []
            gesammelt.extend(seite)
            gesamt = nutzlast.get("total")
            if not seite or gesamt is None or len(gesammelt) >= gesamt:
                return gesammelt
            offset += len(seite)


@router.post("/sync/lager", response_model=SyncResult)
async def sync_lager(me: Me = CurrentUser, db: Session = Depends(get_db)) -> SyncResult:
    """Read-only Mirror der lager.electronics in unsere Asset-Tabelle."""
    items = await _lager_electronics(me.sub)

    added = updated = 0
    for it in items:
        sid = str(it.get("id"))
        existing = (
            db.query(Asset)
            .filter(
                Asset.owner_sub == me.sub,
                Asset.source == "lager-electronics",
                Asset.source_id == sid,
            )
            .one_or_none()
        )
        fields = {
            "name": it.get("name", "?"),
            "category": it.get("category"),
            "location": it.get("location"),
            "usage_status": it.get("usage_status") or "reserve",
            "purchase_price_eur": it.get("purchase_price"),
            "market_value_eur": it.get("estimated_resale_value"),
        }
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            updated += 1
        else:
            db.add(Asset(owner_sub=me.sub, source="lager-electronics", source_id=sid, **fields))
            added += 1
    db.commit()
    log.info("assets.sync.lager", added=added, updated=updated)
    return SyncResult(source="lager-electronics", added=added, updated=updated, skipped=0)


@router.post("/{asset_id}/market", response_model=MarketUpdate)
async def refresh_market_value(
    asset_id: int,
    force: bool = Query(False),
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> MarketUpdate:
    a = _eigenes_asset(db, me, asset_id)

    # Cache prüfen
    if not force and a.market_value_at:
        age = datetime.now(timezone.utc) - a.market_value_at
        if age < timedelta(minutes=settings.market_cache_ttl_minutes):
            return MarketUpdate(
                asset_id=a.id,
                market_value_eur=a.market_value_eur,
                market_value_at=a.market_value_at,
                samples=0,
            )

    # Ohne Marktdaten-Quelle gibt es keinen Marktwert, und das ist eine
    # Konfigurationsaussage, keine Stoerung. Ein Verbindungsversuch gegen eine
    # leere Adresse endete sonst in 502 "unreachable", was nach einem kaputten
    # Dienst aussieht und die Oberflaeche zum Wiederholen einlaedt.
    if not settings.marktwatch_base_url:
        raise HTTPException(
            503,
            "Keine Marktdaten-Quelle konfiguriert (MARKTWATCH_BASE_URL ist leer).",
        )

    query = a.name
    if a.category:
        query = f"{a.name} {a.category}"

    try:
        async with marktwatch_client() as client:
            r = await client.post("/crawl/search", json={"query": query, "limit": 20})
    except httpx.HTTPError as e:
        raise HTTPException(502, f"marktwatch unreachable: {e}") from e
    if r.status_code >= 400:
        raise HTTPException(r.status_code, f"marktwatch: {r.text[:200]}")

    results = (r.json() if r.content else []) or []
    # Preise defensiv parsen: ein nicht-numerischer Wert von marktwatch würde sonst
    # den ganzen Endpunkt mit ValueError (500) killen.
    prices: list[float] = []
    for x in results:
        if not isinstance(x, dict) or not x.get("price"):
            continue
        try:
            prices.append(float(x["price"]))
        except (TypeError, ValueError):
            continue
    median = None
    if prices:
        prices.sort()
        n = len(prices)
        mid = n // 2
        # Echter Median: bei gerader Anzahl das Mittel der beiden mittleren Werte,
        # sonst verzerrt der obere Mittelwert den Marktwert-Schätzer nach oben.
        median = prices[mid] if n % 2 else (prices[mid - 1] + prices[mid]) / 2

    a.market_value_eur = median
    a.market_value_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(a)
    return MarketUpdate(
        asset_id=a.id,
        market_value_eur=a.market_value_eur,
        market_value_at=a.market_value_at,
        samples=len(prices),
    )
