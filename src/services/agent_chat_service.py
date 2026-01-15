import logging
from langchain_core.messages import (
    AIMessageChunk,
    BaseMessageChunk,
    ToolMessage,
    ToolMessageChunk,
    HumanMessage,
    HumanMessageChunk,
    SystemMessage,
    SystemMessageChunk,
    FunctionMessage,
    FunctionMessageChunk,
    ChatMessage,
    ChatMessageChunk
)
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlmodel import select, and_, func

from ..entities import (
    AgentChatMessage,
    AgentChatSessionLastMessageOrder
)
from ..db.context import DbContext
from ..agent.agent_types import AgentType
from ..agent.agent_registry import get_registry


logger = logging.getLogger(__name__)


class AgentChatService:

    @staticmethod
    def _extract_text_content(content) -> str:
        """
        Extract text content from message content.

        Handles both string content (OpenAI) and list content (Anthropic/Google).

        Args:
            content: Message content - can be str, list of dicts, or other

        Returns:
            Extracted text as string
        """
        if content is None:
            return ""
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            # Handle list of content blocks (Anthropic/Google format)
            text_parts = []
            for item in content:
                if isinstance(item, str):
                    text_parts.append(item)
                elif isinstance(item, dict):
                    # Extract text from content block dict
                    if item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif "text" in item:
                        text_parts.append(item.get("text", ""))
            return "".join(text_parts)
        # Fallback: try to convert to string
        return str(content) if content else ""

    async def post_message(
        self,
        user_id: UUID,
        session_id: UUID,
        message: str,
        model_id: Optional[str],
        task_id: str,
        repo_namespace: Optional[str] = None,
        agent_type: str = AgentType.GENERAL.value,
        is_analysis_query: bool = False
    ) -> Dict[str, Any]:
        async with DbContext.get_session_async() as session:
            last_order = await self._get_last_message_order(session, session_id)

            # Get the appropriate agent from registry based on agent_type
            registry = get_registry()
            agent = await registry.get_agent_by_name(agent_type)

            response = await agent.ask(
                user_id=str(user_id),
                session_id=str(session_id),
                message=message,
                model_id=model_id,
                task_id=task_id,
                repo_namespace=repo_namespace
            )

            user_message = AgentChatMessage(
                chat_session_id=session_id,
                role="USER",
                message={
                    "content": message,
                    "model_id": model_id
                },
                message_order=last_order + 1,
                is_analysis_query=is_analysis_query
            )

            assistant_message = AgentChatMessage(
                chat_session_id=session_id,
                role="ASSISTANT",
                message={
                    "content": response["content"],
                    "model_id": model_id
                },
                artifacts={
                    "artifacts": response.get("artifacts", [])
                },
                meta_data={
                    "usage_metadata": response.get("usage_metadata", {}),
                    "raw_messages": response.get("raw_messages", [])
                },
                message_order=last_order + 2,
                is_analysis_query=is_analysis_query
            )

            session.add(user_message)
            session.add(assistant_message)
            await session.commit()
            await session.refresh(user_message)
            await session.refresh(assistant_message)

            await self._update_last_message_order(session, session_id, last_order + 2)
            return {
                "user_message": self._serialize_message(user_message),
                "assistant_message": self._serialize_message(assistant_message),
                "session_id": str(session_id)
            }

    async def stream_message(
        self,
        user_id: UUID,
        session_id: UUID,
        message: str,
        model_id: Optional[str],
        task_id: str,
        repo_namespace: Optional[str] = None,
        agent_type: str = AgentType.GENERAL.value,
        is_analysis_query: bool = False
    ):
        """
        Stream agent responses and save messages to database after completion.

        Yields:
            Stream chunks containing tokens, agent progress, and metadata
        """
        # Get the appropriate agent from registry based on agent_type
        registry = get_registry()
        agent = await registry.get_agent_by_name(agent_type)

        # Accumulate the full response content
        full_content = ""

        # Get initial message order
        async with DbContext.get_session_async() as session:
            last_order = await self._get_last_message_order(session, session_id)

        try:
            # Stream responses from agent
            async for chunk in agent.astream(
                user_id=str(user_id),
                session_id=str(session_id),
                message=message,
                model_id=model_id,
                task_id=task_id,
                repo_namespace=repo_namespace
            ):
                # Agent progress updates - serialize messages in the chunk
                serialized_chunk = {}
                for x in chunk:
                    if isinstance(x, AIMessageChunk):
                        # Streaming AI/LLM response tokens
                        if 'ai_content' not in serialized_chunk:
                            serialized_chunk['ai_content'] = ""

                        # Accumulate content for both full response and chunk
                        # Use helper to handle both str (OpenAI) and list (Anthropic/Google) content
                        if x.content:
                            text_content = self._extract_text_content(x.content)
                            full_content += text_content
                            serialized_chunk['ai_content'] += text_content
                        
                        # Include tool call chunks if AI is invoking tools
                        if hasattr(x, 'tool_call_chunks') and x.tool_call_chunks:
                            if 'tool_call_chunks' not in serialized_chunk:
                                serialized_chunk['tool_call_chunks'] = []
                            serialized_chunk['tool_call_chunks'].extend(
                                self._serialize_tool_call_chunks(x.tool_call_chunks)
                            )
                    
                    elif isinstance(x, (ToolMessage, ToolMessageChunk)):
                        # Tool execution results (both full and chunked)
                        if 'tool_results' not in serialized_chunk:
                            serialized_chunk['tool_results'] = []
                        serialized_chunk['tool_results'].append({
                            'type': 'tool_result',
                            'content': x.content,
                            'name': getattr(x, 'name', None),
                            'tool_call_id': getattr(x, 'tool_call_id', None),
                            'status': getattr(x, 'status', None)
                        })
                    
                    elif isinstance(x, (HumanMessageChunk, HumanMessage)):
                        # Human/user messages in stream (rare, but handle gracefully)
                        if 'human_messages' not in serialized_chunk:
                            serialized_chunk['human_messages'] = []
                        serialized_chunk['human_messages'].append({
                            'type': 'human',
                            'content': x.content
                        })
                    
                    elif isinstance(x, (SystemMessageChunk, SystemMessage)):
                        # System messages in stream (rare, but possible for context injection)
                        if 'system_messages' not in serialized_chunk:
                            serialized_chunk['system_messages'] = []
                        serialized_chunk['system_messages'].append({
                            'type': 'system',
                            'content': x.content
                        })
                    
                    elif isinstance(x, (FunctionMessageChunk, FunctionMessage)):
                        # Function message results (legacy, but still supported)
                        if 'function_results' not in serialized_chunk:
                            serialized_chunk['function_results'] = []
                        serialized_chunk['function_results'].append({
                            'type': 'function',
                            'content': x.content,
                            'name': getattr(x, 'name', None)
                        })
                    
                    elif isinstance(x, (ChatMessageChunk, ChatMessage)):
                        # Generic chat messages
                        if 'chat_messages' not in serialized_chunk:
                            serialized_chunk['chat_messages'] = []
                        serialized_chunk['chat_messages'].append({
                            'type': 'chat',
                            'content': x.content,
                            'role': getattr(x, 'role', None)
                        })
                    
                    elif isinstance(x, BaseMessageChunk):
                        # Catch-all for any other message chunk types
                        logger.debug(f"Received unhandled message chunk type: {type(x).__name__}")
                        if 'unhandled_chunks' not in serialized_chunk:
                            serialized_chunk['unhandled_chunks'] = []
                        serialized_chunk['unhandled_chunks'].append({
                            'type': type(x).__name__,
                            'content': str(x.content) if hasattr(x, 'content') else str(x)
                        })
                    
                    else:
                        # Non-message objects (shouldn't happen in stream_mode="messages")
                        if isinstance(x, dict) and 'thread_id' in x and 'langgraph_node' in x:
                            # Skip internal threading info
                            logger.debug("Skipping internal thread/langgraph info chunk")
                            continue

                        logger.warning(f"Received non-message chunk of type: {type(x).__name__}")
                        if 'other_data' not in serialized_chunk:
                            serialized_chunk['other_data'] = []
                        serialized_chunk['other_data'].append({
                            'type': type(x).__name__,
                            'data': str(x)
                        })

                # Yield serialized chunks to client (only if there's data)
                if serialized_chunk:
                    yield {
                        "type": "update",
                        "data": serialized_chunk
                    }
            
            # Save messages to database after streaming completes
            async with DbContext.get_session_async() as session:
                user_message = AgentChatMessage(
                    chat_session_id=session_id,
                    role="USER",
                    message={
                        "content": message,
                        "model_id": model_id
                    },
                    message_order=last_order + 1,
                    is_analysis_query=is_analysis_query
                )

                assistant_message = AgentChatMessage(
                    chat_session_id=session_id,
                    role="ASSISTANT",
                    message={
                        "content": full_content,
                        "model_id": model_id
                    },
                    artifacts={
                        "artifacts": []
                    },
                    meta_data={
                        "usage_metadata": {},
                        "raw_messages": []
                    },
                    message_order=last_order + 2,
                    is_analysis_query=is_analysis_query
                )
                
                session.add(user_message)
                session.add(assistant_message)
                await session.commit()
                await session.refresh(user_message)
                await session.refresh(assistant_message)
                
                await self._update_last_message_order(session, session_id, last_order + 2)
                
                # Yield completion metadata with saved message IDs
                yield {
                    "type": "metadata",
                    "data": {
                        "status": "completed",
                        "session_id": str(session_id),
                        "user_message": self._serialize_message(user_message),
                        "assistant_message": self._serialize_message(assistant_message),
                    }
                }
        
        except Exception as e:
            logger.exception(f"Error in stream_message: {e}")
            yield {
                "type": "error",
                "data": {
                    "error": str(e)
                }
            }
    
    async def get_messages(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:

        async with DbContext.get_session_async() as session:
            query = select(AgentChatMessage).where(
                and_(
                    AgentChatMessage.chat_session_id == session_id,
                    AgentChatMessage.is_deleted == False
                )
            )
            
            from sqlmodel import asc
            query = query.order_by(asc(AgentChatMessage.message_order))
            query = query.limit(limit).offset(offset)
            
            result = await session.execute(query)
            messages = result.scalars().all()
            
            return [self._serialize_message(msg) for msg in messages]
    
    async def _get_last_message_order(
        self,
        session: Any,
        session_id: UUID
    ) -> int:
        """
        Get the last message order for a session.
        
        Args:
            session: Database session
            session_id: Chat session UUID
            
        Returns:
            Last message order (0 if no messages)
        """
        query = select(AgentChatSessionLastMessageOrder).where(
            AgentChatSessionLastMessageOrder.chat_session_id == session_id
        )
        
        result = await session.execute(query)
        order_record = result.scalar_one_or_none()
        
        if order_record:
            return order_record.last_message_order
        
        # No record exists, return 0
        return 0
    
    async def _update_last_message_order(
        self,
        session: Any,
        session_id: UUID,
        new_order: int
    ):
        """
        Update or insert the last message order for a session.
        
        Args:
            session: Database session
            session_id: Chat session UUID
            new_order: New message order value
        """
        query = select(AgentChatSessionLastMessageOrder).where(
            AgentChatSessionLastMessageOrder.chat_session_id == session_id
        )
        
        result = await session.execute(query)
        order_record = result.scalar_one_or_none()
        
        if order_record:
            order_record.last_message_order = new_order
            session.add(order_record)
        else:
            order_record = AgentChatSessionLastMessageOrder(
                chat_session_id=session_id,
                last_message_order=new_order
            )
            session.add(order_record)
    
    @staticmethod
    def _serialize_message(message: AgentChatMessage) -> Dict[str, Any]:
        return {
            "id": str(message.id),
            "role": message.role,
            "message": message.message,
            "artifacts": message.artifacts,
            "meta_data": message.meta_data,
            "message_order": message.message_order,
            "is_analysis_query": message.is_analysis_query,
            "created_on": message.created_on.isoformat() if message.created_on else None
        }

    @staticmethod
    def _serialize_tool_call_chunks(tool_call_chunks) -> List[Dict[str, Any]]:
        """
        Serialize tool call chunks to JSON-serializable format.
        
        Args:
            tool_call_chunks: List of tool call chunk objects
            
        Returns:
            List of serialized tool call chunks
        """
        serialized_chunks = []
        for chunk in tool_call_chunks:
            if isinstance(chunk, dict):
                serialized_chunks.append({
                    "name": chunk.get("name"),
                    "args": chunk.get("args"),
                    "id": chunk.get("id"),
                    "index": chunk.get("index")
                })
            elif hasattr(chunk, '__dict__'):
                # Handle object-type chunks
                serialized_chunks.append({
                    "name": getattr(chunk, 'name', None),
                    "args": getattr(chunk, 'args', None),
                    "id": getattr(chunk, 'id', None),
                    "index": getattr(chunk, 'index', None)
                })
            else:
                serialized_chunks.append({"raw": str(chunk)})
        
        return serialized_chunks

    @staticmethod
    def _serialize_langchain_message(message) -> Dict[str, Any]:
        """
        Serialize a LangChain message object to a JSON-serializable dict.
        
        Args:
            message: LangChain message object (AIMessage, AIMessageChunk, etc.)
            
        Returns:
            Dictionary representation of the message
        """
        serialized = {
            "type": message.__class__.__name__,
            "content": message.content if hasattr(message, 'content') else None,
        }
        
        # Add additional fields if present
        if hasattr(message, 'id') and message.id:
            serialized["id"] = message.id
        
        if hasattr(message, 'name') and message.name:
            serialized["name"] = message.name
        
        if hasattr(message, 'tool_calls') and message.tool_calls:
            serialized["tool_calls"] = message.tool_calls
        
        if hasattr(message, 'tool_call_chunks') and message.tool_call_chunks:
            serialized["tool_call_chunks"] = [
                {
                    "name": chunk.get("name"),
                    "args": chunk.get("args"),
                    "id": chunk.get("id"),
                    "index": chunk.get("index")
                } if isinstance(chunk, dict) else str(chunk)
                for chunk in message.tool_call_chunks
            ]
        
        if hasattr(message, 'response_metadata') and message.response_metadata:
            # Filter out non-serializable parts of response_metadata
            serialized["response_metadata"] = {
                k: v for k, v in message.response_metadata.items()
                if isinstance(v, (str, int, float, bool, type(None), dict, list))
            }
        
        return serialized


agent_chat_service = AgentChatService()
