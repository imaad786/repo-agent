"""
Background worker for analysis processing.

Polls the database for pending analysis runs and processes them
by invoking specialized agents with predefined queries.
"""
import asyncio
import uuid
from typing import Optional, List, Dict, Any
import logging

from ..services import (
    analysis_service,
    insight_service,
    agent_session_service,
    agent_chat_service
)
from ..services.analysis_query_service import analysis_query_service
from ..entities import AnalysisRun, AnalysisRunStatus
from ..agent.agent_types import AgentType
from ..agent.insight_parser import parse_insights, extract_insights_summary

logger = logging.getLogger(__name__)

# Default poll interval in seconds
DEFAULT_POLL_INTERVAL = 5


class AnalysisWorker:
    """
    Background worker that polls for pending analysis runs.

    Flow:
    1. Poll database for pending runs (status='pending', worker_id=NULL)
    2. Lock the run (set worker_id and locked_at)
    3. For each category in the run:
       a. Create a chat session
       b. Get the analysis query from DB
       c. Invoke the specialized agent
       d. Parse insights from response
       e. Save insights to DB
       f. Link session to run
    4. Update status to completed/failed
    5. Unlock the run
    6. Repeat
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        poll_interval: Optional[int] = None
    ):
        self.worker_id = worker_id or f"analysis-worker-{uuid.uuid4().hex[:8]}"
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
        logger.info(f"AnalysisWorker {self.worker_id} started (poll_interval={self.poll_interval}s)")

        while self._running:
            try:
                # Check for shutdown signal
                if self._shutdown_event.is_set():
                    break

                # Try to get next pending run
                run = await analysis_service.get_next_pending_run(self.worker_id)

                if run:
                    self._current_run_id = run.id
                    logger.info(f"Processing run {run.id} with categories {run.categories}")

                    try:
                        await self._process_run(run)
                    except Exception as e:
                        logger.exception(f"Error processing run {run.id}: {e}")
                        await analysis_service.update_run_status(
                            run.id,
                            status=AnalysisRunStatus.FAILED,
                            error_message=str(e)
                        )
                    finally:
                        # Always unlock the run
                        await analysis_service.unlock_run(run.id)
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

        logger.info(f"AnalysisWorker {self.worker_id} stopped")

    async def stop(self) -> None:
        """
        Signal the worker to stop gracefully.

        Sets the running flag to False and signals the shutdown event.
        Current run (if any) will complete before stopping.
        """
        logger.info(f"Stopping worker {self.worker_id}...")
        self._running = False
        self._shutdown_event.set()

    async def _process_run(self, run: AnalysisRun) -> None:
        """
        Process a single analysis run.

        1. Update status to RUNNING
        2. For each category, invoke specialized agent
        3. Parse and store insights
        4. Update status to COMPLETED
        """
        # Update status to running
        await analysis_service.update_run_status(
            run.id,
            status=AnalysisRunStatus.RUNNING
        )

        all_insights: List[Dict[str, Any]] = []
        category_results: Dict[str, Any] = {}

        # Run all categories in parallel
        tasks = [
            self._process_category(run, category)
            for category in run.categories
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for category, result in zip(run.categories, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing category {category}: {result}")
                category_results[category] = {"error": str(result), "insights_count": 0}
            else:
                insights, session_id = result
                all_insights.extend(insights)
                category_results[category] = {
                    "session_id": str(session_id),
                    "insights_count": len(insights)
                }

        # Build summary
        summary = extract_insights_summary(all_insights)
        summary["by_category_details"] = category_results

        # Update run as completed with summary
        await analysis_service.update_run_status(
            run.id,
            status=AnalysisRunStatus.COMPLETED,
            insights_summary=summary
        )

        logger.info(f"Run {run.id} completed: {len(all_insights)} total insights")

    async def _process_category(
        self,
        run: AnalysisRun,
        category: str
    ) -> tuple[List[Dict[str, Any]], uuid.UUID]:
        """
        Process a single category within a run.

        1. Create a chat session for this category
        2. Get the analysis query from DB
        3. Invoke the specialized agent
        4. Parse insights from response
        5. Save insights to DB
        6. Link session to run

        Returns:
            Tuple of (insights list, session_id)
        """
        logger.info(f"Processing category {category} for run {run.id}")

        # Map category to agent type
        try:
            agent_type = AgentType(category)
        except ValueError:
            # Fall back to general if category doesn't match
            logger.warning(f"Unknown category {category}, falling back to general")
            agent_type = AgentType.GENERAL

        # Create a chat session for this analysis
        session = await agent_session_service.create_session(
            user_id=run.user_id,
            task_id=run.task_id,
            agent_type=agent_type.value,
            title=f"{category.replace('_', ' ').title()} Analysis"
        )

        logger.info(f"Created session {session.id} for category {category}")

        # Get the analysis query from DB
        query_record = await analysis_query_service.get_default_query(category)

        if not query_record:
            # Fallback to general query
            query_record = await analysis_query_service.get_default_query("general")

        if not query_record:
            raise ValueError(f"No analysis query found for category {category}")

        query_text = query_record.query_text
        expected_format = query_record.expected_output_format

        # Invoke the agent via chat service (saves messages with is_analysis_query=True)
        logger.info(f"Invoking {agent_type.value} agent for analysis")

        try:
            result = await agent_chat_service.post_message(
                user_id=run.user_id,
                session_id=session.id,
                message=query_text,
                model_id=None,  # Use default model
                task_id=str(run.task_id),
                repo_namespace=run.repo_namespace,
                agent_type=agent_type.value,
                is_analysis_query=True
            )

            content = result["assistant_message"]["message"].get("content", "")
            model_used = result["assistant_message"].get("meta_data", {}).get("usage_metadata", {}).get("model_name")

        except Exception as e:
            logger.error(f"Agent invocation failed for {category}: {e}")
            raise

        # Parse insights from the response
        insights = parse_insights(content, category, expected_format)

        logger.info(f"Parsed {len(insights)} insights from {category} analysis")

        # Save insights to database
        if insights:
            await insight_service.create_insights_batch(
                task_id=run.task_id,
                analysis_run_id=run.id,
                insights=insights,
                agent_model=model_used
            )

        # Link the session to the run
        await analysis_service.link_session(
            run_id=run.id,
            session_id=session.id,
            category=category
        )

        return insights, session.id


class AnalysisWorkerManager:
    """
    Manages the lifecycle of the AnalysisWorker.

    Integrates with FastAPI lifespan events.
    """

    def __init__(self):
        self._worker: Optional[AnalysisWorker] = None
        self._worker_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        return self._worker is not None and self._worker.is_running

    async def start(self, poll_interval: Optional[int] = None) -> None:
        """Start the background worker as an asyncio task."""
        if self._worker is not None:
            logger.warning("Analysis worker already started")
            return

        self._worker = AnalysisWorker(poll_interval=poll_interval)
        self._worker_task = asyncio.create_task(
            self._worker.start(),
            name="analysis_worker"
        )
        logger.info("Analysis worker manager started")

    async def stop(self, timeout: float = 30.0) -> None:
        """
        Stop the background worker gracefully.

        Waits up to `timeout` seconds for the worker to finish,
        then cancels if still running.
        """
        if self._worker is None:
            return

        logger.info("Stopping analysis worker manager...")

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
        logger.info("Analysis worker manager stopped")


# Global singleton instance
analysis_worker_manager = AnalysisWorkerManager()


# Convenience functions for lifespan integration
async def start_analysis_worker(poll_interval: Optional[int] = None) -> None:
    """Start the global worker manager."""
    await analysis_worker_manager.start(poll_interval=poll_interval)


async def stop_analysis_worker() -> None:
    """Stop the global worker manager."""
    await analysis_worker_manager.stop()
