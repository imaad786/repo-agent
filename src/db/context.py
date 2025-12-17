from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlmodel.ext.asyncio.session import AsyncSession
from contextlib import asynccontextmanager
import logging
from typing import Optional

from src import settings


class DbContext:
    __engine__: Optional[AsyncEngine] = None
    __session_maker__ = None

    @staticmethod
    def initialize():
        if DbContext.__engine__ is None:
            DbContext.__engine__ = create_async_engine(
                settings.database_url,
                echo=False,                    # If True, logs all SQL statements (debugging only)
                pool_size=10,                  # Number of connections kept open in the pool
                max_overflow=20,               # Extra connections allowed beyond pool_size
                pool_timeout=30,               # Seconds to wait before giving up if pool is full
                pool_recycle=1800,             # Seconds after which a connection is recycled (30 minutes)
                pool_pre_ping=True,            # Tests connections before using them
                pool_use_lifo=True,            # Use LIFO instead of FIFO for better connection reuse
            )

            DbContext.__session_maker__ = sessionmaker(
                bind=DbContext.__engine__,
                class_=AsyncSession,
                expire_on_commit=False,        # Keeps objects "live" after commit
                autoflush=False,               # Don't auto-flush before queries
                autocommit=False,              # Explicit transaction control
            )

    @staticmethod
    def get_engine() -> AsyncEngine:
        DbContext.initialize()
        return DbContext.__engine__

    @staticmethod
    @asynccontextmanager
    async def get_session_async():
        DbContext.initialize()
        session: AsyncSession = DbContext.__session_maker__()
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logging.exception("Database session error occurred")
            raise
        finally:
            await session.close()

    @staticmethod
    async def dispose_engine():
        """Dispose of the engine and close all connections. Useful for shutdown."""
        if DbContext.__engine__ is not None:
            await DbContext.__engine__.dispose()
            DbContext.__engine__ = None
            DbContext.__session_maker__ = None
