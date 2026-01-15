"""
API routes for analysis.
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Query, HTTPException
import logging

from ...services import analysis_service, insight_service, agent_session_service
from ...services.analysis_query_service import analysis_query_service
from ...agent.agent_types import AgentType
from .schemas import (
    TriggerAnalysisRequest,
    AnalysisRunResponse,
    AnalysisRunDetailResponse,
    AnalysisSessionResponse,
    InsightResponse,
    InsightsSummaryResponse,
    UpdateInsightRequest,
    CreateAnalysisQueryRequest,
    UpdateAnalysisQueryRequest,
    AnalysisQueryResponse,
    AnalysisQuerySummaryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analysis", tags=["Analysis"])


# ─────────────────────────────────────────────────────────────────
# Analysis Runs
# ─────────────────────────────────────────────────────────────────

@router.post("/runs", status_code=202, response_model=AnalysisRunResponse)
async def trigger_analysis(request: TriggerAnalysisRequest):
    """
    Trigger a new analysis run.

    Creates a PENDING run record that the background worker will pick up.
    All agent types will be analyzed in parallel.
    Returns 202 Accepted immediately - analysis runs asynchronously.
    """
    # Use all agent types for comprehensive analysis
    categories = AgentType.values()

    run = await analysis_service.create_run(
        task_id=request.task_id,
        user_id=request.user_id,
        repo_namespace=request.repo_namespace,
        categories=categories,
        triggered_by=str(request.user_id)
    )

    logger.info(f"Created analysis run {run.id} for task {request.task_id} with {len(categories)} categories")

    return AnalysisRunResponse(
        id=run.id,
        task_id=run.task_id,
        user_id=run.user_id,
        repo_namespace=run.repo_namespace,
        categories=run.categories,
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
    runs = await analysis_service.list_runs(
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
            repo_namespace=r.repo_namespace,
            categories=r.categories,
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
    run = await analysis_service.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    # Get linked sessions
    session_links = await analysis_service.get_sessions_for_run(run_id)

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
        repo_namespace=run.repo_namespace,
        categories=run.categories,
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
    run = await analysis_service.cancel_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Analysis run not found")

    return AnalysisRunResponse(
        id=run.id,
        task_id=run.task_id,
        user_id=run.user_id,
        repo_namespace=run.repo_namespace,
        categories=run.categories,
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
    insights = await insight_service.list_insights(
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
    insight = await insight_service.update_insight_status(
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
    summary = await insight_service.get_summary(task_id)
    return InsightsSummaryResponse(**summary)


# ─────────────────────────────────────────────────────────────────
# Analysis Queries (CRUD)
# ─────────────────────────────────────────────────────────────────

@router.get("/queries", response_model=List[AnalysisQuerySummaryResponse])
async def list_queries(
    category: Optional[str] = Query(None, description="Filter by category"),
    is_default: Optional[bool] = Query(None, description="Filter by is_default flag"),
    limit: int = Query(100, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """
    List analysis queries.

    Returns summaries without full query text for efficiency.
    Use GET /queries/{query_id} to get full query details.
    """
    queries = await analysis_query_service.list_queries(
        category=category,
        is_default=is_default,
        limit=limit,
        offset=offset
    )

    return [
        AnalysisQuerySummaryResponse(
            id=q.id,
            category=q.category,
            name=q.name,
            description=q.description,
            is_default=q.is_default,
            priority=q.priority,
            expected_output_format=q.expected_output_format,
            is_active=q.is_active,
            created_on=q.created_on
        )
        for q in queries
    ]


@router.get("/queries/categories", response_model=List[str])
async def list_query_categories():
    """Get list of all categories that have queries defined."""
    return await analysis_query_service.get_all_categories()


@router.get("/queries/{query_id}", response_model=AnalysisQueryResponse)
async def get_query(query_id: UUID):
    """Get full analysis query details including query text."""
    query = await analysis_query_service.get_query(query_id)
    if not query:
        raise HTTPException(status_code=404, detail="Analysis query not found")

    return AnalysisQueryResponse(
        id=query.id,
        category=query.category,
        name=query.name,
        description=query.description,
        query_text=query.query_text,
        is_default=query.is_default,
        priority=query.priority,
        expected_output_format=query.expected_output_format,
        output_schema=query.output_schema,
        is_active=query.is_active,
        created_on=query.created_on,
        modified_on=query.modified_on
    )


@router.get("/queries/category/{category}/default", response_model=AnalysisQueryResponse)
async def get_default_query_for_category(category: str):
    """Get the default query for a specific category."""
    query = await analysis_query_service.get_default_query(category)
    if not query:
        raise HTTPException(
            status_code=404,
            detail=f"No default query found for category '{category}'"
        )

    return AnalysisQueryResponse(
        id=query.id,
        category=query.category,
        name=query.name,
        description=query.description,
        query_text=query.query_text,
        is_default=query.is_default,
        priority=query.priority,
        expected_output_format=query.expected_output_format,
        output_schema=query.output_schema,
        is_active=query.is_active,
        created_on=query.created_on,
        modified_on=query.modified_on
    )


@router.post("/queries", status_code=201, response_model=AnalysisQueryResponse)
async def create_query(request: CreateAnalysisQueryRequest):
    """
    Create a new analysis query.

    Queries are used by the background worker to analyze repositories.
    Each category can have multiple queries - the default query with
    highest priority is used for automatic analysis.
    """
    # Check if query with same category+name already exists
    existing = await analysis_query_service.get_query_by_name(
        category=request.category,
        name=request.name
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Query with name '{request.name}' already exists for category '{request.category}'"
        )

    query = await analysis_query_service.create_query(
        category=request.category,
        name=request.name,
        query_text=request.query_text,
        description=request.description,
        is_default=request.is_default,
        priority=request.priority,
        expected_output_format=request.expected_output_format,
        output_schema=request.output_schema
    )

    logger.info(f"Created analysis query {query.id} for category {request.category}")

    return AnalysisQueryResponse(
        id=query.id,
        category=query.category,
        name=query.name,
        description=query.description,
        query_text=query.query_text,
        is_default=query.is_default,
        priority=query.priority,
        expected_output_format=query.expected_output_format,
        output_schema=query.output_schema,
        is_active=query.is_active,
        created_on=query.created_on,
        modified_on=query.modified_on
    )


@router.patch("/queries/{query_id}", response_model=AnalysisQueryResponse)
async def update_query(query_id: UUID, request: UpdateAnalysisQueryRequest):
    """
    Update an existing analysis query.

    Changes take effect immediately for new analysis runs.
    Running analyses are not affected.
    """
    query = await analysis_query_service.update_query(
        query_id=query_id,
        name=request.name,
        query_text=request.query_text,
        description=request.description,
        is_default=request.is_default,
        priority=request.priority,
        expected_output_format=request.expected_output_format,
        output_schema=request.output_schema,
        is_active=request.is_active
    )

    if not query:
        raise HTTPException(status_code=404, detail="Analysis query not found")

    logger.info(f"Updated analysis query {query_id}")

    return AnalysisQueryResponse(
        id=query.id,
        category=query.category,
        name=query.name,
        description=query.description,
        query_text=query.query_text,
        is_default=query.is_default,
        priority=query.priority,
        expected_output_format=query.expected_output_format,
        output_schema=query.output_schema,
        is_active=query.is_active,
        created_on=query.created_on,
        modified_on=query.modified_on
    )


@router.delete("/queries/{query_id}", status_code=204)
async def delete_query(query_id: UUID):
    """
    Soft-delete an analysis query.

    The query is marked as deleted but retained in the database
    for audit purposes. It will no longer be used for analysis.
    """
    success = await analysis_query_service.delete_query(query_id)
    if not success:
        raise HTTPException(status_code=404, detail="Analysis query not found")

    logger.info(f"Deleted analysis query {query_id}")
