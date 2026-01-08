"""
Agent chat session entity for code intelligence conversations.
"""
from enum import Enum
from typing import Optional
from uuid import UUID

from sqlmodel import Field

from .base import BaseEntityMixin
from ..utils.settings import settings


class ChatSessionStatus(Enum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    ENDED = "ENDED"


class AgentChatSession(BaseEntityMixin, table=True):
    """
    Represents a chat session for the code intelligence agent.
    Each session is associated with a user and a specific task (indexing task).
    """
    __tablename__ = "agent_chat_sessions"
    __table_args__ = {"schema": settings.database_schema}

    user_id: UUID = Field(nullable=False, index=True)

    title: Optional[str] = Field(default=None, max_length=500)

    # Task ID is the primary identifier for data isolation in MCP server
    task_id: UUID = Field(nullable=False, index=True)

    # Repo namespace is now optional for additional filtering/metadata
    repo_namespace: Optional[str] = Field(default=None, index=True, max_length=500)

    status: str = Field(default=ChatSessionStatus.ACTIVE.value, max_length=50)
