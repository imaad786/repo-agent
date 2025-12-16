from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseEntityMixin(SQLModel, table=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    is_active: bool = Field(default=True, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)

    created_on: datetime = Field(
        default_factory=utcnow,
        # sa_column_kwargs={
        #     "server_default": func.now(),          # DB sets on insert
        # },
        nullable=False,
    )
    modified_on: datetime = Field(
        default_factory=utcnow,
        sa_column_kwargs={
            # "server_default": func.now(),          # initial value on insert
            "onupdate": utcnow,  # DB updates on UPDATE
        },
        nullable=False,
    )
