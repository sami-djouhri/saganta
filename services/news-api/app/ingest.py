"""RSS/Atom-Ingest: pollt enabled FeedSources, dedupet Items via (source_id, guid).

Stage 1 bewusst simpel: kein AI/Clustering, kein Pruning. In-Process asyncio-Loop
statt externem Cron: sauberes Lifecycle mit dem Service.
"""
import asyncio
from datetime import datetime, timezone
from time import struct_time

import feedparser
import httpx
import structlog
from sqlalchemy.orm import Session

from .config import settings
from .db import SessionLocal
from .errors import describe
from .models import FeedItem, FeedSource

log = structlog.get_logger()


def _to_utc(parsed: struct_time | None) -> datetime | None:
    if not parsed:
        return None
    try:
        # feedparser liefert struct_time in UTC (published_parsed/updated_parsed)
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def seed_sources(db: Session) -> int:
    """Ergänzt fehlende Default-/SEED_FEEDS-Quellen (idempotent, per slug).

    Bewusst additiv statt „nur bei leerer DB": so wächst das kuratierte Feed-Set
    beim Deploy mit, ohne bereits vorhandene Quellen (inkl. Nutzer-Deaktivierungen)
    anzufassen. Vorhandene slugs bleiben unberührt.
    """
    existing = {slug for (slug,) in db.query(FeedSource.slug).all()}
    added = 0
    for s in settings.effective_seed_feeds():
        if s["slug"] in existing:
            continue
        db.add(FeedSource(slug=s["slug"], name=s["name"], feed_url=s["feed_url"]))
        added += 1
    if added:
        db.commit()
        log.info("news.seed", added=added)
    return added


async def poll_source(db: Session, source: FeedSource) -> int:
    """Holt einen Feed, speichert neue Items (skip bei Dedup-Konflikt). Gibt #neu zurück."""
    new_items = 0
    try:
        async with httpx.AsyncClient(timeout=settings.feed_fetch_timeout) as client:
            resp = await client.get(source.feed_url, follow_redirects=True)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)

        # Bereits gespeicherte GUIDs dieser Quelle vorab laden. autoflush=False heißt:
        # neu hinzugefügte Items sind in derselben Schleife noch nicht über query()
        # sichtbar, daher tracken wir sie im selben Set, sonst doppelt eingefügte
        # GUIDs (kommen in echten Feeds vor!) sprengen den UNIQUE-Constraint beim
        # commit und rollen den GANZEN Batch zurück (Memory: autoflush-Falle).
        seen: set[str] = {
            g for (g,) in db.query(FeedItem.guid).filter(FeedItem.source_id == source.id).all()
        }

        for entry in parsed.entries:
            guid = (entry.get("id") or entry.get("link") or "")[:500]
            if not guid or guid in seen:
                continue
            seen.add(guid)
            published = _to_utc(
                entry.get("published_parsed") or entry.get("updated_parsed")
            )
            db.add(
                FeedItem(
                    source_id=source.id,
                    guid=guid,
                    title=(entry.get("title") or "(ohne Titel)")[:500],
                    link=(entry.get("link") or "")[:1000],
                    summary=entry.get("summary"),
                    author=(entry.get("author") or None),
                    published_at=published,
                )
            )
            new_items += 1

        source.last_polled_at = datetime.now(timezone.utc)
        source.last_error = None
        db.commit()
        log.info("news.poll.ok", source=source.slug, new=new_items)
    except Exception as exc:  # eine kaputte Quelle darf den Loop nicht killen
        db.rollback()
        source.last_polled_at = datetime.now(timezone.utc)
        # describe() statt str(exc): Netzwerkfehler haben sonst einen leeren Text,
        # und ein leerer last_error ist falsy = nicht von "gesund" unterscheidbar.
        source.last_error = describe(exc, limit=300)
        db.commit()
        log.warning("news.poll.error", source=source.slug, error=describe(exc))
    return new_items


async def poll_all() -> int:
    db = SessionLocal()
    try:
        sources = db.query(FeedSource).filter(FeedSource.enabled.is_(True)).all()
        total = 0
        for source in sources:
            total += await poll_source(db, source)
        return total
    finally:
        db.close()


async def poll_loop() -> None:
    log.info("news.poll_loop.start", interval=settings.poll_interval_seconds)
    while True:
        try:
            await poll_all()
        except Exception as exc:  # Loop-Backstop
            log.error("news.poll_loop.error", error=str(exc)[:200])
        await asyncio.sleep(settings.poll_interval_seconds)
