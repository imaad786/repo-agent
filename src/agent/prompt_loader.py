"""
Prompt loader for loading system prompts from markdown files.

Prompts are loaded from the prompts/ directory based on agent type.
Later this can be extended to load from MCP server.
"""
import logging
from pathlib import Path
from functools import lru_cache
from typing import Optional

from .agent_types import AgentType

logger = logging.getLogger(__name__)

# Directory containing prompt files (at repository root)
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"


@lru_cache(maxsize=16)
def load_prompt(agent_type: AgentType) -> str:
    """
    Load system prompt from markdown file for given agent type.

    Prompts are cached for performance. Use reload_prompts() to clear cache.

    Args:
        agent_type: The type of agent to load prompt for

    Returns:
        System prompt string

    Raises:
        FileNotFoundError: If prompt file doesn't exist and no fallback available
    """
    prompt_file = PROMPTS_DIR / f"{agent_type.value}.md"

    if prompt_file.exists():
        prompt = prompt_file.read_text(encoding="utf-8")
        logger.debug(f"Loaded prompt for {agent_type.value} from {prompt_file}")
        return prompt

    # Fallback to general prompt if specific one not found
    fallback_file = PROMPTS_DIR / "general.md"
    if fallback_file.exists():
        logger.warning(
            f"Prompt file not found for {agent_type.value}, falling back to general.md"
        )
        return fallback_file.read_text(encoding="utf-8")

    # No fallback available
    raise FileNotFoundError(
        f"No prompt file found for {agent_type.value} and no fallback available"
    )


def reload_prompts() -> None:
    """
    Clear the prompt cache to reload prompts from files.

    Useful during development or when prompts are updated dynamically.
    """
    load_prompt.cache_clear()
    logger.info("Prompt cache cleared")


def get_prompt_path(agent_type: AgentType) -> Path:
    """
    Get the file path for an agent type's prompt.

    Args:
        agent_type: The type of agent

    Returns:
        Path to the prompt file (may not exist)
    """
    return PROMPTS_DIR / f"{agent_type.value}.md"


def list_available_prompts() -> list[AgentType]:
    """
    List all agent types that have prompt files available.

    Returns:
        List of AgentType values with existing prompt files
    """
    available = []
    for agent_type in AgentType:
        prompt_file = PROMPTS_DIR / f"{agent_type.value}.md"
        if prompt_file.exists():
            available.append(agent_type)
    return available


def get_prompt_or_default(agent_type: str, default_prompt: Optional[str] = None) -> str:
    """
    Get prompt for agent type with optional default fallback.

    Args:
        agent_type: Agent type string value
        default_prompt: Default prompt to return if not found

    Returns:
        System prompt string or default
    """
    try:
        return load_prompt(AgentType(agent_type))
    except (ValueError, FileNotFoundError) as e:
        if default_prompt is not None:
            logger.warning(f"Using default prompt: {e}")
            return default_prompt
        raise
