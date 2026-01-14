"""
API routes for Code Intelligence Agent.
"""
import logging
import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Path
from fastapi.responses import StreamingResponse

from .schemas import (
    CreateSessionRequest,
    UpdateSessionRequest,
    ChatRequest,
    SessionResponse,
    SessionListResponse,
    MessageListResponse,
    ChatResponse,
    MessageResponse,
    ErrorResponse
)
from ...services import agent_session_service, agent_chat_service, session_cache_service
from ...agent.agent_types import AgentType

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/agent/sessions", response_model=SessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    user_id: UUID = Query(..., description="User UUID")
):
    """
    Create a new agent chat session.

    Args:
        request: Session creation request with agent_type
        user_id: User UUID

    Returns:
        Created session
    """
    try:
        session = await agent_session_service.create_session(
            user_id=user_id,
            task_id=request.task_id,
            repo_namespace=request.repo_namespace,
            title=request.title,
            agent_type=request.agent_type,
        )

        # Cache the session data for future chat requests
        session_cache_service.set(
            session_id=session.id,
            user_id=session.user_id,
            task_id=session.task_id,
            repo_namespace=session.repo_namespace,
            agent_type=session.agent_type
        )

        return SessionResponse.model_validate(session)

    except ValueError as e:
        logger.warning(f"Validation error creating session: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.get("/agent/sessions", response_model=SessionListResponse)
async def list_sessions(
    user_id: UUID = Query(..., description="User UUID"),
    status: Optional[str] = Query(None, description="Filter by status (ACTIVE, ARCHIVED, ENDED)"),
    agent_type: Optional[str] = Query(None, description=f"Filter by agent type. Valid types: {AgentType.values()}"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of sessions to return"),
    offset: int = Query(0, ge=0, description="Number of sessions to skip")
):
    """
    List chat sessions for a user.

    Args:
        user_id: User UUID
        status: Optional status filter
        agent_type: Optional agent type filter
        limit: Maximum number of sessions
        offset: Pagination offset

    Returns:
        List of sessions
    """
    try:
        # Validate agent_type if provided
        if agent_type and agent_type not in AgentType.values():
            raise ValueError(f"Invalid agent_type: {agent_type}. Valid types: {AgentType.values()}")

        sessions = await agent_session_service.list_sessions(
            user_id=user_id,
            status=status,
            agent_type=agent_type,
            limit=limit,
            offset=offset
        )

        return SessionListResponse(
            sessions=[SessionResponse.model_validate(s) for s in sessions],
            total=len(sessions),
            limit=limit,
            offset=offset
        )

    except ValueError as e:
        logger.warning(f"Validation error listing sessions: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


@router.get("/agent/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: UUID = Path(..., description="Session UUID")
):
    """
    Get a specific chat session.

    Args:
        session_id: Session UUID

    Returns:
        Session details
    """
    try:
        session = await agent_session_service.get_session(session_id)

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionResponse.model_validate(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get session: {str(e)}")


@router.patch("/agent/sessions/{session_id}", response_model=SessionResponse)
async def update_session(
    request: UpdateSessionRequest,
    session_id: UUID = Path(..., description="Session UUID")
):
    """
    Update a chat session.

    Args:
        request: Update request
        session_id: Session UUID

    Returns:
        Updated session
    """
    try:
        session = await agent_session_service.update_session(
            session_id=session_id,
            title=request.title,
            status=request.status,
        )

        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        return SessionResponse.model_validate(session)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update session: {str(e)}")


@router.delete("/agent/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID = Path(..., description="Session UUID")
):
    """
    Delete (soft) a chat session.

    Args:
        session_id: Session UUID
    """
    try:
        deleted = await agent_session_service.delete_session(session_id)

        if not deleted:
            raise HTTPException(status_code=404, detail="Session not found")

        # Invalidate cache for deleted session (runs in background, non-blocking)
        session_cache_service.invalidate_background(session_id)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")


# Message and Chat Endpoints

@router.get("/agent/sessions/{session_id}/messages", response_model=MessageListResponse)
async def get_messages(
    session_id: UUID = Path(..., description="Session UUID"),
    limit: int = Query(100, ge=1, le=500, description="Maximum number of messages to return"),
    offset: int = Query(0, ge=0, description="Number of messages to skip")
):
    """
    Get conversation messages for a session.

    Args:
        session_id: Session UUID
        limit: Maximum number of messages
        offset: Pagination offset

    Returns:
        List of messages
    """
    try:
        # Verify session exists
        session = await agent_session_service.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        messages = await agent_chat_service.get_messages(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

        return MessageListResponse(
            messages=[MessageResponse(**msg) for msg in messages],
            total=len(messages),
            limit=limit,
            offset=offset
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting messages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get messages: {str(e)}")


@router.post("/agent/sessions/{session_id}/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session_id: UUID = Path(..., description="Session UUID")
):
    """
    Send a message to the agent (synchronous, non-streaming).

    Args:
        request: Chat request with message and model_id
        session_id: Session UUID (used to retrieve user_id, task_id, repo_namespace, agent_type)

    Returns:
        Chat response with user and assistant messages
    """
    try:
        # Try to get session data from cache first
        cached_session = session_cache_service.get(session_id)

        if cached_session:
            user_id = cached_session.user_id
            task_id = str(cached_session.task_id)
            repo_namespace = cached_session.repo_namespace
            agent_type = cached_session.agent_type
        else:
            # Cache miss - fetch from database (no user_id filter needed)
            session = await agent_session_service.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            # Cache the session data for future requests
            session_cache_service.set(
                session_id=session.id,
                user_id=session.user_id,
                task_id=session.task_id,
                repo_namespace=session.repo_namespace,
                agent_type=session.agent_type
            )

            user_id = session.user_id
            task_id = str(session.task_id)
            repo_namespace = session.repo_namespace
            agent_type = session.agent_type

        # Post message to agent (all context extracted from session)
        response = await agent_chat_service.post_message(
            user_id=user_id,
            session_id=session_id,
            message=request.message,
            model_id=request.model_id,
            task_id=task_id,
            repo_namespace=repo_namespace,
            agent_type=agent_type
        )

        return ChatResponse(
            session_id=response["session_id"],
            user_message=MessageResponse(**response["user_message"]),
            assistant_message=MessageResponse(**response["assistant_message"])
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error in chat: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat: {str(e)}")


@router.post("/agent/sessions/{session_id}/chat/stream")
async def chat_stream(
    request: ChatRequest,
    session_id: UUID = Path(..., description="Session UUID")
):
    """
    Send a message to the agent with streaming response (Server-Sent Events).

    Args:
        request: Chat request with message and model_id
        session_id: Session UUID (used to retrieve user_id, task_id, repo_namespace, agent_type)

    Returns:
        Streaming response with SSE chunks containing LLM tokens and agent progress
    """
    try:
        # Try to get session data from cache first
        cached_session = session_cache_service.get(session_id)

        if cached_session:
            user_id = cached_session.user_id
            task_id = str(cached_session.task_id)
            repo_namespace = cached_session.repo_namespace
            agent_type = cached_session.agent_type
        else:
            # Cache miss - fetch from database (no user_id filter needed)
            session = await agent_session_service.get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            # Cache the session data for future requests
            session_cache_service.set(
                session_id=session.id,
                user_id=session.user_id,
                task_id=session.task_id,
                repo_namespace=session.repo_namespace,
                agent_type=session.agent_type
            )

            user_id = session.user_id
            task_id = str(session.task_id)
            repo_namespace = session.repo_namespace
            agent_type = session.agent_type

        async def event_generator():
            """Generate SSE events from agent stream."""
            try:
                # Stream responses from agent (all context from session)
                async for chunk in agent_chat_service.stream_message(
                    user_id=user_id,
                    session_id=session_id,
                    message=request.message,
                    model_id=request.model_id,
                    task_id=task_id,
                    repo_namespace=repo_namespace,
                    agent_type=agent_type
                ):
                    # Format as SSE
                    chunk_json = json.dumps(chunk)
                    yield f"data: {chunk_json}\n\n"

            except Exception as e:
                logger.exception(f"Error in stream: {e}")
                error_event = {
                    "type": "error",
                    "data": {
                        "error": str(e)
                    }
                }
                yield f"data: {json.dumps(error_event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error in chat stream: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"Error in chat stream: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process chat stream: {str(e)}")
