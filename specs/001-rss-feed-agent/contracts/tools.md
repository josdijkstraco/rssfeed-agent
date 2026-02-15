# Agent Tool Contracts: RSS Feed Agent

**Date**: 2026-02-13
**Feature**: 001-rss-feed-agent

In a LangGraph chat agent, the "API surface" is the set of tools the LLM can invoke. The LLM receives user natural language, decides which tool to call (if any), and formats tool results back into a conversational response.

## Tools

### subscribe_to_feed

**Maps to**: FR-001, FR-002, FR-013, User Story 1

**Description**: Subscribe to an RSS or Atom feed by URL.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "url": {
      "type": "string",
      "description": "The URL of the RSS or Atom feed to subscribe to"
    }
  },
  "required": ["url"]
}
```

**Output**: JSON object with feed metadata on success, or error message on failure.
```json
{
  "status": "subscribed",
  "feed": {
    "id": 1,
    "title": "TechCrunch",
    "description": "Startup and Technology News",
    "url": "https://techcrunch.com/feed/",
    "item_count": 50
  }
}
```

**Error cases**:
- Invalid URL format → `{"status": "error", "message": "Invalid URL format"}`
- URL not a valid feed → `{"status": "error", "message": "URL does not point to a valid RSS or Atom feed"}`
- URL unreachable → `{"status": "error", "message": "Could not reach URL: <detail>"}`
- Already subscribed → `{"status": "error", "message": "Already subscribed to this feed"}`

---

### unsubscribe_from_feed

**Maps to**: FR-008, User Story 3

**Description**: Unsubscribe from a feed by its title or URL.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "feed_identifier": {
      "type": "string",
      "description": "The title or URL of the feed to unsubscribe from"
    }
  },
  "required": ["feed_identifier"]
}
```

**Output**:
```json
{
  "status": "unsubscribed",
  "feed_title": "TechCrunch"
}
```

**Error cases**:
- Feed not found → `{"status": "error", "message": "No feed found matching '<identifier>'"}`
- Ambiguous match → `{"status": "error", "message": "Multiple feeds match. Please be more specific.", "matches": ["Feed A", "Feed B"]}`

---

### list_feeds

**Maps to**: FR-007, FR-009, User Story 3

**Description**: List all subscribed feeds with their current status.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {},
  "required": []
}
```

**Output**:
```json
{
  "feeds": [
    {
      "id": 1,
      "title": "TechCrunch",
      "url": "https://techcrunch.com/feed/",
      "status": "active",
      "last_fetched_at": "2026-02-13T10:30:00Z",
      "error_count": 0
    },
    {
      "id": 2,
      "title": "Hacker News",
      "url": "https://news.ycombinator.com/rss",
      "status": "erroring",
      "last_fetched_at": "2026-02-12T08:00:00Z",
      "error_count": 3,
      "last_error": "Connection timed out"
    }
  ],
  "total": 2
}
```

---

### get_items

**Maps to**: FR-006, FR-011, User Story 2

**Description**: Get feed items, optionally filtered by feed, date range, or read status.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "feed_identifier": {
      "type": "string",
      "description": "Optional: filter by feed title or URL"
    },
    "since": {
      "type": "string",
      "description": "Optional: only items published after this date (ISO 8601)"
    },
    "until": {
      "type": "string",
      "description": "Optional: only items published before this date (ISO 8601)"
    },
    "unread_only": {
      "type": "boolean",
      "description": "Optional: only return unread items (default: false)"
    },
    "limit": {
      "type": "integer",
      "description": "Optional: maximum number of items to return (default: 20)"
    }
  },
  "required": []
}
```

**Output**:
```json
{
  "items": [
    {
      "id": 42,
      "feed_title": "TechCrunch",
      "title": "New AI Startup Raises $10M",
      "link": "https://techcrunch.com/2026/02/13/...",
      "summary": "A new AI startup focused on...",
      "published_at": "2026-02-13T09:00:00Z",
      "is_read": false
    }
  ],
  "total": 1,
  "has_more": false
}
```

---

### search_items

**Maps to**: FR-010, User Story 4

**Description**: Search feed items by keyword across titles and summaries.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "description": "The keyword or phrase to search for"
    },
    "limit": {
      "type": "integer",
      "description": "Optional: maximum number of results (default: 20)"
    }
  },
  "required": ["query"]
}
```

**Output**: Same structure as `get_items` output.

---

### mark_as_read

**Maps to**: FR-012, User Story 5

**Description**: Mark one or more items as read, or mark all items in a feed as read.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "item_ids": {
      "type": "array",
      "items": {"type": "integer"},
      "description": "Optional: specific item IDs to mark as read"
    },
    "feed_identifier": {
      "type": "string",
      "description": "Optional: mark all items from this feed as read"
    }
  },
  "required": []
}
```

**Output**:
```json
{
  "status": "success",
  "items_marked": 15
}
```

**Constraint**: At least one of `item_ids` or `feed_identifier` must be provided.

---

### mark_as_unread

**Maps to**: FR-012, User Story 5

**Description**: Mark one or more items as unread.

**Input Schema**:
```json
{
  "type": "object",
  "properties": {
    "item_ids": {
      "type": "array",
      "items": {"type": "integer"},
      "description": "Specific item IDs to mark as unread"
    }
  },
  "required": ["item_ids"]
}
```

**Output**:
```json
{
  "status": "success",
  "items_marked": 3
}
```

## LangGraph Graph Structure

```
User Input
    │
    ▼
┌──────────┐
│  START    │
└────┬─────┘
     │
     ▼
┌──────────────┐     tool_calls?     ┌──────────────┐
│  agent_node  │────── yes ─────────▶│  tool_node   │
│  (LLM call)  │                     │  (execute)   │
└──────┬───────┘                     └──────┬───────┘
       │                                     │
       │ no tool_calls                       │
       ▼                                     │
┌──────────┐                                 │
│   END    │◀────────────────────────────────┘
└──────────┘
```

The LLM decides which tool to call (if any) based on the user's natural language input. Tool results are fed back to the LLM for final response formatting.
