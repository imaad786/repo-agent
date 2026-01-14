import re

import aiofiles
import logging
from langchain.agents import create_agent
from langchain.agents.middleware import wrap_model_call, ModelRequest, ModelResponse, SummarizationMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.embeddings import Embeddings
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage, AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.config import get_store
from langgraph.store.postgres import AsyncPostgresStore
from langmem import create_manage_memory_tool, create_search_memory_tool
from typing import Dict, Any, List, Optional

from .schemas import ContextSchema
from ..utils.settings import settings

logger = logging.getLogger(__name__)


class CodeIntelligenceAgent:

    def __init__(
            self,
            name: str,
            tools: List[Any],
            embeddings: Embeddings,
            system_prompt: str = "",
            default_llm_model_id: str = "openai:gpt-4o",
            temperature: float = 0.1,
            base_memory_namespace: str = "code_intelligence_agent_memories",
            recursion_limit: int = 50,
    ):
        self._name_ = name
        self._tools_ = tools
        self._embeddings_ = embeddings
        self._system_prompt__ = system_prompt
        self._base_memory_namespace_ = base_memory_namespace
        self._recursion_limit_ = recursion_limit

        self._agent_ = None
        self._checkpointer_ = None
        self._store_ = None

        self._namespace_ = (base_memory_namespace, "{user_id}")
        self._memory_tools_ = [
            create_manage_memory_tool(namespace=self._base_memory_namespace_),
            create_search_memory_tool(namespace=self._base_memory_namespace_)
        ]

        self._temperature_ = temperature
        self._default_llm_model_id_ = default_llm_model_id
        self._model_ = {
            default_llm_model_id: init_chat_model(default_llm_model_id, temperature=temperature)
        }

    async def startup(self):
        """Initialize the agent with checkpointer and store connections."""
        try:
            # Create checkpointer and store by entering their context managers
            # Store the context managers so we can exit them later
            self._checkpointer_cm_ = AsyncPostgresSaver.from_conn_string(
                conn_string=settings.database_url_for_agent
            )
            self._store_cm_ = AsyncPostgresStore.from_conn_string(
                conn_string=settings.database_url_for_agent,
                index={"dims": 384, "embed": self._embeddings_}
            )

            # Enter the context managers to get the actual objects
            self._checkpointer_ = await self._checkpointer_cm_.__aenter__()
            self._store_ = await self._store_cm_.__aenter__()

            # items = [
            #     item async for item in self._checkpointer_.alist(
            #         config={"configurable": {"thread_id": "63c04f45-0030-453c-921a-c1b52244b579"}}
            #     )
            # ]

            await self._checkpointer_.setup()
            await self._store_.setup()

            summarization_middleware = SummarizationMiddleware(
                model=self._model_[self._default_llm_model_id_],
                trigger=[("fraction", 0.65)],
                keep=("fraction", 0.3),
                trim_tokens_to_summarize=5000,
                summary_prefix="Previous conversation summary:",
            )

            self._agent_ = create_agent(
                name=self._name_,
                model=self._model_[self._default_llm_model_id_],
                tools=self._tools_ + self._memory_tools_,
                system_prompt=self._system_prompt__,
                checkpointer=self._checkpointer_,
                store=self._store_,
                context_schema=ContextSchema,
                middleware=[self.get_call_model_middleware(), summarization_middleware],
            )

            logger.info("Agent startup completed successfully")

        except Exception as e:
            logger.error(f"Error during agent startup: {e}", exc_info=True)
            raise

    def get_call_model_middleware(self):
        @wrap_model_call
        async def select_model_request(request: ModelRequest, handler) -> ModelResponse:
            model_id = request.runtime.context.model_id
            user_id = request.runtime.context.user_id
            memories_injected = request.runtime.context.memories_injected

            if model_id:
                if model_id not in self._model_:
                    self._model_[model_id] = init_chat_model(model_id, temperature=self._temperature_)
                    model = self._model_[model_id]
                    logger.info(f"Initialized and cached model '{model_id}'")
                else:
                    model = self._model_[model_id]
                    logger.info(f"Using cached model '{model_id}'")
            else:
                model = self._model_[self._default_llm_model_id_]
                logger.info(f"No model_id specified, using default model '{self._default_llm_model_id_}'")

            # Only inject memories once per agent invocation
            if not memories_injected:
                formatted_namespace = (
                    self._base_memory_namespace_[0],
                    self._base_memory_namespace_[1].format(user_id=user_id)
                )
                store = get_store()

                # Extract text content from message (handle both string and list formats)
                last_message_content = request.messages[-1].content
                if isinstance(last_message_content, list):
                    # Extract text from multimodal content
                    query_text = " ".join([
                        item.get("text", "") if isinstance(item, dict) else str(item)
                        for item in last_message_content
                    ])
                else:
                    query_text = last_message_content

                items = await store.asearch(
                    formatted_namespace,
                    query=query_text
                )
                memories = "\n\n".join([
                    f"**Memory {i + 1}:** {item.value['content']}" for i, item in enumerate(items)
                ])
                system_msg = SystemMessage(content=f'### User Memories:\n\n{memories}')
                request.messages = [system_msg] + request.messages
                self.sanitize_messages_names(request.messages)

                # Mark that memories have been injected by updating the context
                request.runtime.context.memories_injected = True
                logger.info("Injected memories for this agent invocation")
            else:
                logger.info("Skipping memory injection - already injected for this invocation")

            self.sanitize_messages_names(request.messages)
            response_generated = await handler(request.override(model=model))
            self.sanitize_messages_names(response_generated.result)
            return response_generated

        return select_model_request

    def sanitize_messages_names(self, messages):
        for msg in messages:
            if hasattr(msg, 'name') and msg.name and len(msg.name) > 0:
                msg.name = self.sanitize_message_name(msg.name)
                continue

            if isinstance(msg, HumanMessage):
                msg.name = "HumanMessage"
            elif isinstance(msg, ToolMessage):
                msg.name = "ToolMessage"
            elif isinstance(msg, AIMessage):
                msg.name = "AIMessage"
            elif msg.type:
                msg.name = f"{msg.type.upper()}Message"
            else:
                msg.name = "Message"

    def sanitize_message_name(self, name: str) -> str:
        """
        Sanitizes a string to match the OpenAI name pattern.
        This function replaces invalid characters with underscores.
        """
        sanitized_name = re.sub(r'[\s<|\\/>]+', '_', name)
        sanitized_name = sanitized_name.strip('_')
        if not sanitized_name:
            return "Message"
        return sanitized_name

    async def shutdown(self):
        """Cleanup resources when shutting down the agent."""
        try:
            # Exit the context managers properly
            if hasattr(self, '_checkpointer_cm_') and self._checkpointer_cm_:
                await self._checkpointer_cm_.__aexit__(None, None, None)
                self._checkpointer_ = None
                self._checkpointer_cm_ = None
            if hasattr(self, '_store_cm_') and self._store_cm_:
                await self._store_cm_.__aexit__(None, None, None)
                self._store_ = None
                self._store_cm_ = None
            self._model_ = None
            logger.info("Agent shutdown completed successfully")
        except Exception as e:
            logger.error(f"Error during agent shutdown: {e}", exc_info=True)

    async def save_graph_png(self):
        try:
            png_data = self._agent_.get_graph().draw_mermaid_png()
            async with aiofiles.open(f"graph.png", "wb") as f:
                await f.write(png_data)
        except Exception:
            logger.exception("Failed to save agent graph PNG")

    async def ask(
            self,
            user_id: str,
            session_id: str,
            model_id: Optional[str],
            task_id: str,
            repo_namespace: Optional[str] = None,
            message: str = "",
            recursion_limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        input_message = {"role": "user", "content": message.strip()}
        config = {
            "recursion_limit": recursion_limit if recursion_limit else self._recursion_limit_,
            "configurable": {
                "thread_id": session_id,
                "user_id": user_id,
            }
        }
        response_updates = await self._agent_.ainvoke(
            input={"messages": [input_message]},
            config=config,
            context=ContextSchema(
                task_id=task_id,
                repo_namespace=repo_namespace,
                model_id=model_id,
                user_id=user_id
            ),
            stream_mode="updates",
        )
        return {
            "content": response_updates[-1]["model"].get("messages", [])[-1].content
        }

    async def astream(
            self,
            user_id: str,
            session_id: str,
            model_id: Optional[str],
            task_id: str,
            repo_namespace: Optional[str] = None,
            message: str = "",
            recursion_limit: Optional[int] = None,
    ):
        """
        Stream agent responses with agent progress updates.

        Yields:
            Chunk containing state updates after each agent step
        """
        input_message = {"role": "user", "content": message.strip()}
        config = {
            "recursion_limit": recursion_limit if recursion_limit else self._recursion_limit_,
            "configurable": {
                "thread_id": session_id,
                "user_id": user_id,
            }
        }

        # Stream with updates mode for agent progress
        async for chunk in self._agent_.astream(
            input={"messages": [input_message]},
            config=config,
            context=ContextSchema(
                task_id=task_id,
                repo_namespace=repo_namespace,
                model_id=model_id,
                user_id=user_id
            ),
            stream_mode="messages",
        ):
            yield chunk
