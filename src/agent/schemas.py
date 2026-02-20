from typing import Optional

from pydantic import BaseModel


class ContextSchema(BaseModel):
    user_id: str
    task_id: str  # Required: UUID identifying the indexing task for data isolation
    repo_namespace: Optional[str] = None  # Optional: Repository URL for additional filtering/metadata
    model_id: Optional[str] = None
    memories_injected: bool = False
    is_analysis_followup: bool = False  # True when this is a follow-up question on an analysis session
    routed_domain: Optional[str] = None  # Orchestrator: domain classified by the router (e.g., "security", "database")
