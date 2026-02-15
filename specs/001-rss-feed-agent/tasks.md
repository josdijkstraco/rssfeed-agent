# Tasks: RSS Feed Agent

**Input**: Design documents from `/specs/001-rss-feed-agent/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested. Test tasks are excluded.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization, dependencies, and directory structure

- [x] T001 Create project directory structure: `src/rssfeed_agent/`, `tests/unit/`, `tests/integration/` per plan.md
- [x] T002 Create `pyproject.toml` with project metadata, dependencies (langgraph, langchain-anthropic, langchain-core, feedparser, aiosqlite), and dev dependencies (pytest, pytest-asyncio, pytest-cov)
- [x] T003 Create `src/rssfeed_agent/__init__.py` with package version
- [x] T004 [P] Create `tests/conftest.py` with shared fixtures: temporary SQLite database, sample RSS feed XML strings, mock feedparser responses
- [x] T005 [P] Create `.env.example` documenting required environment variables (ANTHROPIC_API_KEY, RSS_POLL_INTERVAL)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core data layer and feed parsing that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T006 Implement Feed and Item dataclasses in `src/rssfeed_agent/models.py` — Feed fields: id, url, title, description, site_link, last_fetched_at, error_count, last_error, is_active, created_at; Item fields: id, feed_id, guid, title, link, summary, published_at, is_read, fetched_at (per data-model.md)
- [x] T007 Implement database module in `src/rssfeed_agent/database.py` — SQLite schema initialization (feeds table, items table, FTS5 virtual table for search, indexes per data-model.md), connection management, and base CRUD operations: `add_feed`, `get_feed_by_url`, `get_feed_by_id`, `get_all_feeds`, `delete_feed`, `add_items`, `get_items_by_feed_id`, `item_exists_by_guid`
- [x] T008 Implement feed parser module in `src/rssfeed_agent/feed_parser.py` — `fetch_and_parse(url)` function using feedparser: validate URL format, fetch feed, detect RSS 2.0 vs Atom, extract feed metadata (title, description, site_link), extract items (guid, title, link, summary, published_at), handle malformed XML gracefully (FR-014), limit to 50 most recent items on initial fetch (FR-013)
- [x] T009 Implement LangGraph agent skeleton in `src/rssfeed_agent/agent.py` — Define `AgentState(TypedDict)` with messages field, create `StateGraph(AgentState)`, add `agent_node` (ChatAnthropic LLM call with system prompt), add `tool_node` (tool execution), add conditional edge `should_continue` routing on tool_calls presence, compile graph with `SqliteSaver` checkpointer

**Checkpoint**: Foundation ready — data layer, feed parsing, and agent skeleton operational

---

## Phase 3: User Story 1 — Subscribe to an RSS Feed (Priority: P1) MVP

**Goal**: User can provide an RSS feed URL via chat; agent validates, fetches, stores the subscription, imports initial items, and confirms with feed metadata.

**Independent Test**: Provide a valid RSS/Atom feed URL → agent confirms subscription with title, description, item count. Provide invalid URL → agent returns clear error. Provide duplicate URL → agent reports already subscribed.

### Implementation for User Story 1

- [x] T010 [US1] Add `subscribe_to_feed` database operations in `src/rssfeed_agent/database.py` — check for existing subscription by URL (duplicate detection), insert new feed record, bulk-insert initial items with dedup by (feed_id, guid), return feed with item count
- [x] T011 [US1] Implement `subscribe_to_feed` tool function in `src/rssfeed_agent/tools.py` — accepts `url: str`, calls `feed_parser.fetch_and_parse(url)` for validation and parsing, calls database to store feed + items, returns JSON with status, feed title, description, url, and item_count per contracts/tools.md; handles all 4 error cases (invalid URL, not a feed, unreachable, already subscribed)
- [x] T012 [US1] Register `subscribe_to_feed` tool in `src/rssfeed_agent/agent.py` — bind tool to ChatAnthropic model via `.bind_tools()`, add to tools_by_name dict in tool_node, add system prompt instructing the agent about feed subscription capabilities
- [x] T013 [US1] Implement `__main__.py` entry point in `src/rssfeed_agent/__main__.py` — async main loop: initialize database, create agent graph with SqliteSaver, run interactive chat loop reading from stdin, invoke graph with user messages, print agent responses to stdout, handle KeyboardInterrupt for graceful shutdown

**Checkpoint**: User Story 1 fully functional — user can subscribe to feeds via natural language chat. This is the MVP.

---

## Phase 4: User Story 2 — Fetch and Display New Feed Items (Priority: P1)

**Goal**: Agent periodically polls subscribed feeds for new items in the background. User can ask for latest items and see them formatted with title, link, date, and summary. Hybrid notification: new item count shown on next user interaction.

**Independent Test**: Subscribe to a feed, trigger a poll cycle, ask "what's new?" → agent displays new items with title, link, date, summary. Poll again with no new items → no duplicates created.

### Implementation for User Story 2

- [x] T014 [US2] Add item retrieval database operations in `src/rssfeed_agent/database.py` — `get_recent_items(feed_id=None, limit=20)` returning items ordered by published_at desc, `get_new_items_count_since(timestamp)` for hybrid notification, `update_feed_last_fetched(feed_id, timestamp)` to track poll state
- [x] T015 [US2] Implement background poller in `src/rssfeed_agent/poller.py` — async polling loop using `asyncio.create_task`: fetch all active feeds at configurable interval (default 15 min via RSS_POLL_INTERVAL env var), for each feed call `feed_parser.fetch_and_parse`, dedup new items via `item_exists_by_guid`, store new items, update feed last_fetched_at, handle fetch errors by incrementing error_count and storing last_error (FR-009), reset error_count on successful fetch
- [x] T016 [US2] Implement `get_items` tool function in `src/rssfeed_agent/tools.py` — accepts optional `feed_identifier`, `since`, `until`, `unread_only`, `limit` parameters per contracts/tools.md; queries database with filters; returns items with feed_title, title, link, summary, published_at, is_read
- [x] T017 [US2] Register `get_items` tool and integrate poller in `src/rssfeed_agent/agent.py` — bind get_items tool to model, update system prompt with item retrieval capabilities, add hybrid notification logic: on each user message check `get_new_items_count_since(last_interaction_time)` and prepend count to context if > 0
- [x] T018 [US2] Start poller as background task in `src/rssfeed_agent/__main__.py` — launch `poller.start_polling(db)` via `asyncio.create_task` alongside the chat loop, ensure graceful shutdown cancels the poller task

**Checkpoint**: Core loop complete — subscribe + poll + display. User can subscribe and see new items arrive over time.

---

## Phase 5: User Story 3 — List and Manage Subscriptions (Priority: P2)

**Goal**: User can list all subscribed feeds with status info (active/erroring, last checked, error details) and unsubscribe from feeds.

**Independent Test**: Subscribe to multiple feeds, ask "show my feeds" → all listed with status. Say "unsubscribe from TechCrunch" → feed removed, no longer polled.

### Implementation for User Story 3

- [x] T019 [US3] Implement `list_feeds` tool function in `src/rssfeed_agent/tools.py` — calls `database.get_all_feeds()`, formats each feed with id, title, url, computed status (active if error_count=0, erroring if error_count>0), last_fetched_at, error_count, last_error; returns JSON per contracts/tools.md
- [x] T020 [US3] Implement `unsubscribe_from_feed` tool function in `src/rssfeed_agent/tools.py` — accepts `feed_identifier: str`, resolves feed by title (case-insensitive partial match) or URL, handles ambiguous matches (multiple results), calls `database.delete_feed(feed_id)` with cascade delete of items, returns confirmation or error per contracts/tools.md
- [x] T021 [US3] Add feed deletion with cascade in `src/rssfeed_agent/database.py` — `delete_feed(feed_id)` removes feed and all associated items, `find_feeds_by_identifier(identifier)` for flexible lookup by title substring or URL
- [x] T022 [US3] Register `list_feeds` and `unsubscribe_from_feed` tools in `src/rssfeed_agent/agent.py` — bind both tools to model, update system prompt with subscription management capabilities

**Checkpoint**: Full subscription lifecycle — subscribe, monitor, unsubscribe. All P1+P2 stories complete.

---

## Phase 6: User Story 4 — Filter and Search Feed Items (Priority: P3)

**Goal**: User can search items by keyword (FTS5) and filter by feed, date range, or read/unread status.

**Independent Test**: With items from multiple feeds, ask "search for python" → only matching items returned. Ask "show items from last week" → date-filtered results.

### Implementation for User Story 4

- [x] T023 [US4] Add FTS5 search operations in `src/rssfeed_agent/database.py` — `search_items(query, limit=20)` using FTS5 MATCH on items_fts virtual table, join with feeds table for feed_title, return ranked results; ensure FTS5 table is kept in sync via triggers on items insert/delete
- [x] T024 [US4] Add filtered item retrieval in `src/rssfeed_agent/database.py` — extend `get_recent_items` to support combined filters: `feed_id`, `since` datetime, `until` datetime, `unread_only` boolean, applied as SQL WHERE clauses
- [x] T025 [US4] Implement `search_items` tool function in `src/rssfeed_agent/tools.py` — accepts `query: str` and optional `limit: int` per contracts/tools.md, calls `database.search_items`, returns items in same format as get_items
- [x] T026 [US4] Register `search_items` tool in `src/rssfeed_agent/agent.py` — bind tool to model, update system prompt with search and filter capabilities

**Checkpoint**: User can find specific content across all feeds via keyword or filters.

---

## Phase 7: User Story 5 — Mark Items as Read/Unread (Priority: P3)

**Goal**: User can mark individual items or all items from a feed as read/unread to track consumed content.

**Independent Test**: Ask "mark item 42 as read" → item flagged. Ask "mark all TechCrunch items as read" → bulk update. Filter for unread → read items excluded.

### Implementation for User Story 5

- [x] T027 [US5] Add read-state operations in `src/rssfeed_agent/database.py` — `mark_items_read(item_ids: list[int])`, `mark_feed_items_read(feed_id: int)`, `mark_items_unread(item_ids: list[int])`, each returning count of affected rows
- [x] T028 [US5] Implement `mark_as_read` tool function in `src/rssfeed_agent/tools.py` — accepts optional `item_ids: list[int]` and/or `feed_identifier: str` per contracts/tools.md, validates at least one is provided, resolves feed_identifier to feed_id if given, calls appropriate database method, returns success with items_marked count
- [x] T029 [US5] Implement `mark_as_unread` tool function in `src/rssfeed_agent/tools.py` — accepts `item_ids: list[int]`, calls `database.mark_items_unread`, returns success with items_marked count
- [x] T030 [US5] Register `mark_as_read` and `mark_as_unread` tools in `src/rssfeed_agent/agent.py` — bind both tools to model, update system prompt with read-state management capabilities

**Checkpoint**: All 5 user stories complete. Full feature set operational.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Edge case handling, robustness, and final integration validation

- [ ] T031 [P] Add edge case handling for malformed feeds in `src/rssfeed_agent/feed_parser.py` — handle valid XML that is not RSS/Atom (reject with clear message), handle partial XML (parse what's possible, skip malformed entries, return warnings list), handle feeds requiring authentication (detect 401/403 responses, advise user)
- [ ] T032 [P] Add graceful error handling and logging throughout `src/rssfeed_agent/poller.py` — log each poll cycle start/end, log per-feed fetch results, handle network timeouts with configurable retry, ensure one feed's failure doesn't block polling of other feeds
- [ ] T033 Refine agent system prompt in `src/rssfeed_agent/agent.py` — comprehensive prompt covering all 7 tools, conversational tone guidelines (FR-017), instructions to ask clarifying questions on ambiguous input (FR-018), instructions to format item lists readably, hybrid notification behavior description
- [ ] T034 Run quickstart.md validation — verify setup instructions work end-to-end: create venv, install deps, set env vars, run agent, perform subscribe → poll → list → search → mark read flow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational (Phase 2) — No dependencies on other stories
- **User Story 2 (Phase 4)**: Depends on Foundational (Phase 2) — Uses database operations from US1 (T010) but can be implemented independently
- **User Story 3 (Phase 5)**: Depends on Foundational (Phase 2) — No dependencies on other stories
- **User Story 4 (Phase 6)**: Depends on Foundational (Phase 2) — No dependencies on other stories
- **User Story 5 (Phase 7)**: Depends on Foundational (Phase 2) — No dependencies on other stories
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Independent after Phase 2 — MVP target
- **US2 (P1)**: Independent after Phase 2 — reuses database from Phase 2, adds poller
- **US3 (P2)**: Independent after Phase 2 — reuses database from Phase 2
- **US4 (P3)**: Independent after Phase 2 — adds FTS5 search to database
- **US5 (P3)**: Independent after Phase 2 — adds read-state to database

### Within Each User Story

- Database operations before tool functions
- Tool functions before agent registration
- Agent registration before entry point integration

### Parallel Opportunities

- T004 and T005 can run in parallel (different files)
- After Phase 2: US1, US2, US3, US4, US5 can all start in parallel (each touches different tool functions and database methods)
- T031 and T032 can run in parallel (different files)
- Within each story: tasks marked [P] can run in parallel

---

## Parallel Example: User Story 1

```bash
# After Phase 2 foundation is complete:

