"""Add meeting structured columns and webhook_configs table

Revision ID: a1b2c3d4e5f6
Revises: 2da00d343264
Create Date: 2026-02-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2da00d343264'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    """Check if a column already exists (for idempotent migrations)."""
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = [c["name"] for c in inspector.get_columns(table)]
    return column in columns


def _table_exists(table: str) -> bool:
    """Check if a table already exists."""
    bind = op.get_bind()
    inspector = inspect(bind)
    return table in inspector.get_table_names()


def upgrade() -> None:
    """Add missing meeting columns and webhook_configs table (idempotent)."""

    # 1. Add missing columns to meetings table (skip if already present)
    new_columns = [
        ("agenda", sa.Column("agenda", sa.Text(), server_default="", nullable=True)),
        ("agenda_questions", sa.Column("agenda_questions", sa.JSON(), nullable=True)),
        ("agenda_rules", sa.Column("agenda_rules", sa.JSON(), nullable=True)),
        ("output_type", sa.Column("output_type", sa.String(length=20), server_default="code", nullable=True)),
        ("context_meeting_ids", sa.Column("context_meeting_ids", sa.JSON(), nullable=True)),
    ]
    for col_name, col_obj in new_columns:
        if not _column_exists("meetings", col_name):
            op.add_column("meetings", col_obj)

    # 2. Create webhook_configs table (skip if already present)
    if not _table_exists("webhook_configs"):
        op.create_table('webhook_configs',
            sa.Column('id', sa.String(length=36), nullable=False),
            sa.Column('url', sa.String(length=2048), nullable=False),
            sa.Column('events', sa.JSON(), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=True),
            sa.Column('secret', sa.String(length=255), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=True),
            sa.Column('updated_at', sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint('id')
        )


def downgrade() -> None:
    """Remove meeting columns and webhook_configs table."""

    # Drop webhook_configs table
    op.drop_table('webhook_configs')

    # Remove added meeting columns
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.drop_column('context_meeting_ids')
        batch_op.drop_column('output_type')
        batch_op.drop_column('agenda_rules')
        batch_op.drop_column('agenda_questions')
        batch_op.drop_column('agenda')
