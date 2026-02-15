"""Agent tool implementations for RSS Feed Agent."""

import json
from datetime import datetime

from langchain_core.tools import tool

from rssfeed_agent.database import Database
from rssfeed_agent.feed_parser import FeedParseError, fetch_and_parse
from rssfeed_agent.models import Feed, Item

# Module-level database reference, set during agent initialization
_db: Database | None = None


def set_database(db: Database) -> None:
    """Set the database instance used by all tools."""
    global _db
    _db = db


def _get_db() -> Database:
    """Get the database instance, raising if not set."""
    if _db is None:
        raise RuntimeError("Database not initialized. Call set_database() first.")
    return _db


@tool
def subscribe_to_feed(url: str) -> str:
    """Subscribe to an RSS or Atom feed by URL.

    Args:
        url: The URL of the RSS or Atom feed to subscribe to.
    """
    db = _get_db()

    # Check for existing subscription first
    existing = db.get_feed_by_url(url)
    if existing:
        return json.dumps({
            "status": "error",
            "message": "Already subscribed to this feed",
        })

    # Fetch and parse the feed
    try:
        parsed = fetch_and_parse(url)
    except FeedParseError as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
        })

    # Create Feed and Item objects
    feed = Feed(
        url=url,
        title=parsed.title,
        description=parsed.description,
        site_link=parsed.site_link,
    )

    items = [
        Item(
            feed_id=0,  # Will be set by subscribe_to_feed
            guid=item_data["guid"],
            title=item_data["title"],
            link=item_data.get("link"),
            summary=item_data.get("summary"),
            published_at=item_data.get("published_at"),
        )
        for item_data in parsed.items
    ]

    # Store in database
    try:
        saved_feed, item_count = db.subscribe_to_feed(feed, items)
    except ValueError as e:
        return json.dumps({
            "status": "error",
            "message": str(e),
        })

    result = {
        "status": "subscribed",
        "feed": {
            "id": saved_feed.id,
            "title": saved_feed.title,
            "description": saved_feed.description,
            "url": saved_feed.url,
            "item_count": item_count,
        },
    }

    if parsed.warnings:
        result["warnings"] = parsed.warnings

    return json.dumps(result)


@tool
def get_items(
    feed_identifier: str = "",
    since: str = "",
    until: str = "",
    unread_only: bool = False,
    limit: int = 20,
) -> str:
    """Get feed items, optionally filtered by feed, date range, or read status.

    Args:
        feed_identifier: Optional filter by feed title or URL.
        since: Optional ISO 8601 date — only items published after this date.
        until: Optional ISO 8601 date — only items published before this date.
        unread_only: If true, only return unread items.
        limit: Maximum number of items to return (default 20).
    """
    db = _get_db()

    # Resolve feed_identifier to feed_id
    feed_id = None
    if feed_identifier:
        matches = db.find_feeds_by_identifier(feed_identifier)
        if not matches:
            return json.dumps({
                "status": "error",
                "message": f"No feed found matching '{feed_identifier}'",
            })
        if len(matches) == 1:
            feed_id = matches[0].id
        else:
            # Multiple matches — use the best one (exact URL match or first title match)
            exact = [f for f in matches if f.url == feed_identifier]
            feed_id = exact[0].id if exact else matches[0].id

    # Parse date filters
    since_dt = _parse_iso_date(since) if since else None
    until_dt = _parse_iso_date(until) if until else None

    items = db.get_recent_items(
        feed_id=feed_id,
        limit=limit,
        since=since_dt,
        until=until_dt,
        unread_only=unread_only,
    )

    total = db.get_total_item_count(
        feed_id=feed_id,
        since=since_dt,
        until=until_dt,
        unread_only=unread_only,
    )

    return json.dumps({
        "items": [
            {
                "id": item["id"],
                "feed_title": item["feed_title"],
                "title": item["title"],
                "link": item["link"],
                "summary": (item["summary"] or "")[:200],
                "published_at": item["published_at"],
                "is_read": item["is_read"],
            }
            for item in items
        ],
        "total": total,
        "has_more": total > limit,
    })


