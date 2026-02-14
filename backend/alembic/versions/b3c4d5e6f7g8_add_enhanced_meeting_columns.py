"""Add enhanced meeting columns (meeting_type, individual_agent_id, source_meeting_ids, parent_meeting_id, rewrite_feedback, agenda_strategy, participant_agent_ids)

Revision ID: b3c4d5e6f7g8
Revises: a1b2c3d4e5f6
Create Date: 2026-02-14 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = 'b3c4d5e6f7g8'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in columns


def upgrade() -> None:
    # participant_agent_ids was missing from a1b2c3d4e5f6 migration
    if not _column_exists("meetings", "participant_agent_ids"):
        op.add_column("meetings", sa.Column("participant_agent_ids", sa.JSON(), nullable=True))
    if not _column_exists("meetings", "meeting_type"):
        op.add_column("meetings", sa.Column("meeting_type", sa.String(20), server_default="team"))
    if not _column_exists("meetings", "individual_agent_id"):
        op.add_column("meetings", sa.Column("individual_agent_id", sa.String(36), nullable=True))
    if not _column_exists("meetings", "source_meeting_ids"):
        op.add_column("meetings", sa.Column("source_meeting_ids", sa.JSON(), nullable=True))
    if not _column_exists("meetings", "parent_meeting_id"):
        op.add_column("meetings", sa.Column("parent_meeting_id", sa.String(36), nullable=True))
    if not _column_exists("meetings", "rewrite_feedback"):
        op.add_column("meetings", sa.Column("rewrite_feedback", sa.Text(), server_default=""))
    if not _column_exists("meetings", "agenda_strategy"):
        op.add_column("meetings", sa.Column("agenda_strategy", sa.String(30), server_default="manual"))


def downgrade() -> None:
    for col in ["agenda_strategy", "rewrite_feedback", "parent_meeting_id", "source_meeting_ids", "individual_agent_id", "meeting_type", "participant_agent_ids"]:
        if _column_exists("meetings", col):
            op.drop_column("meetings", col)
