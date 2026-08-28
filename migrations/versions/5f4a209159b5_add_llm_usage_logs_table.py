"""add_llm_usage_logs_table

Revision ID: 5f4a209159b5
Revises: e5f6a7b8c9d0
Create Date: 2026-03-02 13:48:12.067291

"""
from typing import Sequence, Union
import sqlmodel
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5f4a209159b5'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('llm_usage_logs',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('created_on', sa.DateTime(timezone=True), nullable=False),
    sa.Column('modified_on', sa.DateTime(timezone=True), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('session_id', sa.Uuid(), nullable=True),
    sa.Column('task_id', sa.Uuid(), nullable=True),
    sa.Column('model_provider', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
    sa.Column('model_name', sqlmodel.sql.sqltypes.AutoString(length=200), nullable=False),
    sa.Column('input_tokens', sa.Integer(), nullable=False),
    sa.Column('output_tokens', sa.Integer(), nullable=False),
    sa.Column('total_tokens', sa.Integer(), nullable=False),
    sa.Column('caller', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='chat_agent'
    )
    op.create_index(op.f('ix_chat_agent_llm_usage_logs_caller'), 'llm_usage_logs', ['caller'], unique=False, schema='chat_agent')
    op.create_index(op.f('ix_chat_agent_llm_usage_logs_id'), 'llm_usage_logs', ['id'], unique=False, schema='chat_agent')
    op.create_index(op.f('ix_chat_agent_llm_usage_logs_session_id'), 'llm_usage_logs', ['session_id'], unique=False, schema='chat_agent')
    op.create_index(op.f('ix_chat_agent_llm_usage_logs_task_id'), 'llm_usage_logs', ['task_id'], unique=False, schema='chat_agent')
    op.create_index(op.f('ix_chat_agent_llm_usage_logs_user_id'), 'llm_usage_logs', ['user_id'], unique=False, schema='chat_agent')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chat_agent_llm_usage_logs_user_id'), table_name='llm_usage_logs', schema='chat_agent')
    op.drop_index(op.f('ix_chat_agent_llm_usage_logs_task_id'), table_name='llm_usage_logs', schema='chat_agent')
    op.drop_index(op.f('ix_chat_agent_llm_usage_logs_session_id'), table_name='llm_usage_logs', schema='chat_agent')
    op.drop_index(op.f('ix_chat_agent_llm_usage_logs_id'), table_name='llm_usage_logs', schema='chat_agent')
    op.drop_index(op.f('ix_chat_agent_llm_usage_logs_caller'), table_name='llm_usage_logs', schema='chat_agent')
    op.drop_table('llm_usage_logs', schema='chat_agent')
