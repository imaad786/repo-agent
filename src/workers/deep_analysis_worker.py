"""
Background worker for deep analysis processing.

Polls the database for pending analysis runs and processes them.
Similar to IndexingWorker in TZ-AI-Indexer-SVC.
"""
import asyncio
import uuid
from typing import Optional
import logging

from ..services import deep_analysis_service, deep_insight_service
from ..entities import DeepAnalysisRun, DeepAnalysisRunStatus

logger = logging.getLogger(__name__)

# Default poll interval in seconds
DEFAULT_POLL_INTERVAL = 5


class DeepAnalysisWorker:
    """
    Background worker that polls for pending deep analysis runs.

    Flow:
    1. Poll database for pending runs (status='pending', worker_id=NULL)
    2. Lock the run (set worker_id and locked_at)
    3. Process the run (call orchestrator stub)
    4. Update status to completed/failed
    5. Unlock the run
    6. Repeat
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: Optional[int] = None
    ):
        self.worker_id = worker_id or f"deep-worker-{uuid.uuid4().hex[:8]}"
        self.poll_interval = poll_interval or DEFAULT_POLL_INTERVAL
        self._running = False
        self._current_run_id: Optional[uuid.UUID] = None
        self._shutdown_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_run_id(self) -> Optional[uuid.UUID]:
        return self._current_run_id

    async def start(self) -> None:
        """
        Main polling loop.

        Runs until stop() is called or cancelled.
        """
        self._running = True
        logger.info(f"DeepAnalysisWorker {self.worker_id} started (poll_interval={self.poll_interval}s)")

        while self._running:
            try:
                # Check for shutdown signal
                if self._shutdown_event.is_set():
                    break

                # Try to get next pending run
                run = await deep_analysis_service.get_next_pending_run(self.worker_id)

                if run:
                    self._current_run_id = run.id
                    logger.info(f"Processing run {run.id} with categories {run.categories}")

                    try:
                        await self._process_run(run)
                    except Exception as e:
                        logger.exception(f"Error processing run {run.id}: {e}")
                        await deep_analysis_service.update_run_status(
                            run.id,
                            status=DeepAnalysisRunStatus.FAILED,
                            error_message=str(e)
                        )
                    finally:
                        # Always unlock the run
                        await deep_analysis_service.unlock_run(run.id)
                        self._current_run_id = None
                else:
                    # No pending runs, wait before polling again
                    try:
                        await asyncio.wait_for(
                            self._shutdown_event.wait(),
                            timeout=self.poll_interval
                        )
                    except asyncio.TimeoutError:
                        pass  # Normal timeout, continue polling

            except asyncio.CancelledError:
                logger.info(f"Worker {self.worker_id} cancelled")
                break
            except Exception as e:
                logger.exception(f"Unexpected worker error: {e}")
                # Sleep before retrying to avoid tight error loops
                await asyncio.sleep(self.poll_interval)

        logger.info(f"DeepAnalysisWorker {self.worker_id} stopped")

    async def stop(self) -> None:
        """
        Signal the worker to stop gracefully.

        Sets the running flag to False and signals the shutdown event.
        Current run (if any) will complete before stopping.
        """
        logger.info(f"Stopping worker {self.worker_id}...")
        self._running = False
        self._shutdown_event.set()

    async def _process_run(self, run: DeepAnalysisRun) -> None:
        """
        Process a single analysis run.

        1. Update status to RUNNING
        2. Execute analysis (stub for now)
        3. Store insights
        4. Update status to COMPLETED
        """
        # Update status to running
        await deep_analysis_service.update_run_status(
            run.id,
            status=DeepAnalysisRunStatus.RUNNING
        )

        # Execute analysis (stub for now)
        result = await self._execute_analysis_stub(run)

        # Store insights
        for insight_data in result.get("insights", []):
            await deep_insight_service.create_insight(
                task_id=run.task_id,
                analysis_run_id=run.id,
                **insight_data
            )

        # Update run as completed with summary
        await deep_analysis_service.update_run_status(
            run.id,
            status=DeepAnalysisRunStatus.COMPLETED,
            insights_summary=result.get("summary", {})
        )

        logger.info(f"Run {run.id} completed successfully")

    async def _execute_analysis_stub(self, run: DeepAnalysisRun) -> dict:
        """
        STUB: Placeholder for real orchestrator.

        This method will be replaced with actual orchestrator call
        when the deep agent work is completed.

        TODO: Replace with:
            from src.agent.deep_analysis.orchestrator import orchestrator
            await orchestrator.execute_analysis(
                run_id=run.id,
                task_id=run.task_id,
                user_id=run.user_id,
                categories=run.categories,
                execution_mode=run.execution_mode
            )
        """
        logger.info(f"[STUB] Executing analysis for run {run.id}")
        logger.info(f"[STUB] Task ID: {run.task_id}")
        logger.info(f"[STUB] Categories: {run.categories}")
        logger.info(f"[STUB] Execution mode: {run.execution_mode}")

        # Simulate processing time (2 seconds per category)
        total_time = len(run.categories) * 2
        logger.info(f"[STUB] Simulating {total_time}s of processing...")
        await asyncio.sleep(total_time)

        # Generate stub insights for each category
        insights = []
        for category in run.categories:
            insights.append({
                "category": category,
                "severity": "info",
                "title": f"[STUB] {category.replace('_', ' ').title()} Analysis Complete",
                "description": (
                    f"This is a placeholder insight for {category} analysis. "
                    f"Task ID: {run.task_id}. "
                    f"Replace with actual agent output when orchestrator is implemented."
                ),
                "recommended_action": "Implement real orchestrator integration",
                "details": {
                    "stub": True,
                    "category": category,
                    "run_id": str(run.id)
                }
            })

        # Build summary
        summary = {
            "total": len(insights),
            "by_severity": {"info": len(insights)},
            "by_category": {cat: 1 for cat in run.categories}
        }

        logger.info(f"[STUB] Generated {len(insights)} stub insights")

        return {"insights": insights, "summary": summary}


class DeepAnalysisWorkerManager:
    """
    Manages the lifecycle of the DeepAnalysisWorker.

    Integrates with FastAPI lifespan events.
    """

    def __init__(self):
        self._worker: Optional[DeepAnalysisWorker] = None
        self._worker_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.is_running

    async def start(self, poll_interval: Optional[int] = None) -> None:
        """Start the background worker as an asyncio task."""
        if self._worker is not None:
            logger.warning("Deep analysis worker already started")
            return

        self._worker = DeepAnalysisWorker(poll_interval=poll_interval)
        self._worker_task = asyncio.create_task(
            self._worker.start(),
            name="deep_analysis_worker"
        )
        logger.info("Deep analysis worker manager started")

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the background worker gracefully.

        Waits up to `timeout` seconds for the worker to finish,
        then cancels if still running.
        """
        if self._worker is None:
            return

        logger.info("Stopping deep analysis worker manager...")

        # Signal worker to stop
        await self._worker.stop()

        # Wait for worker task to complete
        if self._worker_task:
            try:
                await asyncio.wait_for(self._worker_task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(
                    f"Worker did not stop within {timeout}s, cancelling..."
                )
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

        self._worker = None
        self._worker_task = None
        logger.info("Deep analysis worker manager stopped")


# Global singleton instance
deep_analysis_worker_manager = DeepAnalysisWorkerManager()


# Convenience functions for lifespan integration
async def start_deep_analysis_worker(poll_interval: Optional[int] = None) -> None:
    """Start the global worker manager."""
    await deep_analysis_worker_manager.start(poll_interval=poll_interval)


async def stop_deep_analysis_worker() -> None:
    """Stop the global worker manager."""
    await deep_analysis_worker_manager.stop()
