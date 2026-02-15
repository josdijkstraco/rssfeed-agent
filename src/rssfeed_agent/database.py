"""SQLite database operations for RSS Feed Agent."""

import sqlite3
from datetime import datetime

from rssfeed_agent.models import Feed, Item

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS feeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    site_link TEXT,
    last_fetched_at TEXT,
    error_count INTEGER DEFAULT 0,
    last_error TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id INTEGER NOT NULL REFERENCES feeds(id) ON DELETE CASCADE,
    guid TEXT NOT NULL,
    title TEXT NOT NULL,
    link TEXT,
    summary TEXT,
    published_at TEXT,
    is_read INTEGER DEFAULT 0,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(feed_id, guid)
);

CREATE INDEX IF NOT EXISTS idx_items_feed_id ON items(feed_id);
CREATE INDEX IF NOT EXISTS idx_items_published_at ON items(published_at);
CREATE INDEX IF NOT EXISTS idx_items_is_read ON items(is_read);

CREATE VIRTUAL TABLE IF NOT EXISTS items_fts USING fts5(
    title,
    summary,
    content='items',
    content_rowid='id'
);

CREATE TRIGGER IF NOT EXISTS items_ai AFTER INSERT ON items BEGIN
    INSERT INTO items_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TRIGGER IF NOT EXISTS items_ad AFTER DELETE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary) VALUES ('delete', old.id, old.title, old.summary);
END;

CREATE TRIGGER IF NOT EXISTS items_au AFTER UPDATE ON items BEGIN
    INSERT INTO items_fts(items_fts, rowid, title, summary) VALUES ('delete', old.id, old.title, old.summary);
    INSERT INTO items_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;
