"""merge heads: round_plans + cached_summary

Revision ID: 56d94b6c741d
Revises: e6f7g8h9i0j1, d6e7f8g9h0i1
Create Date: 2026-02-15 17:00:10.128375

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '56d94b6c741d'
down_revision: Union[str, Sequence[str], None] = ('e6f7g8h9i0j1', 'd6e7f8g9h0i1')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
