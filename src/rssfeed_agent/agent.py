"""LangGraph agent definition for RSS Feed Agent."""

import sqlite3
from typing import Literal

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, MessagesState, StateGraph

from rssfeed_agent.tools import (
    get_items,
    list_feeds,
    mark_as_read,
    mark_as_unread,
    search_items,
    subscribe_to_feed,
    unsubscribe_from_feed,
)

SYSTEM_PROMPT = """You are an RSS Feed Agent — a helpful assistant that manages RSS feed subscriptions.

You help users:
- Subscribe to RSS and Atom feeds by URL
- View their latest feed items
- List and manage their feed subscriptions
- Unsubscribe from feeds they no longer want
- Search for items by keyword across all feeds
- Mark items as read or unread to track what they've consumed

When a user wants to subscribe to an RSS feed, use the subscribe_to_feed tool with the URL they provide.
When a user asks to see items, news, or what's new, use the get_items tool. You can filter by:
- A specific feed (by title or URL)
- Date range (since/until in ISO 8601 format)
- Unread items only
When a user asks to see their feeds or subscriptions, use the list_feeds tool.
When a user wants to unsubscribe or remove a feed, use the unsubscribe_from_feed tool with the feed title or URL.
When a user wants to search for items by keyword, use the search_items tool. It searches across titles and summaries of all items.
When a user wants to mark items as read, use the mark_as_read tool. You can mark specific item IDs or all items from a feed.
When a user wants to mark items as unread, use the mark_as_unread tool with the item IDs.
If they give you a website URL (not a feed URL), try common feed paths like /feed, /rss, or /atom.xml.
When the user's intent is unclear, ask a clarifying question rather than guessing.
Present feed items in a readable format: title, link, date, and a brief summary.
Be concise but informative in your responses."""

# All tools available to the agent
TOOLS = [subscribe_to_feed, get_items, list_feeds, unsubscribe_from_feed, search_items, mark_as_read, mark_as_unread]


def create_agent(
    checkpoint_db_path: str = "rssfeed_agent_checkpoints.db",
    tools: list | None = None,
):
    """Create and compile the LangGraph agent.

    Args:
        checkpoint_db_path: Path to SQLite database for LangGraph checkpointing.
        tools: List of tool functions to bind to the agent. If None, uses default TOOLS.

    Returns:
        Compiled LangGraph agent.
    """
    if tools is None:
        tools = TOOLS

    model = ChatAnthropic(
        model="claude-sonnet-4-5-20250929",
        temperature=0,
    )

    if tools:
        model_with_tools = model.bind_tools(tools)
    else:
        model_with_tools = model

    tools_by_name = {tool.name: tool for tool in tools}

    def agent_node(state: MessagesState):
        """LLM call node — decides whether to use a tool or respond directly."""
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}

    def tool_node(state: MessagesState):
        """Execute tool calls from the LLM response."""
        results = []
        last_message = state["messages"][-1]
        for tool_call in last_message.tool_calls:
            tool = tools_by_name[tool_call["name"]]
            result = tool.invoke(tool_call["args"])
            results.append(
                ToolMessage(content=str(result), tool_call_id=tool_call["id"])
            )
        return {"messages": results}

    def should_continue(state: MessagesState) -> Literal["tool_node", "__end__"]:
        """Route to tool execution or end based on LLM output."""
        last_message = state["messages"][-1]
        if last_message.tool_calls:
            return "tool_node"
        return END

    # Build the graph
    builder = StateGraph(MessagesState)
    builder.add_node("agent_node", agent_node)
    builder.add_node("tool_node", tool_node)

    builder.add_edge(START, "agent_node")
    builder.add_conditional_edges("agent_node", should_continue, ["tool_node", END])
    builder.add_edge("tool_node", "agent_node")

    # Compile with SQLite checkpointer for persistence
    checkpointer = SqliteSaver(sqlite3.connect(checkpoint_db_path, check_same_thread=False))
    agent = builder.compile(checkpointer=checkpointer)

    return agent
