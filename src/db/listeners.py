from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapper
from sqlmodel import SQLModel


@event.listens_for(SQLModel, "before_update", propagate=True)
def update_modified_on(mapper: Mapper, connection: Connection, target):
    if hasattr(target, "modified_on"):
        target.modified_on = datetime.now(timezone.utc)
