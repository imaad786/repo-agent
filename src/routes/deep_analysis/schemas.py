"""
Request and response schemas for deep analysis endpoints.
"""
from typing import Optional, List, Dict
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Request Schemas
# ─────────────────────────────────────────────────────────────────

class TriggerAnalysisRequest(BaseModel):
    """Request to trigger a new deep analysis run."""
    task_id: UUID = Field(..., description="Task ID from indexer (data isolation key)")
    categories: List[str] = Field(
        default=["security", "code_quality"],
        description="Categories to analyze. Examples: security, code_quality, performance, database, architecture"
    )
    execution_mode: str = Field(
        default="parallel",
        description="Execution mode: 'parallel' or 'sequential'"
    )


class UpdateInsightRequest(BaseModel):
    """Request to update insight status."""
    status: str = Field(
        ...,
        description="New status: new, acknowledged, in_progress, resolved, wont_fix"
    )
    resolution_notes: Optional[str] = Field(
        None,
        description="Notes about resolution"
    )


# ─────────────────────────────────────────────────────────────────
# Response Schemas
# ─────────────────────────────────────────────────────────────────

class AnalysisSessionResponse(BaseModel):
    """Session linked to an analysis run."""
    session_id: UUID
    category: str
    title: Optional[str] = None

    class Config:
        from_attributes = True


class AnalysisRunResponse(BaseModel):
    """Analysis run summary."""
    id: UUID
    task_id: UUID
    user_id: UUID
    categories: List[str]
    execution_mode: str
    status: str
    triggered_by: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    insights_summary: Optional[Dict] = None
    created_on: datetime

    class Config:
        from_attributes = True


class AnalysisRunDetailResponse(AnalysisRunResponse):
    """Analysis run with linked sessions."""
    sessions: List[AnalysisSessionResponse] = []


class InsightResponse(BaseModel):
    """Single insight."""
    id: UUID
    task_id: UUID
    analysis_run_id: Optional[UUID] = None
    category: str
    severity: str
    title: str
    description: Optional[str] = None
    file_path: Optional[str] = None
    line_start: Optional[int] = None
    line_end: Optional[int] = None
    recommended_action: Optional[str] = None
    code_suggestion: Optional[str] = None
    status: str
    details: Optional[Dict] = None
    confidence_score: Optional[Decimal] = None
    created_on: datetime

    class Config:
        from_attributes = True


class InsightsSummaryResponse(BaseModel):
    """Aggregated insights summary."""
    total: int
    by_severity: Dict[str, int]
    by_category: Dict[str, int]
    by_status: Dict[str, int]
