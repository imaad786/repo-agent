"""
Pydantic schemas for agent API routes.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# Request Schemas

class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""
    title: Optional[str] = Field(None, max_length=500, description="Session title")
    task_id: UUID = Field(..., description="Task UUID identifying the indexing task for data isolation")
    repo_namespace: Optional[str] = Field(None, max_length=500, description="Repository namespace (e.g., 'org/repo') - optional for additional filtering/metadata")

    @field_validator('repo_namespace')
    @classmethod
    def validate_repo_namespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip() if v.strip() else None
        return v


class UpdateSessionRequest(BaseModel):
    """Request to update a chat session."""
    title: Optional[str] = Field(None, max_length=500, description="New session title")
    status: Optional[str] = Field(None, description="New session status (ACTIVE, ARCHIVED, ENDED)")

    @field_validator('status')
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        if v and v not in ["ACTIVE", "ARCHIVED", "ENDED"]:
            raise ValueError("status must be one of: ACTIVE, ARCHIVED, ENDED")
        return v


class ChatRequest(BaseModel):
    """Request to send a message to the agent."""
    message: str = Field(..., min_length=1, description="User message")
    model_id: str = Field(..., description="LLM model identifier (e.g., 'openai:gpt-4', 'anthropic:claude-3-5-sonnet-20241022')")
    task_id: UUID = Field(..., description="Task UUID identifying the indexing task for data isolation")
    repo_namespace: Optional[str] = Field(None, max_length=500, description="Repository namespace for context - optional for additional filtering/metadata")

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("message cannot be empty")
        return v.strip()

    @field_validator('model_id')
    @classmethod
    def validate_model_id(cls, v: str) -> str:
        if not v or ":" not in v:
            raise ValueError("model_id must be in format 'provider:model-name' (e.g., 'openai:gpt-4')")

        provider = v.split(":", 1)[0].lower()
        if provider not in ["openai", "anthropic", "google_genai"]:
            raise ValueError(f"Unsupported provider: {provider}. Supported: openai, anthropic, google")

        return v

    @field_validator('repo_namespace')
    @classmethod
    def validate_repo_namespace(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return v.strip() if v.strip() else None
        return v


# Response Schemas

class SessionResponse(BaseModel):
    """Response for a chat session."""
    id: UUID
    user_id: UUID
    title: Optional[str]
    task_id: UUID
    repo_namespace: Optional[str]
    status: str
    created_on: datetime
    modified_on: datetime

    class Config:
        from_attributes = True


class MessageResponse(BaseModel):
    """Response for a chat message."""
    id: str
    role: str
    message: Dict[str, Any]
    artifacts: Optional[Dict[str, Any]] = None
    meta_data: Optional[Dict[str, Any]] = None
    message_order: int
    created_on: Optional[str] = None


class ChatResponse(BaseModel):
    """Response for a chat interaction."""
    session_id: str
    user_message: MessageResponse
    assistant_message: MessageResponse


class SessionListResponse(BaseModel):
    """Response for list of sessions."""
    sessions: List[SessionResponse]
    total: int
    limit: int
    offset: int


class MessageListResponse(BaseModel):
    """Response for list of messages."""
    messages: List[MessageResponse]
    total: int
    limit: int
    offset: int


class StreamChunk(BaseModel):
    """Stream chunk for server-sent events."""
    type: str = Field(..., description="Chunk type: content, tool_call, metadata, error")
    content: Optional[str] = Field(None, description="Content chunk (for type=content)")
    tool_calls: Optional[List[Dict[str, Any]]] = Field(None, description="Tool calls (for type=tool_call)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata (for type=metadata)")
    error: Optional[str] = Field(None, description="Error message (for type=error)")


class ErrorResponse(BaseModel):
    """Error response."""
    detail: str
    error_code: Optional[str] = None
