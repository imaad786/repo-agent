import asyncio
import logging
from typing import Optional, Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

from ..db.context import DbContext
from ..entities.llm_usage_log import LlmUsageLog
from ..utils.model_utils import parse_model_id

logger = logging.getLogger(__name__)


class UsageLoggingCallback(AsyncCallbackHandler):
    """
    LangChain async callback handler that logs token usage after each LLM call.

    Used for call sites where we can't intercept the response directly
    (e.g., SummarizationMiddleware).
    """

    def __init__(self, model_id: str, caller: str):
        super().__init__()
        self._model_id = model_id
        self._caller = caller

    async def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        try:
            llm_output = response.llm_output or {}
            token_usage = llm_output.get("token_usage", {})

            input_tokens = token_usage.get("prompt_tokens", 0)
            output_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)

            if total_tokens > 0:
                llm_usage_service.log_usage_background(
                    model_id=self._model_id,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    caller=self._caller,
                )
        except Exception:
            logger.debug("Failed to log LLM usage from callback", exc_info=True)


class LlmUsageService:

    async def log_usage(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        caller: str,
        user_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        task_id: Optional[UUID] = None,
    ) -> None:
        try:
            provider, model_name = parse_model_id(model_id)

            log_entry = LlmUsageLog(
                user_id=user_id,
                session_id=session_id,
                task_id=task_id,
                model_provider=provider,
                model_name=model_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                caller=caller,
            )

            async with DbContext.get_session_async() as session:
                session.add(log_entry)

            logger.debug(
                f"LLM usage logged: caller={caller}, model={provider}:{model_name}, "
                f"tokens={input_tokens}/{output_tokens}/{total_tokens}"
            )
        except Exception:
            logger.exception(f"Failed to log LLM usage for caller={caller}")

    def log_usage_background(
        self,
        model_id: str,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        caller: str,
        user_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        task_id: Optional[UUID] = None,
    ) -> None:
        asyncio.create_task(
            self.log_usage(
                model_id=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                caller=caller,
                user_id=user_id,
                session_id=session_id,
                task_id=task_id,
            ),
            name=f"llm_usage_log_{caller}"
        )


llm_usage_service = LlmUsageService()
