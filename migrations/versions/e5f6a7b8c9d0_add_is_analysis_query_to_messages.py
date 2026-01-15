"""Add is_analysis_query to agent_chat_messages

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-01-15

Adds is_analysis_query boolean column to agent_chat_messages table.
When true, indicates the message is part of an analysis query and
should be rendered with a special UI (e.g., JSON insights view).
"""
from alembic import op
import sqlalchemy as sa
from src.utils.settings import settings

revision = 'e5f6a7b8c9d0'
down_revision = 'd4e5f6a7b8c9'
branch_labels = None
depends_on = None


def upgrade():
    schema = settings.database_schema
    op.add_column(
        'agent_chat_messages',
        sa.Column('is_analysis_query', sa.Boolean(), nullable=False, server_default='false'),
        schema=schema
    )


def downgrade():
    schema = settings.database_schema
    op.drop_column('agent_chat_messages', 'is_analysis_query', schema=schema)
