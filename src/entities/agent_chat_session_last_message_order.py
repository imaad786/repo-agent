"""
Entity to track the last message order for each agent chat session.
"""
from uuid import UUID

from sqlmodel import Field

from .base import BaseEntityMixin
from ..utils.settings import settings


class AgentChatSessionLastMessageOrder(BaseEntityMixin, table=True):
    """
    Tracks the last message order number for each chat session.
    Used to generate sequential message ordering efficiently.
    """
    __tablename__ = "agent_chat_session_last_message_order"
    __table_args__ = {"schema": settings.database_schema}

    chat_session_id: UUID = Field(foreign_key=f"{settings.database_schema}.agent_chat_sessions.id", nullable=False,
                                  unique=True, index=True)

    last_message_order: int = Field(default=0, nullable=False)
