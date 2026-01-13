"""
API routes for deep analysis.
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Query, HTTPException
import logging

from ...services import deep_analysis_service, deep_insight_service, agent_session_service
from .schemas import (
    TriggerAnalysisRequest,
    AnalysisRunResponse,
    AnalysisRunDetailResponse,
    AnalysisSessionResponse,
    InsightResponse,
    InsightsSummaryResponse,
    UpdateInsightRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/deep-analysis", tags=["Deep Analysis"])


# ─────────────────────────────────────────────────────────────────
# Analysis Runs
# ─────────────────────────────────────────────────────────────────

@router.post("/runs", status_code=202, response_model=AnalysisRunResponse)
async def trigger_analysis(
    request: TriggerAnalysisRequest,
    user_id: UUID = Query(..., description="User UUID triggering the analysis")
):
    """
    Trigger a new deep analysis run.

    Creates a PENDING run record that the background worker will pick up.
    Returns 202 Accepted immediately - analysis runs asynchronously.
    """
    run = await deep_analysis_service.create_run(
        task_id=request.task_id,
        user_id=user_id,
        categories=request.categories,
        execution_mode=request.execution_mode,
        triggered_by=str(user_id)
    )

    logger.info(f"Created analysis run {run.id} for task {request.task_id}")

    return AnalysisRunResponse(
        id=run.id,
        task_id=run.task_id,
        user_id=run.user_id,
        categories=run.categories,
        execution_mode=run.execution_mode,
        status=run.status,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        insights_summary=run.insights_summary,
        created_on=run.created_on
    )


@router.get("/runs", response_model=List[AnalysisRunResponse])
async def list_runs(
    task_id: Optional[UUID] = Query(None, description="Filter by task ID"),
    user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, le=100, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """List analysis runs with optional filters."""
    runs = await deep_analysis_service.list_runs(
        task_id=task_id,
        user_id=user_id,
        status=status,
        limit=limit,
        offset=offset
    )

    return [
        AnalysisRunResponse(
            id=r.id,
            task_id=r.task_id,
            user_id=r.user_id,
            categories=r.categories,
            execution_mode=r.execution_mode,
            status=r.status,
            triggered_by=r.triggered_by,
            started_at=r.started_at,
            completed_at=r.completed_at,
            error_message=r.error_message,
            insights_summary=r.insights_summary,
            created_on=r.created_on
        )
        for r in runs
    ]


@router.get("/runs/{run_id}", response_model=AnalysisRunDetailResponse)
async def get_run(run_id: UUID):
    """Get analysis run with linked sessions."""
    run = await deep_analysis_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    # Get linked sessions
    session_links = await deep_analysis_service.get_sessions_for_run(run_id)

    sessions = []
    for link in session_links:
        chat_session = await agent_session_service.get_session(link.chat_session_id)
        sessions.append(AnalysisSessionResponse(
            session_id=link.chat_session_id,
            category=link.category,
            title=chat_session.title if chat_session else None
        ))

    return AnalysisRunDetailResponse(
        id=run.id,
        task_id=run.task_id,
        user_id=run.user_id,
        categories=run.categories,
        execution_mode=run.execution_mode,
        status=run.status,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        insights_summary=run.insights_summary,
        created_on=run.created_on,
        sessions=sessions
    )


@router.post("/runs/{run_id}/cancel", response_model=AnalysisRunResponse)
async def cancel_run(run_id: UUID):
    """Cancel a pending or running analysis."""
    run = await deep_analysis_service.cancel_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return AnalysisRunResponse(
        id=run.id,
        task_id=run.task_id,
        user_id=run.user_id,
        categories=run.categories,
        execution_mode=run.execution_mode,
        status=run.status,
        triggered_by=run.triggered_by,
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
        insights_summary=run.insights_summary,
        created_on=run.created_on
    )


# ─────────────────────────────────────────────────────────────────
# Insights
# ─────────────────────────────────────────────────────────────────

@router.get("/insights", response_model=List[InsightResponse])
async def list_insights(
    task_id: Optional[UUID] = Query(None, description="Filter by task ID"),
    analysis_run_id: Optional[UUID] = Query(None, description="Filter by run ID"),
    category: Optional[str] = Query(None, description="Filter by category"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    status: Optional[str] = Query(None, description="Filter by status"),
    file_path: Optional[str] = Query(None, description="Filter by file path (partial match)"),
    limit: int = Query(100, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Query insights with filters."""
    insights = await deep_insight_service.list_insights(
        task_id=task_id,
        analysis_run_id=analysis_run_id,
        category=category,
        severity=severity,
        status=status,
        file_path=file_path,
        limit=limit,
        offset=offset
    )

    return [
        InsightResponse(
            id=i.id,
            task_id=i.task_id,
            analysis_run_id=i.analysis_run_id,
            category=i.category,
            severity=i.severity,
            title=i.title,
            description=i.description,
            file_path=i.file_path,
            line_start=i.line_start,
            line_end=i.line_end,
            recommended_action=i.recommended_action,
            code_suggestion=i.code_suggestion,
            status=i.status,
            details=i.details,
            confidence_score=i.confidence_score,
            created_on=i.created_on
        )
        for i in insights
    ]


@router.patch("/insights/{insight_id}", response_model=InsightResponse)
async def update_insight(
    insight_id: UUID,
    request: UpdateInsightRequest,
    user_id: Optional[UUID] = Query(None, description="User making the update")
):
    """Update insight status."""
    insight = await deep_insight_service.update_insight_status(
        insight_id=insight_id,
        status=request.status,
        resolved_by=user_id,
        resolution_notes=request.resolution_notes
    )

    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    return InsightResponse(
        id=insight.id,
        task_id=insight.task_id,
        analysis_run_id=insight.analysis_run_id,
        category=insight.category,
        severity=insight.severity,
        title=insight.title,
        description=insight.description,
        file_path=insight.file_path,
        line_start=insight.line_start,
        line_end=insight.line_end,
        recommended_action=insight.recommended_action,
        code_suggestion=insight.code_suggestion,
        status=insight.status,
        details=insight.details,
        confidence_score=insight.confidence_score,
        created_on=insight.created_on
    )


@router.get("/insights/summary", response_model=InsightsSummaryResponse)
async def get_insights_summary(
    task_id: UUID = Query(..., description="Task ID to summarize")
):
    """Get insights summary for a task."""
    summary = await deep_insight_service.get_summary(task_id)
    return InsightsSummaryResponse(**summary)
