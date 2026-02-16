"""Add meeting cached summary columns (cached_summary_text, cached_key_points)

Revision ID: d6e7f8g9h0i1
Revises: c4d5e6f7g8h9
Create Date: 2026-02-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "d6e7f8g9h0i1"
down_revision: Union[str, Sequence[str], None] = "c4d5e6f7g8h9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _column_exists("meetings", "cached_summary_text"):
        op.add_column("meetings", sa.Column("cached_summary_text", sa.Text(), nullable=True))
    if not _column_exists("meetings", "cached_key_points"):
        op.add_column("meetings", sa.Column("cached_key_points", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _column_exists("meetings", "cached_summary_text"):
        op.drop_column("meetings", "cached_summary_text")
    if _column_exists("meetings", "cached_key_points"):
        op.drop_column("meetings", "cached_key_points")
