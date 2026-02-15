"""Entry point for RSS Feed Agent: python -m rssfeed_agent"""

import asyncio
import logging
import os
import uuid

from langchain_core.messages import HumanMessage

from rssfeed_agent.agent import create_agent
from rssfeed_agent.database import Database
from rssfeed_agent.poller import start_polling
from rssfeed_agent.tools import set_database

DEFAULT_DB_PATH = "rssfeed_agent.db"
CHECKPOINT_DB_PATH = "rssfeed_agent_checkpoints.db"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
# Quiet noisy loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)


async def chat_loop(agent, config: dict) -> None:
    """Run the interactive chat loop."""
    print("RSS Feed Agent ready! Type your message (Ctrl+C to quit).\n")

    while True:
        try:
            user_input = await asyncio.to_thread(input, "You: ")
        except EOFError:
            break

        if not user_input.strip():
            continue

        try:
            response = await asyncio.to_thread(
                agent.invoke,
                {"messages": [HumanMessage(content=user_input)]},
                config,
            )

            # Extract the last AI message
            last_message = response["messages"][-1]
            print(f"\nAgent: {last_message.content}\n")
        except Exception as e:
            error_msg = str(e)
            if "tool_use" in error_msg and "tool_result" in error_msg:
                # Corrupted checkpoint — start a fresh thread
                config["configurable"]["thread_id"] = uuid.uuid4().hex
                print("\nAgent: Sorry, I had an issue with my memory. Let me start fresh. Please try again.\n")
            else:
                print(f"\nAgent: Sorry, I encountered an error: {error_msg}\n")


async def main() -> None:
    """Initialize and run the RSS Feed Agent."""
    db_path = os.environ.get("RSS_DB_PATH", DEFAULT_DB_PATH)
    checkpoint_path = os.environ.get("RSS_CHECKPOINT_PATH", CHECKPOINT_DB_PATH)

    # Initialize database
    db = Database(db_path)
    db.connect()
    set_database(db)

    # Create agent with separate checkpoint database
    agent = create_agent(checkpoint_db_path=checkpoint_path)

    # Each session gets a fresh thread to avoid corrupted checkpoint issues
    thread_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": thread_id}}

    # Start background poller
    poller_task = asyncio.create_task(start_polling(db))

    try:
        await chat_loop(agent, config)
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        poller_task.cancel()
        try:
            await poller_task
        except asyncio.CancelledError:
            pass
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
