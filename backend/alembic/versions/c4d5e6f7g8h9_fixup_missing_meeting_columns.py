"""Fixup: ensure all meeting columns exist on PostgreSQL

Safety net migration - re-checks and adds any columns that might be missing
if previous migrations were stamped but columns weren't actually created.

Revision ID: c4d5e6f7g8h9
Revises: b3c4d5e6f7g8
Create Date: 2026-02-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'c4d5e6f7g8h9'
down_revision: Union[str, Sequence[str], None] = 'b3c4d5e6f7g8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in columns


def upgrade() -> None:
    """Re-check all meeting columns that should exist by now."""
    columns_to_ensure = [
        ("participant_agent_ids", sa.Column("participant_agent_ids", sa.JSON(), nullable=True)),
        ("meeting_type", sa.Column("meeting_type", sa.String(20), server_default="team")),
        ("individual_agent_id", sa.Column("individual_agent_id", sa.String(36), nullable=True)),
        ("source_meeting_ids", sa.Column("source_meeting_ids", sa.JSON(), nullable=True)),
        ("parent_meeting_id", sa.Column("parent_meeting_id", sa.String(36), nullable=True)),
        ("rewrite_feedback", sa.Column("rewrite_feedback", sa.Text(), server_default="")),
        ("agenda_strategy", sa.Column("agenda_strategy", sa.String(30), server_default="manual")),
    ]
    for col_name, col_obj in columns_to_ensure:
        if not _column_exists("meetings", col_name):
            op.add_column("meetings", col_obj)


def downgrade() -> None:
    pass  # No-op: don't remove columns that b3c4d5e6f7g8 should manage
