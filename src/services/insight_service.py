"""
Service for managing analysis insights.
"""
import logging
from datetime import datetime, UTC
from typing import List, Optional, Dict
from uuid import UUID
from decimal import Decimal

from sqlmodel import select, func, and_

from ..db.context import DbContext
from ..entities import Insight, InsightStatus

logger = logging.getLogger(__name__)


class InsightService:
    """Service for managing analysis insights."""

    async def create_insight(
        self,
        task_id: UUID,
        category: str,
        severity: str,
        title: str,
        analysis_run_id: Optional[UUID] = None,
        description: Optional[str] = None,
        file_path: Optional[str] = None,
        line_start: Optional[int] = None,
        line_end: Optional[int] = None,
        recommended_action: Optional[str] = None,
        code_suggestion: Optional[str] = None,
        details: Optional[Dict] = None,
        confidence_score: Optional[float] = None,
        agent_model: Optional[str] = None
    ) -> Insight:
        """Create a single insight."""
        async with DbContext.get_session_async() as session:
            insight = Insight(
                task_id=task_id,
                analysis_run_id=analysis_run_id,
                category=category,
                severity=severity,
                title=title,
                description=description,
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                recommended_action=recommended_action,
                code_suggestion=code_suggestion,
                details=details,
                confidence_score=Decimal(str(confidence_score)) if confidence_score else None,
                agent_model=agent_model
            )
            session.add(insight)
            await session.commit()
            await session.refresh(insight)
            return insight

    async def create_insights_batch(
        self,
        task_id: UUID,
        analysis_run_id: UUID,
        insights: List[Dict],
        agent_model: Optional[str] = None
    ) -> int:
        """Batch create insights. Returns count created."""
        async with DbContext.get_session_async() as session:
            count = 0
            for data in insights:
                confidence = data.get("confidence_score")
                insight = Insight(
                    task_id=task_id,
                    analysis_run_id=analysis_run_id,
                    category=data.get("category", "unknown"),
                    severity=data.get("severity", "info"),
                    title=data.get("title", "Untitled"),
                    description=data.get("description"),
                    file_path=data.get("file_path"),
                    line_start=data.get("line_start"),
                    line_end=data.get("line_end"),
                    recommended_action=data.get("recommended_action"),
                    code_suggestion=data.get("code_suggestion"),
                    details=data.get("details"),
                    confidence_score=Decimal(str(confidence)) if confidence else None,
                    agent_model=agent_model
                )
                session.add(insight)
                count += 1

            await session.commit()
            logger.info(f"Created {count} insights for run {analysis_run_id}")
            return count

    async def list_insights(
        self,
        task_id: Optional[UUID] = None,
        analysis_run_id: Optional[UUID] = None,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        file_path: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Insight]:
        """List insights with filters."""
        async with DbContext.get_session_async() as session:
            query = select(Insight).where(Insight.is_deleted == False)

            if task_id:
                query = query.where(Insight.task_id == task_id)
            if analysis_run_id:
                query = query.where(Insight.analysis_run_id == analysis_run_id)
            if category:
                query = query.where(Insight.category == category)
            if severity:
                query = query.where(Insight.severity == severity)
            if status:
                query = query.where(Insight.status == status)
            if file_path:
                query = query.where(Insight.file_path.ilike(f"%{file_path}%"))

            query = query.order_by(Insight.created_on.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_summary(self, task_id: UUID) -> Dict:
        """Get insights summary for a task."""
        async with DbContext.get_session_async() as session:
            base_filter = and_(
                Insight.task_id == task_id,
                Insight.is_deleted == False
            )

            # Total count
            total_result = await session.execute(
                select(func.count(Insight.id)).where(base_filter)
            )
            total = total_result.scalar() or 0

            # By severity
            severity_result = await session.execute(
                select(
                    Insight.severity,
                    func.count(Insight.id)
                ).where(base_filter).group_by(Insight.severity)
            )
            by_severity = {row[0]: row[1] for row in severity_result}

            # By category
            category_result = await session.execute(
                select(
                    Insight.category,
                    func.count(Insight.id)
                ).where(base_filter).group_by(Insight.category)
            )
            by_category = {row[0]: row[1] for row in category_result}

            # By status
            status_result = await session.execute(
                select(
                    Insight.status,
                    func.count(Insight.id)
                ).where(base_filter).group_by(Insight.status)
            )
            by_status = {row[0]: row[1] for row in status_result}

            return {
                "total": total,
                "by_severity": by_severity,
                "by_category": by_category,
                "by_status": by_status
            }

    async def update_insight_status(
        self,
        insight_id: UUID,
        status: str,
        resolved_by: Optional[UUID] = None,
        resolution_notes: Optional[str] = None
    ) -> Optional[Insight]:
        """Update insight workflow status."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(Insight).where(Insight.id == insight_id)
            )
            insight = result.scalar_one_or_none()

            if not insight:
                return None

            insight.status = status
            insight.modified_on = datetime.now(UTC)

            if status == InsightStatus.RESOLVED:
                insight.resolved_at = datetime.now(UTC)
                insight.resolved_by = resolved_by
            if resolution_notes:
                insight.resolution_notes = resolution_notes

            session.add(insight)
            await session.commit()
            await session.refresh(insight)

            return insight


# Singleton instance
insight_service = InsightService()
