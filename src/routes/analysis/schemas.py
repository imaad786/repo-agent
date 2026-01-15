"""
Request and response schemas for analysis endpoints.
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
    """Request to trigger a new analysis run."""
    task_id: UUID = Field(..., description="Task ID from indexer (data isolation key)")
    user_id: UUID = Field(..., description="User ID triggering the analysis")
    repo_namespace: str = Field(..., description="Repository namespace for the indexed repo")


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
    repo_namespace: Optional[str] = None
    categories: List[str]
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


# ─────────────────────────────────────────────────────────────────
# Analysis Query Schemas
# ─────────────────────────────────────────────────────────────────

class CreateAnalysisQueryRequest(BaseModel):
    """Request to create a new analysis query."""
    category: str = Field(..., description="Category/agent type (security, database, etc.)")
    name: str = Field(..., max_length=200, description="Unique name for the query")
    query_text: str = Field(..., description="The analysis query/prompt text")
    description: Optional[str] = Field(None, max_length=1000, description="Description of what this query does")
    is_default: bool = Field(default=False, description="Whether this is the default query for the category")
    priority: int = Field(default=0, description="Priority (higher = used first when is_default=True)")
    expected_output_format: str = Field(default="json", description="Expected output format: json, text, markdown")
    output_schema: Optional[Dict] = Field(None, description="Optional JSON schema for output validation")


class UpdateAnalysisQueryRequest(BaseModel):
    """Request to update an existing analysis query."""
    name: Optional[str] = Field(None, max_length=200)
    query_text: Optional[str] = None
    description: Optional[str] = Field(None, max_length=1000)
    is_default: Optional[bool] = None
    priority: Optional[int] = None
    expected_output_format: Optional[str] = None
    output_schema: Optional[Dict] = None
    is_active: Optional[bool] = None


class AnalysisQueryResponse(BaseModel):
    """Analysis query response."""
    id: UUID
    category: str
    name: str
    description: Optional[str] = None
    query_text: str
    is_default: bool
    priority: int
    expected_output_format: str
    output_schema: Optional[Dict] = None
    is_active: bool
    created_on: datetime
    modified_on: datetime

    class Config:
        from_attributes = True


class AnalysisQuerySummaryResponse(BaseModel):
    """Summary of an analysis query (without full query_text)."""
    id: UUID
    category: str
    name: str
    description: Optional[str] = None
    is_default: bool
    priority: int
    expected_output_format: str
    is_active: bool
    created_on: datetime

    class Config:
        from_attributes = True
