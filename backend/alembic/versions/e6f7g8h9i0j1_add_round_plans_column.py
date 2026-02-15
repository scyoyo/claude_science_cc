"""Add round_plans column to meetings table

Revision ID: e6f7g8h9i0j1
Revises: d5e6f7g8h9i0
Create Date: 2026-02-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "e6f7g8h9i0j1"
down_revision = "d5e6f7g8h9i0"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _column_exists("meetings", "round_plans"):
        op.add_column(
            "meetings",
            sa.Column("round_plans", sa.JSON(), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("meetings", "round_plans"):
        op.drop_column("meetings", "round_plans")
