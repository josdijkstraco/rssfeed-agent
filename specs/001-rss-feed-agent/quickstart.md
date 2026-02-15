# Quickstart: RSS Feed Agent

**Date**: 2026-02-13
**Feature**: 001-rss-feed-agent

## Prerequisites

- Python 3.11+
- An Anthropic API key (set as `ANTHROPIC_API_KEY` environment variable)

## Setup

```bash
# Clone and enter the project
cd rssfeed-agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install -e ".[dev]"
```

## Configuration

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY="your-key-here"

# Optional: customize poll interval (default: 900 seconds / 15 minutes)
export RSS_POLL_INTERVAL=900
```

## Run the Agent

```bash
python -m rssfeed_agent
```

The agent starts in interactive chat mode. Type natural language commands:

```
You: Subscribe to https://techcrunch.com/feed/
Agent: Subscribed to TechCrunch! Found 50 items. The feed covers startup and technology news.

You: What's new?
Agent: Here are the latest items across your feeds:
  1. "New AI Startup Raises $10M" - TechCrunch (2 hours ago)
  2. "Python 3.13 Released" - TechCrunch (5 hours ago)
  ...

You: Show me my feeds
Agent: You have 1 active feed:
  - TechCrunch (https://techcrunch.com/feed/) - Active, last checked 2 min ago

You: Search for "python"
Agent: Found 3 items matching "python":
  1. "Python 3.13 Released" - TechCrunch
  ...
```

## Run Tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# With coverage
pytest --cov=rssfeed_agent
```

## Project Structure

```
rssfeed-agent/
├── src/
│   └── rssfeed_agent/
│       ├── __init__.py
│       ├── __main__.py        # Entry point
│       ├── agent.py           # LangGraph agent definition
│       ├── tools.py           # Agent tool implementations
│       ├── models.py          # Data models (Feed, Item)
│       ├── database.py        # SQLite database operations
│       ├── feed_parser.py     # RSS/Atom parsing via feedparser
│       └── poller.py          # Background polling loop
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
├── pyproject.toml
└── README.md
```
