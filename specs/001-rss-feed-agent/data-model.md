# Data Model: RSS Feed Agent

**Date**: 2026-02-13
**Feature**: 001-rss-feed-agent

## Entities

### Feed

Represents a subscribed RSS/Atom source.

| Field            | Type     | Constraints                          | Description                                   |
|------------------|----------|--------------------------------------|-----------------------------------------------|
| id               | integer  | Primary key, auto-increment          | Unique identifier                             |
| url              | text     | Unique, not null                     | Feed URL                                      |
| title            | text     | Not null                             | Feed title from source                        |
| description      | text     | Nullable                             | Feed description from source                  |
| site_link        | text     | Nullable                             | Website URL associated with feed              |
| last_fetched_at  | datetime | Nullable                             | Timestamp of last successful fetch            |
| error_count      | integer  | Default 0                            | Consecutive fetch failure count               |
| last_error       | text     | Nullable                             | Most recent error message                     |
| is_active        | boolean  | Default true                         | Whether the feed is actively being polled     |
| created_at       | datetime | Not null, default current timestamp  | When the subscription was created             |

**Uniqueness**: `url` (prevents duplicate subscriptions per FR-002, User Story 1 scenario 3)

**State transitions**:
- `is_active=true, error_count=0` → Active (normal polling)
- `is_active=true, error_count>0` → Erroring (still polling, user warned)
- `is_active=false` → Inactive (unsubscribed, no longer polled)

### Item

Represents a single entry from a feed.

| Field           | Type     | Constraints                                  | Description                               |
|-----------------|----------|----------------------------------------------|-------------------------------------------|
| id              | integer  | Primary key, auto-increment                  | Unique identifier                         |
| feed_id         | integer  | Foreign key → Feed.id, not null              | Parent feed                               |
| guid            | text     | Not null                                     | Item unique identifier from feed          |
| title           | text     | Not null                                     | Item title                                |
| link            | text     | Nullable                                     | Item URL                                  |
| summary         | text     | Nullable                                     | Item description/summary                  |
| published_at    | datetime | Nullable                                     | Publication date from feed                |
| is_read         | boolean  | Default false                                | Whether user has marked as read           |
| fetched_at      | datetime | Not null, default current timestamp          | When the item was first fetched           |

**Uniqueness**: `(feed_id, guid)` composite unique — prevents duplicate items within a feed (FR-005, SC-005)

**Relationships**:
- Many Items belong to one Feed
- When a Feed is deleted (unsubscribed), all its Items are cascade-deleted

### AgentState (LangGraph-managed)

LangGraph manages agent conversation state via its checkpoint system. This is not a user-defined table but is persisted by `SqliteSaver`.

| Concept        | Description                                                    |
|----------------|----------------------------------------------------------------|
| thread_id      | Identifies a conversation thread (single user = single thread) |
| checkpoint     | Serialized graph state at each step                            |
| messages       | Conversation history (user + assistant messages)               |

## Indexes

- `idx_items_feed_id` on `Item.feed_id` — fast lookup of items by feed
- `idx_items_published_at` on `Item.published_at` — efficient date range filtering (FR-011)
- `idx_items_is_read` on `Item.is_read` — fast unread filtering
- `idx_items_guid` on `Item(feed_id, guid)` — enforced by unique constraint, used for dedup checks

## Search

Keyword search (FR-010) uses SQLite FTS5 (Full-Text Search) on `Item.title` and `Item.summary` for efficient text matching. This avoids `LIKE '%keyword%'` scans and supports SC-004 (search in under 5 seconds).
