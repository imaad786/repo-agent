"""
Agent module initialization.

Provides access to the agent registry for managing multiple specialized agents.
"""
from .code_intelligence_agent import CodeIntelligenceAgent
from .agent_types import AgentType
from .agent_registry import (
    AgentRegistry,
    initialize_registry,
    get_registry,
    shutdown_registry
)
from .prompt_loader import load_prompt, reload_prompts

__all__ = [
    # Agent class
    "CodeIntelligenceAgent",
    # Agent types
    "AgentType",
    # Registry
    "AgentRegistry",
    "initialize_registry",
    "get_registry",
    "shutdown_registry",
    # Prompts
    "load_prompt",
    "reload_prompts",
]
