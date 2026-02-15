"""Background polling loop for RSS Feed Agent."""

import asyncio
import logging
import os
from datetime import datetime

from rssfeed_agent.database import Database
from rssfeed_agent.feed_parser import FeedParseError, fetch_and_parse
from rssfeed_agent.models import Item

logger = logging.getLogger(__name__)

DEFAULT_POLL_INTERVAL = 900  # 15 minutes


async def poll_feeds_once(db: Database) -> int:
    """Poll all active feeds once. Returns count of new items found."""
    feeds = db.get_active_feeds()
    total_new = 0

    for feed in feeds:
        try:
            parsed = await asyncio.to_thread(fetch_and_parse, feed.url)

            # Build items, filtering out ones we already have
            new_items = []
            for item_data in parsed.items:
                if not db.item_exists_by_guid(feed.id, item_data["guid"]):
                    new_items.append(
                        Item(
                            feed_id=feed.id,
                            guid=item_data["guid"],
                            title=item_data["title"],
                            link=item_data.get("link"),
                            summary=item_data.get("summary"),
                            published_at=item_data.get("published_at"),
                        )
                    )

            if new_items:
                inserted = db.add_items(new_items)
                total_new += inserted
                logger.info(
                    "Feed '%s': %d new items", feed.title, inserted
                )

            # Update last fetched and reset errors on success
            db.update_feed_last_fetched(feed.id, datetime.utcnow())
            db.reset_feed_error(feed.id)

        except FeedParseError as e:
            logger.warning("Feed '%s' error: %s", feed.title, e)
            db.update_feed_error(feed.id, str(e))
        except Exception as e:
            logger.warning("Feed '%s' unexpected error: %s", feed.title, e)
            db.update_feed_error(feed.id, str(e))

    return total_new


async def start_polling(db: Database) -> None:
    """Run the polling loop indefinitely."""
    interval = int(os.environ.get("RSS_POLL_INTERVAL", DEFAULT_POLL_INTERVAL))
    logger.info("Poller started (interval: %ds)", interval)

    while True:
        try:
            new_count = await poll_feeds_once(db)
            if new_count > 0:
                logger.info("Poll cycle complete: %d new items", new_count)
        except Exception as e:
            logger.error("Poll cycle failed: %s", e)

        await asyncio.sleep(interval)
