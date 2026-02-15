"""Data models for RSS Feed Agent."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Feed:
    """Represents a subscribed RSS/Atom source."""

    url: str
    title: str
    description: str | None = None
    site_link: str | None = None
    last_fetched_at: datetime | None = None
    error_count: int = 0
    last_error: str | None = None
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    id: int | None = None


@dataclass
class Item:
    """Represents a single entry from a feed."""

    feed_id: int
    guid: str
    title: str
    link: str | None = None
    summary: str | None = None
    published_at: datetime | None = None
    is_read: bool = False
    fetched_at: datetime = field(default_factory=datetime.utcnow)
    id: int | None = None
