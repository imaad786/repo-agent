import logging
from datetime import datetime, UTC
from sqlmodel import select, and_
from typing import List, Optional
from uuid import UUID

from ..db.context import DbContext
from ..entities import AgentChatSession

logger = logging.getLogger(__name__)


class AgentSessionService:

    async def create_session(
            self,
            user_id: UUID,
            task_id: UUID,
            repo_namespace: Optional[str] = None,
            title: Optional[str] = None,
    ) -> AgentChatSession:
        async with DbContext.get_session_async() as session:
            if not title:
                title = f"Chat - {datetime.now(UTC).strftime('%Y-%m-%d %H:%M')}"

            chat_session = AgentChatSession(
                user_id=user_id,
                task_id=task_id,
                repo_namespace=repo_namespace,
                title=title,
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


agent_session_service = AgentSessionService()