# Step 1: Database operations (single file, sequential)
Task: T010 "Add subscribe_to_feed database operations in src/rssfeed_agent/database.py"

# Step 2: Tool function (depends on T010)
Task: T011 "Implement subscribe_to_feed tool in src/rssfeed_agent/tools.py"

# Step 3: Agent registration + entry point (depends on T011)
Task: T012 "Register subscribe_to_feed tool in src/rssfeed_agent/agent.py"
Task: T013 "Implement __main__.py entry point in src/rssfeed_agent/__main__.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T005)
2. Complete Phase 2: Foundational (T006–T009)
3. Complete Phase 3: User Story 1 (T010–T013)
4. **STOP and VALIDATE**: Run agent, subscribe to a feed, verify confirmation with metadata
5. Demo-ready: User can chat with agent and subscribe to RSS feeds

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (subscribe) → Test independently → **MVP!**
3. Add US2 (poll + display) → Test independently → Core loop complete
4. Add US3 (manage subscriptions) → Test independently → Full subscription lifecycle
5. Add US4 (search + filter) → Test independently → Content discovery
6. Add US5 (read/unread) → Test independently → Content tracking
7. Polish → Production-ready

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All tools share `src/rssfeed_agent/tools.py` — within a story, tool implementations are sequential; across stories, different tool functions can be implemented in parallel if careful about file conflicts
