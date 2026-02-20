"""
Agent chat session entity for code intelligence conversations.
"""
from enum import Enum
from typing import Optional, Dict
from uuid import UUID

from sqlmodel import Field, Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import BaseEntityMixin
from ..utils.settings import settings
from ..agent.agent_types import AgentType


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

    # Agent type determines which specialized agent handles this session
    agent_type: str = Field(default=AgentType.ORCHESTRATOR.value, index=True, max_length=50)

    status: str = Field(default=ChatSessionStatus.ACTIVE.value, max_length=50)

    # Metadata for additional context (e.g., analysis run info)
    session_metadata: Optional[Dict] = Field(default=None, sa_column=Column(JSONB))
