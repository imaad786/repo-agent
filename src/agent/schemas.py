from typing import Optional

from pydantic import BaseModel


class ContextSchema(BaseModel):
    user_id: str
    repo_namespace: str
    model_id: Optional[str]
    memories_injected: bool = False