"""


class Database:
    """SQLite database manager for feeds and items."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def connect(self) -> None:
        """Open database connection and initialize schema."""
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA_SQL)
        self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    # --- Feed operations ---

    def add_feed(self, feed: Feed) -> Feed:
        """Insert a new feed and return it with its assigned id."""
        cursor = self.conn.execute(
            """INSERT INTO feeds (url, title, description, site_link, last_fetched_at,
               error_count, last_error, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                feed.url,
                feed.title,
                feed.description,
                feed.site_link,
                _dt_to_str(feed.last_fetched_at),
                feed.error_count,
                feed.last_error,
                int(feed.is_active),
                _dt_to_str(feed.created_at),
            ),
        )
        self.conn.commit()
        feed.id = cursor.lastrowid
        return feed

    def get_feed_by_url(self, url: str) -> Feed | None:
        """Look up a feed by its URL."""
        row = self.conn.execute(
            "SELECT * FROM feeds WHERE url = ?", (url,)
        ).fetchone()
        return _row_to_feed(row) if row else None

    def get_feed_by_id(self, feed_id: int) -> Feed | None:
        """Look up a feed by its id."""
        row = self.conn.execute(
            "SELECT * FROM feeds WHERE id = ?", (feed_id,)
        ).fetchone()
        return _row_to_feed(row) if row else None

    def get_all_feeds(self) -> list[Feed]:
        """Return all feeds."""
        rows = self.conn.execute(
            "SELECT * FROM feeds ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_feed(r) for r in rows]

    def delete_feed(self, feed_id: int) -> bool:
        """Delete a feed and its items (cascade). Returns True if deleted."""
        cursor = self.conn.execute("DELETE FROM feeds WHERE id = ?", (feed_id,))
        self.conn.commit()
        return cursor.rowcount > 0

    def subscribe_to_feed(
        self, feed: Feed, items: list[Item]
    ) -> tuple[Feed, int]:
        """Subscribe to a feed: check for duplicates, insert feed and items.

        Args:
            feed: Feed to subscribe to.
            items: Initial items to import.

        Returns:
            Tuple of (saved Feed with id, count of imported items).

        Raises:
            ValueError: If already subscribed to this URL.
        """
        existing = self.get_feed_by_url(feed.url)
        if existing:
            raise ValueError(f"Already subscribed to this feed")

        saved_feed = self.add_feed(feed)

        # Set feed_id on all items
        for item in items:
            item.feed_id = saved_feed.id

        item_count = self.add_items(items)
        return saved_feed, item_count

    def get_item_count_for_feed(self, feed_id: int) -> int:
        """Get the number of items stored for a feed."""
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE feed_id = ?", (feed_id,)
        ).fetchone()
        return row["cnt"] if row else 0

    # --- Item operations ---

    def add_items(self, items: list[Item]) -> int:
        """Bulk-insert items, skipping duplicates. Returns count of inserted items."""
        inserted = 0
        for item in items:
            try:
                self.conn.execute(
                    """INSERT INTO items (feed_id, guid, title, link, summary,
                       published_at, is_read, fetched_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        item.feed_id,
                        item.guid,
                        item.title,
                        item.link,
                        item.summary,
                        _dt_to_str(item.published_at),
                        int(item.is_read),
                        _dt_to_str(item.fetched_at),
                    ),
                )
                inserted += 1
            except sqlite3.IntegrityError:
                # Duplicate (feed_id, guid) — skip
                continue
        self.conn.commit()
        return inserted

    def get_items_by_feed_id(self, feed_id: int, limit: int = 50) -> list[Item]:
        """Get items for a specific feed, ordered by publication date."""
        rows = self.conn.execute(
            """SELECT * FROM items WHERE feed_id = ?
               ORDER BY published_at DESC LIMIT ?""",
            (feed_id, limit),
        ).fetchall()
        return [_row_to_item(r) for r in rows]

    def get_recent_items(
        self,
        feed_id: int | None = None,
        limit: int = 20,
        since: datetime | None = None,
        until: datetime | None = None,
        unread_only: bool = False,
    ) -> list[dict]:
        """Get recent items with feed title, optionally filtered.

        Returns dicts (not Item objects) to include feed_title from join.
        """
        query = """
            SELECT items.*, feeds.title as feed_title
            FROM items
            JOIN feeds ON items.feed_id = feeds.id
            WHERE 1=1
        """
        params: list = []

        if feed_id is not None:
            query += " AND items.feed_id = ?"
            params.append(feed_id)
        if since is not None:
            query += " AND items.published_at >= ?"
            params.append(_dt_to_str(since))
        if until is not None:
            query += " AND items.published_at <= ?"
            params.append(_dt_to_str(until))
        if unread_only:
            query += " AND items.is_read = 0"

        query += " ORDER BY items.published_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(query, params).fetchall()
        return [
            {
                "id": r["id"],
                "feed_id": r["feed_id"],
                "feed_title": r["feed_title"],
                "guid": r["guid"],
                "title": r["title"],
                "link": r["link"],
                "summary": r["summary"],
                "published_at": r["published_at"],
                "is_read": bool(r["is_read"]),
                "fetched_at": r["fetched_at"],
            }
            for r in rows
        ]

    def get_total_item_count(
        self,
        feed_id: int | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        unread_only: bool = False,
    ) -> int:
        """Get count of items matching filters (for has_more calculation)."""
        query = "SELECT COUNT(*) as cnt FROM items WHERE 1=1"
        params: list = []

        if feed_id is not None:
            query += " AND feed_id = ?"
            params.append(feed_id)
        if since is not None:
            query += " AND published_at >= ?"
            params.append(_dt_to_str(since))
        if until is not None:
            query += " AND published_at <= ?"
            params.append(_dt_to_str(until))
        if unread_only:
            query += " AND is_read = 0"

        row = self.conn.execute(query, params).fetchone()
        return row["cnt"] if row else 0

    def get_new_items_count_since(self, timestamp: datetime) -> int:
        """Count items fetched since the given timestamp (for hybrid notification)."""
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM items WHERE fetched_at >= ?",
            (_dt_to_str(timestamp),),
        ).fetchone()
        return row["cnt"] if row else 0

    def update_feed_last_fetched(self, feed_id: int, timestamp: datetime) -> None:
        """Update a feed's last_fetched_at timestamp."""
        self.conn.execute(
            "UPDATE feeds SET last_fetched_at = ? WHERE id = ?",
            (_dt_to_str(timestamp), feed_id),
        )
        self.conn.commit()

    def update_feed_error(
        self, feed_id: int, error_message: str
    ) -> None:
        """Increment error count and store error message for a feed."""
        self.conn.execute(
            """UPDATE feeds SET error_count = error_count + 1, last_error = ?
               WHERE id = ?""",
            (error_message, feed_id),
        )
        self.conn.commit()

    def reset_feed_error(self, feed_id: int) -> None:
        """Reset error count and clear error message on successful fetch."""
        self.conn.execute(
            "UPDATE feeds SET error_count = 0, last_error = NULL WHERE id = ?",
            (feed_id,),
        )
        self.conn.commit()

    def get_active_feeds(self) -> list[Feed]:
        """Return all active feeds (for polling)."""
        rows = self.conn.execute(
            "SELECT * FROM feeds WHERE is_active = 1 ORDER BY id"
        ).fetchall()
        return [_row_to_feed(r) for r in rows]

    def find_feeds_by_identifier(self, identifier: str) -> list[Feed]:
        """Find feeds by title (case-insensitive substring) or URL."""
        rows = self.conn.execute(
            """SELECT * FROM feeds
               WHERE url = ? OR title LIKE ? COLLATE NOCASE""",
            (identifier, f"%{identifier}%"),
        ).fetchall()
        return [_row_to_feed(r) for r in rows]

    def item_exists_by_guid(self, feed_id: int, guid: str) -> bool:
        """Check if an item with the given guid exists for a feed."""
        row = self.conn.execute(
            "SELECT 1 FROM items WHERE feed_id = ? AND guid = ?",
            (feed_id, guid),
        ).fetchone()
        return row is not None

    def search_items(self, query: str, limit: int = 20) -> list[dict]:
        """Full-text search across item titles and summaries using FTS5.

        Returns dicts with feed_title, ranked by relevance.
        """
        rows = self.conn.execute(
            """SELECT items.*, feeds.title as feed_title,
                      items_fts.rank
               FROM items_fts
               JOIN items ON items.id = items_fts.rowid
               JOIN feeds ON items.feed_id = feeds.id
               WHERE items_fts MATCH ?
               ORDER BY items_fts.rank
               LIMIT ?""",
            (query, limit),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "feed_id": r["feed_id"],
                "feed_title": r["feed_title"],
                "guid": r["guid"],
                "title": r["title"],
                "link": r["link"],
                "summary": r["summary"],
                "published_at": r["published_at"],
                "is_read": bool(r["is_read"]),
                "fetched_at": r["fetched_at"],
            }
            for r in rows
        ]

    def mark_items_read(self, item_ids: list[int]) -> int:
        """Mark specific items as read. Returns count of affected rows."""
        if not item_ids:
            return 0
        placeholders = ",".join("?" for _ in item_ids)
        cursor = self.conn.execute(
            f"UPDATE items SET is_read = 1 WHERE id IN ({placeholders}) AND is_read = 0",
            item_ids,
        )
        self.conn.commit()
        return cursor.rowcount

    def mark_feed_items_read(self, feed_id: int) -> int:
        """Mark all items in a feed as read. Returns count of affected rows."""
        cursor = self.conn.execute(
            "UPDATE items SET is_read = 1 WHERE feed_id = ? AND is_read = 0",
            (feed_id,),
        )
        self.conn.commit()
        return cursor.rowcount

    def mark_items_unread(self, item_ids: list[int]) -> int:
        """Mark specific items as unread. Returns count of affected rows."""
        if not item_ids:
            return 0
        placeholders = ",".join("?" for _ in item_ids)
        cursor = self.conn.execute(
            f"UPDATE items SET is_read = 0 WHERE id IN ({placeholders}) AND is_read = 1",
            item_ids,
        )
        self.conn.commit()
        return cursor.rowcount


