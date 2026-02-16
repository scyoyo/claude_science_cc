"""add cached_round_summaries to meetings

Revision ID: 67e8f9g0h1i2
Revises: 56d94b6c741d
Create Date: 2026-02-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "67e8f9g0h1i2"
down_revision: Union[str, Sequence[str], None] = "56d94b6c741d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(connection, table: str, column: str) -> bool:
    insp = inspect(connection)
    cols = [c["name"] for c in insp.get_columns(table)]
    return column in cols


def upgrade() -> None:
    conn = op.get_bind()
    if not _column_exists(conn, "meetings", "cached_round_summaries"):
        op.add_column(
            "meetings",
            sa.Column("cached_round_summaries", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if _column_exists(conn, "meetings", "cached_round_summaries"):
        op.drop_column("meetings", "cached_round_summaries")
