"""RSS/Atom feed parsing using feedparser."""

from dataclasses import dataclass
from datetime import datetime
from time import mktime, struct_time
from urllib.parse import urlparse

import feedparser


MAX_INITIAL_ITEMS = 50


@dataclass
class ParsedFeed:
    """Result of parsing an RSS/Atom feed."""

    title: str
    description: str | None
    site_link: str | None
    items: list[dict]
    warnings: list[str]


class FeedParseError(Exception):
    """Raised when a feed cannot be parsed."""


def fetch_and_parse(url: str) -> ParsedFeed:
    """Fetch and parse an RSS or Atom feed from a URL.

    Args:
        url: The feed URL to fetch and parse.

    Returns:
        ParsedFeed with feed metadata and items.

    Raises:
        FeedParseError: If the URL is invalid, unreachable, or not a valid feed.
    """
    _validate_url(url)

    parsed = feedparser.parse(url)

    if parsed.get("status", 200) in (401, 403):
        raise FeedParseError(
            "Feed requires authentication. Ensure the URL is publicly accessible."
        )

    if parsed.get("status", 200) >= 400:
        raise FeedParseError(
            f"Could not reach URL: HTTP {parsed.get('status', 'unknown')}"
        )

    if not parsed.feed.get("title"):
        if parsed.bozo and parsed.bozo_exception:
            raise FeedParseError(
                "URL does not point to a valid RSS or Atom feed"
            )
        raise FeedParseError(
            "URL does not point to a valid RSS or Atom feed"
        )

    warnings: list[str] = []
    if parsed.bozo:
        warnings.append(
            f"Feed has formatting issues: {parsed.bozo_exception}"
        )

    items = _extract_items(parsed.entries, warnings)

    return ParsedFeed(
        title=parsed.feed.get("title", "Untitled Feed"),
        description=parsed.feed.get("description") or parsed.feed.get("subtitle"),
        site_link=parsed.feed.get("link"),
        items=items[:MAX_INITIAL_ITEMS],
        warnings=warnings,
    )


def _validate_url(url: str) -> None:
    """Validate that the URL has a valid format."""
    try:
        result = urlparse(url)
        if not result.scheme or not result.netloc:
            raise FeedParseError("Invalid URL format")
        if result.scheme not in ("http", "https"):
            raise FeedParseError("Invalid URL format: only http and https are supported")
    except ValueError:
        raise FeedParseError("Invalid URL format")


def _extract_items(entries: list, warnings: list[str]) -> list[dict]:
    """Extract normalized item dicts from feedparser entries."""
    items = []
    for entry in entries:
        try:
            guid = (
                entry.get("id")
                or entry.get("guid")
                or entry.get("link")
            )
            if not guid:
                warnings.append(
                    f"Skipping entry with no identifier: {entry.get('title', 'unknown')}"
                )
                continue

            title = entry.get("title", "Untitled")
            link = entry.get("link")
            summary = entry.get("summary") or entry.get("description")
            published_at = _parse_date(entry)

            items.append({
                "guid": guid,
                "title": title,
                "link": link,
                "summary": summary,
                "published_at": published_at,
            })
        except Exception as e:
            warnings.append(f"Skipping malformed entry: {e}")
            continue

    # Sort by published date descending (newest first)
    items.sort(
        key=lambda x: x["published_at"] or datetime.min,
        reverse=True,
    )
    return items


def _parse_date(entry: dict) -> datetime | None:
    """Parse publication date from a feedparser entry."""
    for field in ("published_parsed", "updated_parsed"):
        time_struct = entry.get(field)
        if isinstance(time_struct, struct_time):
            try:
                return datetime.fromtimestamp(mktime(time_struct))
            except (ValueError, OverflowError):
                continue
    return None
