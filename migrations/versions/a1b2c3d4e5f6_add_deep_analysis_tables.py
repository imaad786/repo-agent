"""Add deep analysis tables

Revision ID: a1b2c3d4e5f6
Revises: ef043fbe1d9a
Create Date: 2026-01-12

Creates tables for deep analysis background worker:
- deep_analysis_runs: Batch analysis runs with worker locking
- deep_analysis_sessions: Links runs to chat sessions
- deep_insights: Individual analysis findings

Also adds metadata column to agent_chat_sessions.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = 'a1b2c3d4e5f6'
down_revision = 'ef043fbe1d9a'
branch_labels = None
depends_on = None


def upgrade():
    # 1. deep_analysis_runs - batch analysis with worker locking
    op.create_table(
        'deep_analysis_runs',
        # Primary key
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Context / Data Isolation
        sa.Column('task_id', UUID(), nullable=False, index=True),
        sa.Column('user_id', UUID(), nullable=False, index=True),

        # Analysis Configuration
        sa.Column('categories', JSONB(), nullable=False),
        sa.Column('execution_mode', sa.String(20), nullable=False, server_default='parallel'),

        # Status & Progress
        sa.Column('status', sa.String(20), nullable=False, server_default='pending', index=True),
        sa.Column('triggered_by', sa.String(100)),

        # Timing
        sa.Column('started_at', sa.DateTime(timezone=True)),
        sa.Column('completed_at', sa.DateTime(timezone=True)),

        # Results & Errors
        sa.Column('error_message', sa.Text()),
        sa.Column('insights_summary', JSONB()),

        # Worker Locking
        sa.Column('worker_id', sa.String(100), index=True),
        sa.Column('locked_at', sa.DateTime(timezone=True)),

        # BaseEntityMixin fields
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), index=True),
        sa.Column('modified_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='chat_agent'
    )

    # 2. deep_analysis_sessions - links runs to chat sessions
    op.create_table(
        'deep_analysis_sessions',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Foreign Keys
        sa.Column('analysis_run_id', UUID(), sa.ForeignKey('chat_agent.deep_analysis_runs.id'), nullable=False, index=True),
        sa.Column('chat_session_id', UUID(), sa.ForeignKey('chat_agent.agent_chat_sessions.id'), nullable=False, index=True),

        # Category this session analyzed
        sa.Column('category', sa.String(50), nullable=False),

        # BaseEntityMixin fields
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('modified_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),

        # Unique constraint - one session per category per run
        sa.UniqueConstraint('analysis_run_id', 'category', name='uq_analysis_run_category'),
        schema='chat_agent'
    )

    # 3. deep_insights - individual findings
    op.create_table(
        'deep_insights',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),

        # Context
        sa.Column('task_id', UUID(), nullable=False, index=True),
        sa.Column('analysis_run_id', UUID(), sa.ForeignKey('chat_agent.deep_analysis_runs.id'), index=True),

        # Classification
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('severity', sa.String(20), nullable=False, index=True),

        # Content
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('description', sa.Text()),

        # Location
        sa.Column('file_path', sa.String(1000), index=True),
        sa.Column('line_start', sa.Integer()),
        sa.Column('line_end', sa.Integer()),

        # Recommendations
        sa.Column('recommended_action', sa.Text()),
        sa.Column('code_suggestion', sa.Text()),

        # Workflow Status
        sa.Column('status', sa.String(30), nullable=False, server_default='new', index=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True)),
        sa.Column('resolved_by', UUID()),
        sa.Column('resolution_notes', sa.Text()),

        # Metadata
        sa.Column('details', JSONB()),
        sa.Column('confidence_score', sa.Numeric(3, 2)),
        sa.Column('agent_model', sa.String(100)),

        # BaseEntityMixin fields
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), index=True),
        sa.Column('modified_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema='chat_agent'
    )

    # 4. Add session_metadata column to agent_chat_sessions for analysis context
    op.add_column(
        'agent_chat_sessions',
        sa.Column('session_metadata', JSONB(), nullable=True),
        schema='chat_agent'
    )


def downgrade():
    # Remove in reverse order
    op.drop_column('agent_chat_sessions', 'session_metadata', schema='chat_agent')
    op.drop_table('deep_insights', schema='chat_agent')
    op.drop_table('deep_analysis_runs', schema='chat_agent')
    op.drop_table('deep_analysis_sessions', schema='chat_agent')
    op.drop_table('deep_analysis_runs', schema='chat_agent')
