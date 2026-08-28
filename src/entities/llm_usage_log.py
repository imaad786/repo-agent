from typing import Optional
from uuid import UUID

from sqlmodel import Field

from .base import BaseEntityMixin
from ..utils.settings import settings


class LlmUsageLog(BaseEntityMixin, table=True):
    __tablename__ = "llm_usage_logs"
    __table_args__ = {"schema": settings.database_schema}

    user_id: Optional[UUID] = Field(default=None, index=True)
    session_id: Optional[UUID] = Field(default=None, index=True)
    task_id: Optional[UUID] = Field(default=None, index=True)

    model_provider: str = Field(nullable=False, max_length=50)
    model_name: str = Field(nullable=False, max_length=200)

    input_tokens: int = Field(default=0, nullable=False)
    output_tokens: int = Field(default=0, nullable=False)
    total_tokens: int = Field(default=0, nullable=False)

    caller: str = Field(nullable=False, max_length=100, index=True)
