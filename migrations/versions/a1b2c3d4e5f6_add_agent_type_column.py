"""Add agent_type column to agent_chat_sessions

Revision ID: a1b2c3d4e5f6
Revises: ef043fbe1d9a
Create Date: 2026-01-13 10:00:00.000000

"""
from typing import Sequence, Union
import sqlmodel
from alembic import op
import sqlalchemy as sa
from src.utils.settings import settings

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'ef043fbe1d9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add agent_type column with default value 'general'."""
    op.add_column(
        'agent_chat_sessions',
        sa.Column('agent_type', sa.VARCHAR(length=50), nullable=False, server_default='general'),
        schema=settings.database_schema
    )
    op.create_index(
        op.f(f'ix_{settings.database_schema}_agent_chat_sessions_agent_type'),
        'agent_chat_sessions',
        ['agent_type'],
        unique=False,
        schema=settings.database_schema
    )


def downgrade() -> None:
    """Remove agent_type column."""
    op.drop_index(
        op.f(f'ix_{settings.database_schema}_agent_chat_sessions_agent_type'),
        table_name='agent_chat_sessions',
        schema=settings.database_schema
    )
    op.drop_column('agent_chat_sessions', 'agent_type', schema=settings.database_schema)
