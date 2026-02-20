"""
Auto-routed memory tools for the orchestrator agent.

These wrap LangMem's memory tools to automatically route to the correct
per-domain namespace based on the router's classification stored in
ContextSchema.routed_domain.

Decision D6: Memory tools auto-route using router classification.
No domain parameter exposed to the LLM.
"""

import logging
from typing import Optional

from langchain_core.tools import tool
from langgraph.config import get_store, get_config

logger = logging.getLogger(__name__)


def create_auto_routed_manage_memory_tool():
    """
    Create a memory management tool that auto-routes to the correct
    domain namespace based on ContextSchema.routed_domain.
    """

    @tool
    async def manage_memory(content: str, action: str = "save") -> str:
        """Save or update a memory about the user or their codebase.
        Use this to remember important facts, preferences, or patterns
        that might be useful in future conversations.

        Args:
            content: The memory content to save
            action: 'save' to create/update, 'delete' to remove
        """
        store = get_store()
        config = get_config()

        user_id = config.get("configurable", {}).get("user_id", "unknown")
        routed_domain = config.get("configurable", {}).get("routed_domain", "general")

        namespace = (f"{routed_domain}_agent_memories", user_id)

        if action == "delete":
            # Search for matching memory and delete
            items = await store.asearch(namespace, query=content, limit=1)
            if items:
                await store.adelete(namespace, items[0].key)
                logger.info(f"Deleted memory from namespace {namespace}")
                return "Memory deleted."
            return "No matching memory found to delete."

        # Save new memory
        from uuid import uuid4
        key = str(uuid4())
        await store.aput(namespace, key, {"content": content})
        logger.info(f"Saved memory to namespace {namespace}")
        return "Memory saved."

    return manage_memory


def create_auto_routed_search_memory_tool():
    """
    Create a memory search tool that auto-routes to the correct
    domain namespace based on ContextSchema.routed_domain.
    """

    @tool
    async def search_memory(query: str) -> str:
        """Search for relevant memories about the user or their codebase.
        Use this to recall previously saved information.

        Args:
            query: What to search for in memories
        """
        store = get_store()
        config = get_config()

        user_id = config.get("configurable", {}).get("user_id", "unknown")
        routed_domain = config.get("configurable", {}).get("routed_domain", "general")

        namespace = (f"{routed_domain}_agent_memories", user_id)

        items = await store.asearch(namespace, query=query)
        if not items:
            return "No relevant memories found."

        memories = "\n".join([
            f"- {item.value['content']}" for item in items
        ])
        logger.info(f"Found {len(items)} memories in namespace {namespace}")
        return f"Found memories:\n{memories}"

    return search_memory
