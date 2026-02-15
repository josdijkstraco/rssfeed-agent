# Implementation Plan: RSS Feed Agent

**Branch**: `001-rss-feed-agent` | **Date**: 2026-02-13 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-rss-feed-agent/spec.md`

## Summary

Build a chat-based conversational RSS feed agent using LangGraph (StateGraph + tool-calling pattern) with Anthropic's Claude Sonnet 4.5 as the LLM. The agent allows users to subscribe to RSS/Atom feeds, periodically polls for new items, and supports searching, filtering, and managing feed subscriptions — all via natural language interaction in the terminal. Data is persisted in SQLite; agent state is checkpointed via LangGraph's SqliteSaver.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: langgraph, langchain-anthropic, langchain-core, feedparser, aiosqlite
**Storage**: SQLite (feeds/items) + LangGraph SqliteSaver (agent checkpoints)
**Testing**: pytest, pytest-asyncio, pytest-cov
**Target Platform**: Local machine (macOS/Linux terminal)
**Project Type**: Single Python package
**Performance Goals**: 100 feeds polled per interval without user-noticeable delay (SC-003); search in under 5 seconds (SC-004)
**Constraints**: Single-user, local storage, public feeds only, RSS 2.0 + Atom 1.0
**Scale/Scope**: Up to 100 subscribed feeds, thousands of stored items

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution not yet configured (blank template). No gates to enforce. Proceeding.

## Project Structure

### Documentation (this feature)

```text
specs/001-rss-feed-agent/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output - technology decisions
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - setup guide
├── contracts/
│   └── tools.md         # Phase 1 output - agent tool contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
src/
└── rssfeed_agent/
    ├── __init__.py          # Package init, version
    ├── __main__.py          # Entry point (python -m rssfeed_agent)
    ├── agent.py             # LangGraph StateGraph definition, nodes, edges
    ├── tools.py             # Tool functions (subscribe, unsubscribe, list, get, search, mark)
    ├── models.py            # Data classes for Feed and Item
    ├── database.py          # SQLite operations (CRUD, search, schema init)
    ├── feed_parser.py       # feedparser wrapper (fetch, validate, parse)
    └── poller.py            # Async background polling loop

tests/
├── conftest.py              # Shared fixtures (temp DB, mock feeds)
├── unit/
│   ├── test_database.py     # Database CRUD operations
│   ├── test_feed_parser.py  # Feed parsing and validation
│   ├── test_tools.py        # Tool function logic
│   └── test_poller.py       # Polling loop behavior
└── integration/
    ├── test_agent.py        # End-to-end agent graph invocation
    └── test_subscribe_flow.py  # Subscribe → poll → fetch → display flow

pyproject.toml               # Project metadata, dependencies, tool config
```

**Structure Decision**: Single Python package (`src/rssfeed_agent/`). No frontend, no separate API server. The agent is a terminal application that combines a chat loop with background polling. This is the simplest structure that meets all requirements.

## Complexity Tracking

No constitution violations to justify.
