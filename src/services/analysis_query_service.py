"""
Service for managing analysis queries.
"""
import logging
from datetime import datetime, UTC
from typing import List, Optional
from uuid import UUID

from sqlmodel import select, and_, desc

from ..db.context import DbContext
from ..entities.analysis_query import AnalysisQuery

logger = logging.getLogger(__name__)


class AnalysisQueryService:
    """Service for managing configurable analysis queries."""

    async def get_default_query(self, category: str) -> Optional[AnalysisQuery]:
        """
        Get the default query for a category.

        Returns the highest priority default query for the category.
        """
        async with DbContext.get_session_async() as session:
            query = select(AnalysisQuery).where(
                and_(
                    AnalysisQuery.category == category,
                    AnalysisQuery.is_default == True,
                    AnalysisQuery.is_active == True,
                    AnalysisQuery.is_deleted == False
                )
            ).order_by(desc(AnalysisQuery.priority)).limit(1)

            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def get_queries_by_category(
        self,
        category: str,
        include_inactive: bool = False
    ) -> List[AnalysisQuery]:
        """Get all queries for a category."""
        async with DbContext.get_session_async() as session:
            conditions = [
                AnalysisQuery.category == category,
                AnalysisQuery.is_deleted == False
            ]
            if not include_inactive:
                conditions.append(AnalysisQuery.is_active == True)

            query = select(AnalysisQuery).where(
                and_(*conditions)
            ).order_by(desc(AnalysisQuery.priority))

            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_query(self, query_id: UUID) -> Optional[AnalysisQuery]:
        """Get a specific query by ID."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisQuery).where(
                    and_(
                        AnalysisQuery.id == query_id,
                        AnalysisQuery.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()

    async def get_query_by_name(
        self,
        category: str,
        name: str
    ) -> Optional[AnalysisQuery]:
        """Get a query by category and name."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisQuery).where(
                    and_(
                        AnalysisQuery.category == category,
                        AnalysisQuery.name == name,
                        AnalysisQuery.is_deleted == False
                    )
                )
            )
            return result.scalar_one_or_none()

    async def list_queries(
        self,
        category: Optional[str] = None,
        is_default: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[AnalysisQuery]:
        """List queries with optional filters."""
        async with DbContext.get_session_async() as session:
            query = select(AnalysisQuery).where(
                and_(
                    AnalysisQuery.is_active == True,
                    AnalysisQuery.is_deleted == False
                )
            )

            if category:
                query = query.where(AnalysisQuery.category == category)
            if is_default is not None:
                query = query.where(AnalysisQuery.is_default == is_default)

            query = query.order_by(
                AnalysisQuery.category,
                desc(AnalysisQuery.priority)
            )
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            return list(result.scalars().all())

    async def create_query(
        self,
        category: str,
        name: str,
        query_text: str,
        description: Optional[str] = None,
        is_default: bool = False,
        priority: int = 0,
        expected_output_format: str = "json",
        output_schema: Optional[dict] = None
    ) -> AnalysisQuery:
        """Create a new analysis query."""
        async with DbContext.get_session_async() as session:
            query = AnalysisQuery(
                category=category,
                name=name,
                query_text=query_text,
                description=description,
                is_default=is_default,
                priority=priority,
                expected_output_format=expected_output_format,
                output_schema=output_schema
            )
            session.add(query)
            await session.commit()
            await session.refresh(query)
            logger.info(f"Created analysis query {query.id} for category {category}")
            return query

    async def update_query(
        self,
        query_id: UUID,
        name: Optional[str] = None,
        query_text: Optional[str] = None,
        description: Optional[str] = None,
        is_default: Optional[bool] = None,
        priority: Optional[int] = None,
        expected_output_format: Optional[str] = None,
        output_schema: Optional[dict] = None,
        is_active: Optional[bool] = None
    ) -> Optional[AnalysisQuery]:
        """Update an existing query."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisQuery).where(AnalysisQuery.id == query_id)
            )
            query = result.scalar_one_or_none()

            if not query:
                return None

            if name is not None:
                query.name = name
            if query_text is not None:
                query.query_text = query_text
            if description is not None:
                query.description = description
            if is_default is not None:
                query.is_default = is_default
            if priority is not None:
                query.priority = priority
            if expected_output_format is not None:
                query.expected_output_format = expected_output_format
            if output_schema is not None:
                query.output_schema = output_schema
            if is_active is not None:
                query.is_active = is_active

            query.modified_on = datetime.now(UTC)

            session.add(query)
            await session.commit()
            await session.refresh(query)

            logger.info(f"Updated analysis query {query_id}")
            return query

    async def delete_query(self, query_id: UUID) -> bool:
        """Soft delete a query."""
        async with DbContext.get_session_async() as session:
            result = await session.execute(
                select(AnalysisQuery).where(
                    and_(
                        AnalysisQuery.id == query_id,
                        AnalysisQuery.is_deleted == False
                    )
                )
            )
            query = result.scalar_one_or_none()

            if not query:
                return False

            query.is_deleted = True
            query.modified_on = datetime.now(UTC)

            session.add(query)
            await session.commit()

            logger.info(f"Deleted analysis query {query_id}")
            return True

    async def get_all_categories(self) -> List[str]:
        """Get list of all unique categories with queries."""
        async with DbContext.get_session_async() as session:
            from sqlmodel import distinct
            result = await session.execute(
                select(distinct(AnalysisQuery.category)).where(
                    and_(
                        AnalysisQuery.is_active == True,
                        AnalysisQuery.is_deleted == False
                    )
                )
            )
            return [row[0] for row in result.all()]


# Singleton instance
analysis_query_service = AnalysisQueryService()
