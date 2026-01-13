"""
Deep insight entity for analysis findings.
"""
from typing import Optional, Dict
from uuid import UUID
from datetime import datetime
from decimal import Decimal

from sqlmodel import Field, Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import DateTime

from .base import BaseEntityMixin
from ..utils.settings import settings


class InsightSeverity:
    """Severity levels for insights."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class InsightStatus:
    """Workflow status for insights."""
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    WONT_FIX = "wont_fix"


class DeepInsight(BaseEntityMixin, table=True):
    """
    Represents a single finding/insight from deep analysis.

    Can be linked to a specific analysis run and has workflow status
    for tracking resolution. Includes location information (file, lines)
    and recommendations for fixing issues.
    """
    __tablename__ = "deep_insights"
    __table_args__ = {"schema": settings.database_schema}

    # Context
    task_id: UUID = Field(nullable=False, index=True)
    analysis_run_id: Optional[UUID] = Field(
        default=None,
        foreign_key=f"{settings.database_schema}.deep_analysis_runs.id",
        index=True
    )

    # Classification
    category: str = Field(max_length=50, index=True)
    severity: str = Field(max_length=20, index=True)

    # Content
    title: str = Field(max_length=500)
    description: Optional[str] = Field(default=None)

    # Location
    file_path: Optional[str] = Field(default=None, max_length=1000, index=True)
    line_start: Optional[int] = Field(default=None)
    line_end: Optional[int] = Field(default=None)

    # Recommendations
    recommended_action: Optional[str] = Field(default=None)
    code_suggestion: Optional[str] = Field(default=None)

    # Workflow
    status: str = Field(default=InsightStatus.NEW, max_length=30, index=True)
    resolved_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
    resolved_by: Optional[UUID] = Field(default=None)
    resolution_notes: Optional[str] = Field(default=None)

    # Metadata
    details: Optional[Dict] = Field(default=None, sa_column=Column(JSONB))
    confidence_score: Optional[Decimal] = Field(default=None)
    agent_model: Optional[str] = Field(default=None, max_length=100)
