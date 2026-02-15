"""Shared test fixtures for RSS Feed Agent tests."""

import os
import sqlite3
import tempfile
from unittest.mock import MagicMock

import pytest


SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <link>https://example.com</link>
    <description>A test RSS feed</description>
    <item>
      <title>First Article</title>
      <link>https://example.com/article-1</link>
      <guid>article-1</guid>
      <description>Description of the first article</description>
      <pubDate>Thu, 13 Feb 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Second Article</title>
      <link>https://example.com/article-2</link>
      <guid>article-2</guid>
      <description>Description of the second article</description>
      <pubDate>Thu, 13 Feb 2026 09:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""

SAMPLE_ATOM_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title>
  <link href="https://example.com"/>
  <subtitle>A test Atom feed</subtitle>
  <entry>
    <title>Atom Entry 1</title>
    <link href="https://example.com/entry-1"/>
    <id>urn:uuid:entry-1</id>
    <summary>Summary of entry 1</summary>
    <updated>2026-02-13T10:00:00Z</updated>
  </entry>
</feed>"""

SAMPLE_MALFORMED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Malformed Feed</title>
    <link>https://example.com</link>
    <item>
      <title>Good Item</title>
      <guid>good-item</guid>
    </item>
    <item>
      <title>Bad Item</title>
      <!-- Missing closing tags intentionally -->
"""

SAMPLE_NOT_A_FEED_XML = """<?xml version="1.0" encoding="UTF-8"?>
<html>
  <body>This is not a feed</body>
</html>"""


@pytest.fixture
def tmp_db_path():
    """Provide a temporary SQLite database path."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    yield path
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def sample_rss_xml():
    """Sample valid RSS 2.0 XML."""
    return SAMPLE_RSS_XML


@pytest.fixture
def sample_atom_xml():
    """Sample valid Atom XML."""
    return SAMPLE_ATOM_XML


@pytest.fixture
def sample_malformed_xml():
    """Sample malformed RSS XML."""
    return SAMPLE_MALFORMED_XML


@pytest.fixture
def sample_not_a_feed_xml():
    """Sample XML that is not a feed."""
    return SAMPLE_NOT_A_FEED_XML


@pytest.fixture
def mock_feedparser_response():
    """Create a mock feedparser response for a valid RSS feed."""
    mock = MagicMock()
    mock.bozo = False
    mock.feed.title = "Test Feed"
    mock.feed.description = "A test RSS feed"
    mock.feed.link = "https://example.com"
    mock.entries = [
        MagicMock(
            title="First Article",
            link="https://example.com/article-1",
            id="article-1",
            summary="Description of the first article",
            published_parsed=(2026, 2, 13, 10, 0, 0, 3, 44, 0),
        ),
        MagicMock(
            title="Second Article",
            link="https://example.com/article-2",
            id="article-2",
            summary="Description of the second article",
            published_parsed=(2026, 2, 13, 9, 0, 0, 3, 44, 0),
        ),
    ]
    return mock
