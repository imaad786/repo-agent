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

# Subfolder for orchestrator-specific prompts (orchestrator.md + *_domain.md)
ORCHESTRATION_PROMPTS_DIR = PROMPTS_DIR / "orchestration_prompts"


@lru_cache(maxsize=16)
def load_prompt(agent_type: AgentType) -> str:
    """
    Load system prompt from markdown file for given agent type.

    For AgentType.ORCHESTRATOR, loads from the orchestration_prompts/ subfolder.
    For all other types, loads from the root prompts/ directory (existing behavior).

    Prompts are cached for performance. Use reload_prompts() to clear cache.

    Args:
        agent_type: The type of agent to load prompt for

    Returns:
        System prompt string

    Raises:
        FileNotFoundError: If prompt file doesn't exist and no fallback available
    """
    # Orchestrator prompt lives in the orchestration_prompts/ subfolder
    if agent_type == AgentType.ORCHESTRATOR:
        prompt_file = ORCHESTRATION_PROMPTS_DIR / "orchestrator.md"
    else:
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


@lru_cache(maxsize=16)
def load_domain_prompt(agent_type: AgentType) -> str:
    """
    Load domain-specific prompt (trimmed version without shared sections)
    for injection by the orchestrator middleware.

    These are the *_domain.md files in the orchestration_prompts/ subfolder,
    not the full standalone prompts.

    Args:
        agent_type: The domain type to load prompt for

    Returns:
        Domain-specific prompt string

    Raises:
        FileNotFoundError: If domain prompt file doesn't exist
    """
    prompt_file = ORCHESTRATION_PROMPTS_DIR / f"{agent_type.value}_domain.md"

    if prompt_file.exists():
        prompt = prompt_file.read_text(encoding="utf-8")
        logger.debug(f"Loaded domain prompt for {agent_type.value} from {prompt_file}")
        return prompt

    # Fallback to general domain prompt
    fallback_file = ORCHESTRATION_PROMPTS_DIR / "general_domain.md"
    if fallback_file.exists():
        logger.warning(
            f"Domain prompt not found for {agent_type.value}, falling back to general_domain.md"
        )
        return fallback_file.read_text(encoding="utf-8")

    raise FileNotFoundError(
        f"No domain prompt file found for {agent_type.value}"
    )


def reload_prompts() -> None:
    """
    Clear all prompt caches to reload prompts from files.

    Useful during development or when prompts are updated dynamically.
    """
    load_prompt.cache_clear()
    load_domain_prompt.cache_clear()
    logger.info("All prompt caches cleared")


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
