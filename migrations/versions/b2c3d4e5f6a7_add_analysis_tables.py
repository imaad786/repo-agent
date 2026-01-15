"""Add analysis tables

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-15

Creates tables for analysis background worker:
- analysis_runs: Batch analysis runs with worker locking
- analysis_sessions: Links runs to chat sessions
- insights: Individual analysis findings

Also adds session_metadata column to agent_chat_sessions.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.utils.settings import settings

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    schema = settings.database_schema

    # 1. analysis_runs - batch analysis with worker locking
    op.create_table(
        'analysis_runs',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', UUID(), nullable=False, index=True),
        sa.Column('user_id', UUID(), nullable=False, index=True),
        sa.Column('repo_namespace', sa.String(500), nullable=True, index=True),
        sa.Column('categories', JSONB(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', index=True),
        sa.Column('triggered_by', sa.String(100)),
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),
        sa.Column('error_message', sa.Text()),
        sa.Column('insights_summary', JSONB()),
        sa.Column('worker_id', sa.String(100), index=True),
        sa.Column('locked_at', sa.DateTime(timezone=True)),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), index=True),
        sa.Column('modified_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema=schema
    )

    # 2. analysis_sessions - links runs to chat sessions
    op.create_table(
        'analysis_sessions',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('analysis_run_id', UUID(), sa.ForeignKey(f'{schema}.analysis_runs.id'), nullable=False, index=True),
        sa.Column('chat_session_id', UUID(), sa.ForeignKey(f'{schema}.agent_chat_sessions.id'), nullable=False, index=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('modified_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.UniqueConstraint('analysis_run_id', 'category', name='uq_analysis_run_category'),
        schema=schema
    )

    # 3. insights - individual findings
    op.create_table(
        'insights',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('task_id', UUID(), nullable=False, index=True),
        sa.Column('analysis_run_id', UUID(), sa.ForeignKey(f'{schema}.analysis_runs.id'), index=True),
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('severity', sa.String(20), nullable=False, index=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text()),
        sa.Column('file_path', sa.String(1000), index=True),
        sa.Column('line_start', sa.Integer()),
        sa.Column('line_end', sa.Integer()),
        sa.Column('recommended_action', sa.Text()),
        sa.Column('code_suggestion', sa.Text()),
        sa.Column('status', sa.String(30), nullable=False, server_default='new', index=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('resolved_by', UUID()),
        sa.Column('resolution_notes', sa.Text()),
        sa.Column('details', JSONB()),
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('agent_model', sa.String(100)),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), index=True),
        sa.Column('modified_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema=schema
    )

    # 4. Add session_metadata column to agent_chat_sessions
    op.add_column(
        'agent_chat_sessions',
        sa.Column('session_metadata', JSONB(), nullable=True),
        schema=schema
    )


def downgrade():
    schema = settings.database_schema
    op.drop_column('agent_chat_sessions', 'session_metadata', schema=schema)
    op.drop_table('insights', schema=schema)
    op.drop_table('analysis_sessions', schema=schema)
    op.drop_table('analysis_runs', schema=schema)