# --- Helper functions ---


def _dt_to_str(dt: datetime | None) -> str | None:
    """Convert datetime to ISO string for storage."""
    return dt.isoformat() if dt else None


def _str_to_dt(s: str | None) -> datetime | None:
    """Convert stored ISO string back to datetime."""
    if not s:
        return None
    return datetime.fromisoformat(s)


def _row_to_feed(row: sqlite3.Row) -> Feed:
    """Convert a database row to a Feed dataclass."""
    return Feed(
        id=row["id"],
        url=row["url"],
        title=row["title"],
        description=row["description"],
        site_link=row["site_link"],
        last_fetched_at=_str_to_dt(row["last_fetched_at"]),
        error_count=row["error_count"],
        last_error=row["last_error"],
        is_active=bool(row["is_active"]),
        created_at=_str_to_dt(row["created_at"]) or datetime.utcnow(),
    )


def _row_to_item(row: sqlite3.Row) -> Item:
    """Convert a database row to an Item dataclass."""
    return Item(
        id=row["id"],
        feed_id=row["feed_id"],
        guid=row["guid"],
        title=row["title"],
        link=row["link"],
        summary=row["summary"],
        published_at=_str_to_dt(row["published_at"]),
        is_read=bool(row["is_read"]),
        fetched_at=_str_to_dt(row["fetched_at"]) or datetime.utcnow(),
    )
