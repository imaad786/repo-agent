from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field
from sqlalchemy import DateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BaseEntityMixin(SQLModel, table=False):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)

    is_active: bool = Field(default=True, nullable=False)
    is_deleted: bool = Field(default=False, nullable=False)

    created_on: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    modified_on: datetime = Field(
        default_factory=utcnow,
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
