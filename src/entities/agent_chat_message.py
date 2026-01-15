"""
Agent chat message entity for storing conversation history.
"""
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Column

from .base import BaseEntityMixin
from ..utils.settings import settings


class AgentChatMessage(BaseEntityMixin, table=True):
    """
    Represents a single message in an agent chat session.
    Messages are ordered sequentially and support parent-child relationships.
    """
    __tablename__ = "agent_chat_messages"
    __table_args__ = {"schema": settings.database_schema}

    chat_session_id: UUID = Field(foreign_key=f"{settings.database_schema}.agent_chat_sessions.id", nullable=False,
                                  index=True)

    role: str = Field(nullable=False, max_length=50)

    message: Dict = Field(sa_column=Column(JSONB, nullable=False))

    artifacts: Optional[Dict] = Field(sa_column=Column(JSONB, nullable=True))

    meta_data: Optional[Dict[str, Any]] = Field(sa_column=Column(JSONB, nullable=True))

    message_order: int = Field(nullable=False, index=True)

    # Flag to indicate this message is part of an analysis query (for smart UI rendering)
    is_analysis_query: bool = Field(default=False, nullable=False)