@tool
def list_feeds() -> str:
    """List all subscribed feeds with their current status.

    Returns each feed's id, title, url, status (active or erroring),
    last_fetched_at, error_count, and last_error if any.
    """
    db = _get_db()
    feeds = db.get_all_feeds()

    return json.dumps({
        "feeds": [
            {
                "id": feed.id,
                "title": feed.title,
                "url": feed.url,
                "status": "erroring" if feed.error_count > 0 else "active",
                "last_fetched_at": feed.last_fetched_at.isoformat() if feed.last_fetched_at else None,
                "error_count": feed.error_count,
                **({"last_error": feed.last_error} if feed.last_error else {}),
            }
            for feed in feeds
        ],
        "total": len(feeds),
    })


@tool
def unsubscribe_from_feed(feed_identifier: str) -> str:
    """Unsubscribe from a feed by its title or URL.

    Args:
        feed_identifier: The title or URL of the feed to unsubscribe from.
    """
    db = _get_db()

    matches = db.find_feeds_by_identifier(feed_identifier)
    if not matches:
        return json.dumps({
            "status": "error",
            "message": f"No feed found matching '{feed_identifier}'",
        })

    if len(matches) > 1:
        # Check for exact URL match first
        exact = [f for f in matches if f.url == feed_identifier]
        if len(exact) == 1:
            matches = exact
        else:
            return json.dumps({
                "status": "error",
                "message": "Multiple feeds match. Please be more specific.",
                "matches": [f.title for f in matches],
            })

    feed = matches[0]
    db.delete_feed(feed.id)

    return json.dumps({
        "status": "unsubscribed",
        "feed_title": feed.title,
    })


@tool
def search_items(query: str, limit: int = 20) -> str:
    """Search feed items by keyword across titles and summaries.

    Args:
        query: The keyword or phrase to search for.
        limit: Maximum number of results to return (default 20).
    """
    db = _get_db()

    items = db.search_items(query, limit=limit)

    return json.dumps({
        "items": [
            {
                "id": item["id"],
                "feed_title": item["feed_title"],
                "title": item["title"],
                "link": item["link"],
                "summary": (item["summary"] or "")[:200],
                "published_at": item["published_at"],
                "is_read": item["is_read"],
            }
            for item in items
        ],
        "total": len(items),
        "has_more": False,
    })


@tool
def mark_as_read(
    item_ids: list[int] | None = None,
    feed_identifier: str = "",
) -> str:
    """Mark one or more items as read, or mark all items in a feed as read.

    Args:
        item_ids: Optional list of specific item IDs to mark as read.
        feed_identifier: Optional feed title or URL — marks all items from this feed as read.
    """
    db = _get_db()

    if not item_ids and not feed_identifier:
        return json.dumps({
            "status": "error",
            "message": "Provide item_ids and/or feed_identifier",
        })

    total_marked = 0

    if feed_identifier:
        matches = db.find_feeds_by_identifier(feed_identifier)
        if not matches:
            return json.dumps({
                "status": "error",
                "message": f"No feed found matching '{feed_identifier}'",
            })
        if len(matches) > 1:
            exact = [f for f in matches if f.url == feed_identifier]
            if len(exact) == 1:
                matches = exact
            else:
                return json.dumps({
                    "status": "error",
                    "message": "Multiple feeds match. Please be more specific.",
                    "matches": [f.title for f in matches],
                })
        total_marked += db.mark_feed_items_read(matches[0].id)

    if item_ids:
        total_marked += db.mark_items_read(item_ids)

    return json.dumps({
        "status": "success",
        "items_marked": total_marked,
    })


@tool
def mark_as_unread(item_ids: list[int]) -> str:
    """Mark one or more items as unread.

    Args:
        item_ids: List of specific item IDs to mark as unread.
    """
    db = _get_db()

    marked = db.mark_items_unread(item_ids)

    return json.dumps({
        "status": "success",
        "items_marked": marked,
    })


def _parse_iso_date(date_str: str) -> datetime | None:
    """Parse an ISO 8601 date string, returning None on failure."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None
