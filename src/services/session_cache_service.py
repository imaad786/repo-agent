"""
Local cache service for session data with TTL support.
Provides caching for session lookups to avoid repeated database queries.
"""
import asyncio
import logging
from datetime import datetime, UTC
from dataclasses import dataclass
from typing import Optional, Dict
from uuid import UUID

logger = logging.getLogger(__name__)

# Default cache TTL in seconds (5 minutes)
DEFAULT_CACHE_TTL_SECONDS = 300

# Default cleanup interval in seconds (1 minute)
DEFAULT_CLEANUP_INTERVAL_SECONDS = 30


@dataclass
class CachedSessionData:
    """Cached session data with task_id and repo_namespace."""
    session_id: UUID
    user_id: UUID
    task_id: UUID
    repo_namespace: Optional[str]
    cached_at: datetime
    ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS

    def is_expired(self) -> bool:
        """Check if the cached entry has expired."""
        elapsed = (datetime.now(UTC) - self.cached_at).total_seconds()
        return elapsed >= self.ttl_seconds


class SessionCacheService:
    """
    In-memory cache service for session data.

    Caches session information (task_id, repo_namespace) by session_id
    with a configurable TTL (default: 5 minutes).

    This reduces database lookups for frequently accessed sessions during
    chat interactions.

    Supports background cleanup of expired entries without blocking the main thread.
    """

    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        cleanup_interval_seconds: int = DEFAULT_CLEANUP_INTERVAL_SECONDS
    ):
        """
        Initialize the cache service.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds (default: 300 = 5 minutes)
            cleanup_interval_seconds: Interval for background cleanup (default: 60 = 1 minute)
        """
        self._cache: Dict[UUID, CachedSessionData] = {}
        self._ttl_seconds = ttl_seconds
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        logger.info(f"SessionCacheService initialized with TTL: {ttl_seconds}s, cleanup interval: {cleanup_interval_seconds}s")

    def get(self, session_id: UUID) -> Optional[CachedSessionData]:
        """
        Get cached session data by session_id.

        Args:
            session_id: The session UUID to look up

        Returns:
            CachedSessionData if found and not expired, None otherwise
        """
        cached = self._cache.get(session_id)

        if cached is None:
            logger.debug(f"Cache miss for session {session_id}")
            return None

        if cached.is_expired():
            logger.debug(f"Cache expired for session {session_id}")
            self._cache.pop(session_id, None)
            return None

        logger.debug(f"Cache hit for session {session_id}")
        return cached

    def set(
        self,
        session_id: UUID,
        user_id: UUID,
        task_id: UUID,
        repo_namespace: Optional[str]
    ) -> CachedSessionData:
        """
        Cache session data.

        Args:
            session_id: The session UUID
            user_id: The user UUID
            task_id: The task UUID for data isolation
            repo_namespace: Optional repository namespace

        Returns:
            The cached session data
        """
        cached = CachedSessionData(
            session_id=session_id,
            user_id=user_id,
            task_id=task_id,
            repo_namespace=repo_namespace,
            cached_at=datetime.now(UTC),
            ttl_seconds=self._ttl_seconds
        )
        self._cache[session_id] = cached
        logger.debug(f"Cached session data for session {session_id}")
        return cached

    def invalidate(self, session_id: UUID) -> bool:
        """
        Remove a session from the cache.

        Args:
            session_id: The session UUID to invalidate

        Returns:
            True if the session was in cache and removed, False otherwise
        """
        removed = self._cache.pop(session_id, None) is not None
        if removed:
            logger.debug(f"Invalidated cache for session {session_id}")
        return removed

    def clear(self) -> int:
        """
        Clear all cached entries.

        Returns:
            Number of entries cleared
        """
        count = len(self._cache)
        self._cache.clear()
        logger.info(f"Cleared {count} entries from session cache")
        return count

    def cleanup_expired(self) -> int:
        """
        Remove all expired entries from the cache.

        Returns:
            Number of expired entries removed
        """
        expired_keys = [
            session_id for session_id, cached in self._cache.items()
            if cached.is_expired()
        ]

        for key in expired_keys:
            self._cache.pop(key, None)

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)

    def validate_task_id(self, cached: CachedSessionData, provided_task_id: UUID) -> bool:
        """
        Validate that the provided task_id matches the cached session's task_id.

        Args:
            cached: The cached session data
            provided_task_id: The task_id from the request

        Returns:
            True if task_ids match, False otherwise
        """
        return cached.task_id == provided_task_id

    @property
    def size(self) -> int:
        """Return the current number of cached entries."""
        return len(self._cache)

    # Background operations

    def invalidate_background(self, session_id: UUID) -> None:
        """
        Remove a session from the cache in the background (non-blocking).

        Args:
            session_id: The session UUID to invalidate
        """
        try:
            loop = asyncio.get_running_loop()
            loop.call_soon(self._do_invalidate, session_id)
        except RuntimeError:
            # No running event loop, fall back to sync invalidation
            self._do_invalidate(session_id)

    def _do_invalidate(self, session_id: UUID) -> None:
        """Internal method to perform invalidation."""
        removed = self._cache.pop(session_id, None) is not None
        if removed:
            logger.debug(f"Invalidated cache for session {session_id} (background)")

    async def start_background_cleanup(self) -> None:
        """
        Start the background cleanup task that periodically removes expired entries.
        Should be called during application startup.
        """
        if self._running:
            logger.warning("Background cleanup already running")
            return

        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Started background cache cleanup task")

    async def stop_background_cleanup(self) -> None:
        """
        Stop the background cleanup task.
        Should be called during application shutdown.
        """
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            logger.info("Stopped background cache cleanup task")

    async def _cleanup_loop(self) -> None:
        """Background loop that periodically cleans up expired cache entries."""
        while self._running:
            try:
                await asyncio.sleep(self._cleanup_interval)
                if self._running:
                    count = self.cleanup_expired()
                    if count > 0:
                        logger.info(f"Background cleanup removed {count} expired cache entries")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in background cleanup: {e}")
                # Continue running despite errors


# Singleton instance
session_cache_service = SessionCacheService()
