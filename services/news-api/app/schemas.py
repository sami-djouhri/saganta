from datetime import datetime

from pydantic import BaseModel, Field


class SourceOut(BaseModel):
    id: int
    slug: str
    name: str
    enabled: bool
    last_polled_at: datetime | None
    last_error: str | None


class FeedItemOut(BaseModel):
    id: int
    source_id: int
    source_slug: str
    source_name: str
    title: str
    link: str
    summary: str | None
    author: str | None
    published_at: datetime | None
    fetched_at: datetime
    # Per-User-State (aus UserItemState gejoint; default false wenn kein Row)
    read: bool = False
    bookmarked: bool = False


class FeedPage(BaseModel):
    items: list[FeedItemOut]
    offset: int
    limit: int
    total: int
    next_offset: int | None


class ItemStatePatch(BaseModel):
    read: bool | None = Field(None)
    bookmarked: bool | None = Field(None)
