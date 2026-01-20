import asyncio
import logging
from datetime import datetime, UTC
from sqlmodel import select, and_
from typing import List, Optional
from uuid import UUID

from langchain.chat_models import init_chat_model

from ..db.context import DbContext
from ..entities import AgentChatSession
from ..agent.agent_types import AgentType
from ..utils.settings import settings

logger = logging.getLogger(__name__)

# Prefix used for auto-generated default titles (to identify sessions needing title generation)
DEFAULT_TITLE_PREFIX = "Chat -"

# Prompt for generating session titles
TITLE_GENERATION_PROMPT = """Generate a very short, concise title (3-6 words max) for a chat conversation that starts with this message.
The title should capture the main topic or intent. Do not use quotes or punctuation at the end.

User's first message: {message}

Title:"""

# Cached model instance for title generation (initialized lazily)
_title_generation_model = None


def _get_title_generation_model():
    """Get or initialize the cached model for title generation."""
    global _title_generation_model
    if _title_generation_model is None:
        _title_generation_model = init_chat_model(
            settings.default_agent_model,
            temperature=0.3  # Slightly creative but consistent
        )
        logger.info(f"Initialized title generation model: {settings.default_agent_model}")
    return _title_generation_model


class AgentSessionService:

    async def create_session(
            self,
            user_id: UUID,
            task_id: UUID,
            repo_namespace: Optional[str] = None,
            title: Optional[str] = None,
            agent_type: str = AgentType.GENERAL.value,
    ) -> AgentChatSession:
        async with DbContext.get_session_async() as session:
            if not title:
                title = f"Chat - {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"

            # Validate agent_type
            if agent_type not in AgentType.values():
                raise ValueError(
                    f"Invalid agent type: {agent_type}. "
                    f"Valid types: {AgentType.values()}"
                )

            chat_session = AgentChatSession(
                user_id=user_id,
                task_id=task_id,
                repo_namespace=repo_namespace,
                title=title,
                agent_type=agent_type,
                status="ACTIVE",
            )

            session.add(chat_session)
            await session.commit()
            await session.refresh(chat_session)

            logger.info(f"Created chat session {chat_session.id} for user {user_id} with task {task_id}")
            return chat_session

    async def get_session(
            self,
            session_id: UUID,
            user_id: Optional[UUID] = None
    ) -> Optional[AgentChatSession]:
        async with DbContext.get_session_async() as session:
            query = select(AgentChatSession).where(
                and_(
                    AgentChatSession.id == session_id,
                    AgentChatSession.is_deleted == False
                )
            )

            if user_id:
                query = query.where(AgentChatSession.user_id == user_id)

            result = await session.execute(query)
            chat_session = result.scalar_one_or_none()

            return chat_session

    async def list_sessions(
            self,
            user_id: UUID,
            status: Optional[str] = None,
            agent_type: Optional[str] = None,
            limit: int = 50,
            offset: int = 0
    ) -> List[AgentChatSession]:
        async with DbContext.get_session_async() as session:
            query = select(AgentChatSession).where(
                and_(
                    AgentChatSession.user_id == user_id,
                    AgentChatSession.is_deleted == False
                )
            )

            if status:
                query = query.where(AgentChatSession.status == status)

            if agent_type:
                query = query.where(AgentChatSession.agent_type == agent_type)

            from sqlmodel import desc
            query = query.order_by(desc(AgentChatSession.modified_on))
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            sessions = result.scalars().all()

            return list(sessions)

    async def update_session(
            self,
            session_id: UUID,
            title: Optional[str] = None,
            status: Optional[str] = None,
    ) -> Optional[AgentChatSession]:
        async with DbContext.get_session_async() as session:
            query = select(AgentChatSession).where(
                and_(
                    AgentChatSession.id == session_id,
                    AgentChatSession.is_deleted == False
                )
            )

            result = await session.execute(query)
            chat_session = result.scalar_one_or_none()

            if not chat_session:
                return None

            if title is not None:
                chat_session.title = title
            if status is not None:
                chat_session.status = status

            chat_session.modified_on = datetime.now(UTC)

            session.add(chat_session)
            await session.commit()
            await session.refresh(chat_session)

            logger.info(f"Updated chat session {session_id}")
            return chat_session

    async def delete_session(
            self,
            session_id: UUID,
    ) -> bool:
        async with DbContext.get_session_async() as session:
            query = select(AgentChatSession).where(
                and_(
                    AgentChatSession.id == session_id,
                    AgentChatSession.is_deleted == False
                )
            )

            result = await session.execute(query)
            chat_session = result.scalar_one_or_none()

            if not chat_session:
                return False

            chat_session.is_deleted = True
            chat_session.modified_on = datetime.now(UTC)

            session.add(chat_session)
            await session.commit()

            logger.info(f"Deleted chat session {session_id}")
            return True

    def needs_title_generation(self, title: Optional[str]) -> bool:
        """
        Check if a session title needs auto-generation.

        A title needs generation if it's None, empty, or starts with the default prefix.

        Args:
            title: Current session title

        Returns:
            True if title should be auto-generated
        """
        if not title:
            return True
        return title.startswith(DEFAULT_TITLE_PREFIX)

    async def generate_and_update_title(
            self,
            session_id: UUID,
            first_message: str
    ) -> Optional[str]:
        """
        Generate a title from the first message using LLM and update the session.

        This method runs the LLM call and updates the session title.
        Should be called in the background to not block the chat response.

        Args:
            session_id: Session UUID
            first_message: The user's first message in the conversation

        Returns:
            Generated title or None if generation failed
        """
        try:
            # Use the cached model for title generation
            model = _get_title_generation_model()

            prompt = TITLE_GENERATION_PROMPT.format(message=first_message[:500])  # Limit message length
            response = await model.ainvoke(prompt)

            # Extract and clean the title
            generated_title = response.content.strip()
            # Remove quotes if present
            generated_title = generated_title.strip('"\'')
            # Limit length
            if len(generated_title) > 100:
                generated_title = generated_title[:97] + "..."

            if generated_title:
                # Update the session with the generated title
                await self.update_session(session_id, title=generated_title)
                logger.info(f"Generated title for session {session_id}: {generated_title}")
                return generated_title

        except Exception as e:
            logger.warning(f"Failed to generate title for session {session_id}: {e}")

        return None

    def generate_title_background(self, session_id: UUID, first_message: str) -> None:
        """
        Trigger title generation in the background.

        Creates an asyncio task that runs the title generation without blocking.

        Args:
            session_id: Session UUID
            first_message: The user's first message
        """
        asyncio.create_task(
            self.generate_and_update_title(session_id, first_message),
            name=f"title_gen_{session_id}"
        )


agent_session_service = AgentSessionService()
