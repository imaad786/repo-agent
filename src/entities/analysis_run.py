"""
Analysis run entity for background worker processing.
"""
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime

from sqlmodel import Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import DateTime

from .base import BaseEntityMixin
from ..utils.settings import settings


class AnalysisRunStatus:
    """Status values for analysis runs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisRun(BaseEntityMixin, table=True):
    """
    Represents a batch of analysis across multiple categories.

    One run contains multiple categories (stored as JSONB array).
    Background worker polls for pending runs and processes them.

    Worker locking fields (worker_id, locked_at) enable optimistic
    locking to prevent multiple workers from processing the same run.
    """
    __tablename__ = "analysis_runs"
    __table_args__ = {"schema": settings.database_schema}

    # Context / Data Isolation
    task_id: UUID = Field(nullable=False, index=True)
    user_id: UUID = Field(nullable=False, index=True)
    repo_namespace: Optional[str] = Field(default=None, max_length=500, index=True)

    # Analysis Configuration (all agent types, parallel execution)
    categories: List[str] = Field(sa_column=Column(JSONB, nullable=False))

    # Status & Progress
    status: str = Field(default=AnalysisRunStatus.PENDING, max_length=20, index=True)
    triggered_by: Optional[str] = Field(default=None, max_length=100)

    # Timing
    started_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    completed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))

    # Results & Errors
    error_message: Optional[str] = Field(default=None)
    insights_summary: Optional[Dict] = Field(default=None, sa_column=Column(JSONB))

    # Worker Locking
    worker_id: Optional[str] = Field(default=None, max_length=100, index=True)
    locked_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
