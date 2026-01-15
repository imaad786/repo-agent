"""
Analysis session entity - links runs to chat sessions.
"""
from uuid import UUID

from sqlmodel import Field

from .base import BaseEntityMixin
from ..utils.settings import settings


class AnalysisSession(BaseEntityMixin, table=True):
    """
    Links an analysis run to its chat sessions.

    Each category in a run gets its own chat session for checkpointing.
    This allows users to continue conversations about specific analyses.

    The unique constraint on (analysis_run_id, category) ensures
    each category only has one session per run.
    """
    __tablename__ = "analysis_sessions"
    __table_args__ = {"schema": settings.database_schema}

    analysis_run_id: UUID = Field(
        foreign_key=f"{settings.database_schema}.analysis_runs.id",
        nullable=False,
        index=True
    )
    chat_session_id: UUID = Field(
        foreign_key=f"{settings.database_schema}.agent_chat_sessions.id",
        nullable=False,
        index=True
    )
    category: str = Field(max_length=50, nullable=False)
