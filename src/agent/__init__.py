"""
Agent module initialization.
"""
from typing import Optional

from .code_intelligence_agent import CodeIntelligenceAgent
from .configure_agent import configure_agent

agent_instance : Optional[CodeIntelligenceAgent] = None

async def initialize_and_get_agent():
    global agent_instance
    if agent_instance is None:
        agent_instance = await configure_agent()
    return agent_instance


__all__ = [
    "CodeIntelligenceAgent",
    "configure_agent",
    "agent_instance",
    "initialize_and_get_agent",
]
