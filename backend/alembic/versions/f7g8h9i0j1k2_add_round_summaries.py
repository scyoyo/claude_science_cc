"""Add meeting round_summaries column

Revision ID: f7g8h9i0j1k2
Revises: 56d94b6c741d
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "f7g8h9i0j1k2"
down_revision: Union[str, Sequence[str], None] = "56d94b6c741d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _column_exists("meetings", "round_summaries"):
        op.add_column("meetings", sa.Column("round_summaries", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _column_exists("meetings", "round_summaries"):
        op.drop_column("meetings", "round_summaries")
