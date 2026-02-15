# Research: RSS Feed Agent

**Date**: 2026-02-13
**Feature**: 001-rss-feed-agent

## R1: Agent Framework — LangGraph

**Decision**: Use LangGraph with `StateGraph` and `ChatAnthropic` to build the conversational RSS agent.

**Rationale**: LangGraph provides a graph-based state machine for building stateful agents with built-in persistence (checkpointing), tool calling, and conditional routing. It integrates natively with `langchain_anthropic.ChatAnthropic`, which is the preferred way to use Anthropic models in the LangChain/LangGraph ecosystem. The `StateGraph` + nodes + conditional edges pattern gives explicit control over agent behavior — important for an RSS agent that needs to route between distinct actions (subscribe, fetch, search, etc.).

**Alternatives considered**:
- **Raw Anthropic SDK**: Simpler but lacks built-in state management, persistence, and tool orchestration. Would require hand-rolling the agent loop.
- **LangChain AgentExecutor**: Legacy approach; LangGraph is the recommended successor for stateful agent workflows.
- **Anthropic Claude Agent SDK**: Focused on interactive CLI sessions, not suited for a long-running daemon with periodic polling.

## R2: LLM Integration — Anthropic via ChatAnthropic

**Decision**: Use `langchain_anthropic.ChatAnthropic` with `claude-sonnet-4-5-20250929` as the default model, integrated via LangGraph's tool-calling pattern.

**Rationale**: `ChatAnthropic` is the LangChain-compatible wrapper around the Anthropic API. It supports `.bind_tools()` for native tool calling, which LangGraph uses to route between LLM reasoning and tool execution nodes. Claude Sonnet 4.5 provides strong reasoning at reasonable cost for an agent that processes user intents and generates conversational responses.

**Alternatives considered**:
- **Claude Opus 4.6**: Higher capability but significantly more expensive; unnecessary for intent classification and feed summarization.
- **Claude Haiku 4.5**: Cheaper but may struggle with nuanced intent parsing in edge cases.

## R3: RSS Feed Parsing

**Decision**: Use `feedparser` (Python) for RSS/Atom feed parsing.

**Rationale**: `feedparser` is the de facto standard Python library for parsing RSS 2.0, Atom 1.0, and other syndication formats. It handles malformed feeds gracefully, normalizes different feed formats into a consistent structure, and has been battle-tested for over a decade. It aligns with FR-001, FR-002, and FR-014.

**Alternatives considered**:
- **atoma**: Stricter parser, less tolerant of malformed feeds (conflicts with FR-014 graceful degradation).
- **Manual XML parsing (lxml/ElementTree)**: Too low-level; would reimplement what feedparser already does.

## R4: Data Persistence

**Decision**: Use SQLite via Python's built-in `sqlite3` module for feed and item storage. Use LangGraph's `SqliteSaver` for agent checkpoint persistence.

**Rationale**: SQLite is a natural fit for a single-user local agent — zero configuration, file-based, supports SQL queries for search/filter operations (FR-010, FR-011), and persists across restarts (FR-003). LangGraph's `SqliteSaver` provides checkpoint persistence using the same database technology, keeping the stack simple. SQLite comfortably handles the scale target of 100 feeds (SC-003).

**Alternatives considered**:
- **JSON files**: Simpler but makes search/filter inefficient at scale; no transactional guarantees.
- **PostgreSQL**: Overkill for single-user local agent; adds deployment complexity.
- **LangGraph MemorySaver**: In-memory only; does not persist across restarts (violates FR-003 and SC-007).

## R5: Periodic Polling Architecture

**Decision**: Use Python's `asyncio` with background tasks for periodic feed polling, running alongside the agent's chat interface.

**Rationale**: The agent needs to simultaneously handle user chat input and poll feeds in the background (FR-004). Python's `asyncio` enables cooperative multitasking without threads. A simple `asyncio.create_task` with a loop and `asyncio.sleep` handles the polling interval. The agent process runs as a long-lived async application.

**Alternatives considered**:
- **APScheduler**: Full-featured scheduler but adds a dependency for a single recurring task.
- **Threading**: Works but adds complexity with thread safety around shared database access.
- **Celery/cron**: External process orchestration; overengineered for a single-user local agent.

## R6: Chat Interface

**Decision**: Terminal-based interactive chat using Python's `asyncio` stdin reading, with the LangGraph agent processing each user message.

**Rationale**: A terminal chat interface is the simplest way to deliver a conversational agent (FR-015, FR-017). The user types messages, the agent processes them through the LangGraph graph (which includes LLM reasoning + tool execution), and responses are printed to stdout. This aligns with the single-user, locally-running assumptions.

**Alternatives considered**:
- **Web UI (Streamlit/Gradio)**: Adds frontend complexity; deferred to future iteration.
- **Slack/Discord bot**: Requires external service integration; out of scope per assumptions.

## R7: New Items Notification Behavior

**Decision**: Hybrid pull model — the agent silently fetches in the background, but displays a brief "X new items since last check" summary when the user next interacts.

**Rationale**: This balances simplicity with usability. A pure pull model means users may not realize new content arrived. A pure push model complicates the terminal UX (interrupting user input). The hybrid approach piggybacks on the next user interaction to surface new item counts without interrupting workflow.

## R8: Item Retention Policy

**Decision**: Retain items indefinitely by default with no automatic cleanup. Users can manually unsubscribe from a feed, which removes its items.

**Rationale**: For a single-user local agent, SQLite storage is practically unlimited for text-based RSS items. Adding retention policies adds complexity without clear user value in the initial version. This can be revisited if storage becomes a concern.
