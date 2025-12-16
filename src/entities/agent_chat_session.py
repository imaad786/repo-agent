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
    Each session is associated with a user and a specific repository namespace.
    """
    __tablename__ = "agent_chat_sessions"
    __table_args__ = {"schema": settings.database_schema}

    user_id: UUID = Field(nullable=False, index=True)

    title: Optional[str] = Field(default=None, max_length=500)

    repo_namespace: str = Field(nullable=False, index=True, max_length=500)

    status: str = Field(default=ChatSessionStatus.ACTIVE.value, max_length=50)
