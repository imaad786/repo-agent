"""
Service for managing analysis runs.
"""
import logging
from datetime import datetime, UTC
from typing import List, Optional, Dict
from uuid import UUID

from sqlmodel import select, and_

from ..db.context import DbContext
from ..entities import AnalysisRun, AnalysisRunStatus, AnalysisSession

logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for managing analysis runs."""

    # ─────────────────────────────────────────────────────────────────
    # CRUD Operations
    # ─────────────────────────────────────────────────────────────────

    async def create_run(
        self,
        task_id: UUID,
        user_id: UUID,
        categories: List[str],
        repo_namespace: Optional[str] = None,
        triggered_by: Optional[str] = None
    ) -> AnalysisRun:
        """Create a new analysis run."""
        async with DbContext.get_session_async() as session:
            run = AnalysisRun(
                task_id=task_id,
                user_id=user_id,
                repo_namespace=repo_namespace,
                categories=categories,
                triggered_by=triggered_by,
                status=AnalysisRunStatus.PENDING
            )
            session.add(run)
            await session.commit()
            await session.refresh(run)
            logger.info(f"Created analysis run {run.id} for task {task_id}")
            return run

    async def get_run(self, run_id: UUID) -> Optional[AnalysisRun]:
        """Get analysis run by ID."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisRun).where(
                    and_(
                        AnalysisRun.id == run_id,
                        AnalysisRun.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()

    async def list_runs(
        self,
        task_id: Optional[UUID] = None,
        user_id: Optional[UUID] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[AnalysisRun]:
        """List analysis runs with filters."""
        async with DbContext.get_session_async() as session:
            query = select(AnalysisRun).where(
                AnalysisRun.is_deleted == False
            )

            if task_id:
                query = query.where(AnalysisRun.task_id == task_id)
            if user_id:
                query = query.where(AnalysisRun.user_id == user_id)
            if status:
                query = query.where(AnalysisRun.status == status)

            query = query.order_by(AnalysisRun.created_on.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            return list(result.scalars().all())

    # ─────────────────────────────────────────────────────────────────
    # Worker Locking
    # ─────────────────────────────────────────────────────────────────

    async def get_next_pending_run(self, worker_id: str) -> Optional[AnalysisRun]:
        """
        Get and lock the next pending run.

        Uses optimistic locking - finds oldest pending run with
        worker_id = NULL and atomically assigns this worker.
        """
        async with DbContext.get_session_async() as session:
            # Find oldest pending, unlocked run
            query = select(AnalysisRun).where(
                and_(
                    AnalysisRun.status == AnalysisRunStatus.PENDING,
                    AnalysisRun.is_deleted == False,
                    AnalysisRun.worker_id == None
                )
            ).order_by(AnalysisRun.created_on).limit(1)

            result = await session.execute(query)
            run = result.scalar_one_or_none()

            if not run:
                return None

            # Lock the run
            run.worker_id = worker_id
            run.locked_at = datetime.now(UTC)
            run.modified_on = datetime.now(UTC)

            session.add(run)
            await session.commit()
            await session.refresh(run)

            logger.info(f"Worker {worker_id} locked run {run.id}")
            return run

    async def unlock_run(self, run_id: UUID) -> None:
        """Clear worker lock after processing."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisRun).where(AnalysisRun.id == run_id)
            )
            run = result.scalar_one_or_none()

            if run:
                run.worker_id = None
                run.locked_at = None
                run.modified_on = datetime.now(UTC)
                session.add(run)
                await session.commit()
                logger.debug(f"Unlocked run {run_id}")

    # ─────────────────────────────────────────────────────────────────
    # Status Updates
    # ─────────────────────────────────────────────────────────────────

    async def update_run_status(
        self,
        run_id: UUID,
        status: str,
        error_message: Optional[str] = None,
        insights_summary: Optional[Dict] = None
    ) -> Optional[AnalysisRun]:
        """Update run status with optional error/summary."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisRun).where(AnalysisRun.id == run_id)
            )
            run = result.scalar_one_or_none()

            if not run:
                return None

            run.status = status
            run.modified_on = datetime.now(UTC)

            # Set timing based on status
            if status == AnalysisRunStatus.RUNNING and not run.started_at:
                run.started_at = datetime.now(UTC)
            elif status in [AnalysisRunStatus.COMPLETED,
                           AnalysisRunStatus.FAILED,
                           AnalysisRunStatus.CANCELLED]:
                run.completed_at = datetime.now(UTC)

            if error_message is not None:
                run.error_message = error_message
            if insights_summary is not None:
                run.insights_summary = insights_summary

            session.add(run)
            await session.commit()
            await session.refresh(run)

            logger.info(f"Updated run {run_id} status to {status}")
            return run

    async def cancel_run(self, run_id: UUID) -> Optional[AnalysisRun]:
        """Cancel a pending or running analysis."""
        return await self.update_run_status(
            run_id,
            status=AnalysisRunStatus.CANCELLED
        )

    # ─────────────────────────────────────────────────────────────────
    # Session Linking
    # ─────────────────────────────────────────────────────────────────

    async def link_session(
        self,
        run_id: UUID,
        session_id: UUID,
        category: str
    ) -> AnalysisSession:
        """Link a chat session to an analysis run."""
        async with DbContext.get_session_async() as session:
            link = AnalysisSession(
                analysis_run_id=run_id,
                chat_session_id=session_id,
                category=category
            )
            session.add(link)
            await session.commit()
            await session.refresh(link)
            logger.info(f"Linked session {session_id} to run {run_id} for {category}")
            return link

    async def get_sessions_for_run(self, run_id: UUID) -> List[AnalysisSession]:
        """Get all sessions linked to a run."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisSession).where(
                    and_(
                        AnalysisSession.analysis_run_id == run_id,
                        AnalysisSession.is_deleted == False
                    )
                )
            )
            return list(result.scalars().all())


# Singleton instance
analysis_service = AnalysisService()
