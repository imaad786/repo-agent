"""
Analysis query entity for storing configurable analysis queries.
"""
from typing import Optional, Dict

from sqlmodel import Field, Column
from sqlalchemy.dialects.postgresql import JSONB

from .base import BaseEntityMixin
from ..utils.settings import settings


class OutputFormat:
    """Expected output formats for analysis queries."""
    JSON = "json"
    TEXT = "text"
    MARKDOWN = "markdown"


class AnalysisQuery(BaseEntityMixin, table=True):
    """
    Represents a configurable analysis query for a specific category.

    Queries are stored in the database so they can be modified without
    code changes. Each category can have multiple queries with different
    priorities - the default query with highest priority is used for
    background analysis.
    """
    __tablename__ = "analysis_queries"
    __table_args__ = {"schema": settings.database_schema}

    # Category (maps to agent type)
    category: str = Field(max_length=50, index=True)

    # Query identification
    name: str = Field(max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)

    # The actual query text sent to the agent
    query_text: str = Field(sa_column=Column("query_text", nullable=False))

    # Configuration
    is_default: bool = Field(default=True)
    priority: int = Field(default=0)

    # Output format hints for the parser
    expected_output_format: str = Field(default=OutputFormat.JSON, max_length=50)
    output_schema: Optional[Dict] = Field(default=None, sa_column=Column(JSONB))
