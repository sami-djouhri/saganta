import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_
from sqlalchemy.orm import Session

from .auth import CurrentUser, Me
from .config import settings
from .db import get_db
from .models import FeedItem, FeedSource, UserItemState
from .schemas import FeedItemOut, FeedPage, ItemStatePatch, SourceOut

log = structlog.get_logger()
router = APIRouter()


@router.get("/sources", response_model=list[SourceOut])
def list_sources(me: Me = CurrentUser, db: Session = Depends(get_db)) -> list[SourceOut]:
    rows = db.query(FeedSource).filter(FeedSource.enabled.is_(True)).order_by(FeedSource.name).all()
    return [
        SourceOut(
            id=s.id,
            slug=s.slug,
            name=s.name,
            enabled=s.enabled,
            last_polled_at=s.last_polled_at,
            last_error=s.last_error,
        )
        for s in rows
    ]


@router.get("/feed", response_model=FeedPage)
def get_feed(
    me: Me = CurrentUser,
    offset: int = Query(0, ge=0),
    limit: int | None = Query(None, ge=1),
    source: str | None = Query(None, description="FeedSource.slug filtern"),
    bookmarked: bool = Query(False, description="nur Bookmarks dieses Users"),
    db: Session = Depends(get_db),
) -> FeedPage:
    page_size = min(limit or settings.default_feed_page_size, settings.max_feed_page_size)

    # LEFT JOIN UserItemState NUR für diesen sub → read/bookmarked pro User, default false.
    q = (
        db.query(FeedItem, FeedSource, UserItemState)
        .join(FeedSource, FeedSource.id == FeedItem.source_id)
        .outerjoin(
            UserItemState,
            and_(
                UserItemState.item_id == FeedItem.id,
                UserItemState.sub == me.sub,
            ),
        )
    )
    if source:
        q = q.filter(FeedSource.slug == source)
    if bookmarked:
        q = q.filter(UserItemState.bookmarked.is_(True))

    total = q.count()
    rows = (
        q.order_by(FeedItem.published_at.desc().nullslast(), FeedItem.fetched_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    items = [
        FeedItemOut(
            id=item.id,
            source_id=item.source_id,
            source_slug=src.slug,
            source_name=src.name,
            title=item.title,
            link=item.link,
            summary=item.summary,
            author=item.author,
            published_at=item.published_at,
            fetched_at=item.fetched_at,
            read=bool(state.read) if state else False,
            bookmarked=bool(state.bookmarked) if state else False,
        )
        for item, src, state in rows
    ]
    next_offset = offset + page_size if offset + page_size < total else None
    return FeedPage(items=items, offset=offset, limit=page_size, total=total, next_offset=next_offset)


@router.post("/items/{item_id}/state", response_model=FeedItemOut)
def set_item_state(
    item_id: int,
    payload: ItemStatePatch,
    me: Me = CurrentUser,
    db: Session = Depends(get_db),
) -> FeedItemOut:
    item = db.get(FeedItem, item_id)
    if not item:
        raise HTTPException(404, "item not found")
    src = db.get(FeedSource, item.source_id)

    state = (
        db.query(UserItemState)
        .filter(UserItemState.sub == me.sub, UserItemState.item_id == item_id)
        .one_or_none()
    )
    if state is None:
        state = UserItemState(sub=me.sub, item_id=item_id)
        db.add(state)

    data = payload.model_dump(exclude_unset=True)
    if "read" in data:
        state.read = bool(data["read"])
    if "bookmarked" in data:
        state.bookmarked = bool(data["bookmarked"])
    db.commit()
    db.refresh(state)

    return FeedItemOut(
        id=item.id,
        source_id=item.source_id,
        source_slug=src.slug if src else "",
        source_name=src.name if src else "",
        title=item.title,
        link=item.link,
        summary=item.summary,
        author=item.author,
        published_at=item.published_at,
        fetched_at=item.fetched_at,
        read=bool(state.read),
        bookmarked=bool(state.bookmarked),
    )
