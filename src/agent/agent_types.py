"""
Agent type definitions for the multi-agent system.
"""
from enum import Enum


class AgentType(str, Enum):
    """
    Available agent types in the system.

    Each agent type has a specialized system prompt but shares
    the same tools, memory, checkpointer, and infrastructure.
    """
    GENERAL = "general"
    SECURITY = "security"
    DATABASE = "database"
    API = "api"
    PERFORMANCE = "performance"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    CODE_QUALITY = "code_quality"

    @classmethod
    def values(cls) -> list[str]:
        """Return list of all agent type values."""
        return [member.value for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a value is a valid agent type."""
        return value in cls.values()
