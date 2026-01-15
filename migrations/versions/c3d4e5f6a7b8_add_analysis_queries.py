"""Add analysis queries table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-01-15

Creates the analysis_queries table for storing configurable
analysis queries that can be modified without code changes.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from src.utils.settings import settings

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    schema = settings.database_schema

    op.create_table(
        'analysis_queries',
        sa.Column('id', UUID(), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('category', sa.String(50), nullable=False, index=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.String(1000)),
        sa.Column('query_text', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('priority', sa.Integer(), server_default='0', nullable=False),
        sa.Column('expected_output_format', sa.String(50), server_default='json'),
        sa.Column('output_schema', JSONB()),
        sa.Column('is_active', sa.Boolean(), server_default='true'),
        sa.Column('is_deleted', sa.Boolean(), server_default='false'),
        sa.Column('created_on', sa.DateTime(timezone=True), server_default=sa.text('now()'), index=True),
        sa.Column('modified_on', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        schema=schema
    )

    op.create_unique_constraint(
        'uq_analysis_queries_category_name',
        'analysis_queries',
        ['category', 'name'],
        schema=schema
    )

    op.create_index(
        'ix_analysis_queries_category_default',
        'analysis_queries',
        ['category', 'is_default', 'priority'],
        schema=schema
    )


def downgrade():
    schema = settings.database_schema
    op.drop_table('analysis_queries', schema=schema)
