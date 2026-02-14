"""Add language column to teams table

Revision ID: d5e6f7g8h9i0
Revises: c4d5e6f7g8h9
Create Date: 2026-02-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "d5e6f7g8h9i0"
down_revision = "c4d5e6f7g8h9"
branch_labels = None
depends_on = None


def _column_exists(table, column):
    bind = op.get_bind()
    columns = [c["name"] for c in inspect(bind).get_columns(table)]
    return column in columns


def upgrade() -> None:
    if not _column_exists("teams", "language"):
        op.add_column(
            "teams",
            sa.Column("language", sa.String(10), server_default="en", nullable=True),
        )


def downgrade() -> None:
    if _column_exists("teams", "language"):
        op.drop_column("teams", "language")
