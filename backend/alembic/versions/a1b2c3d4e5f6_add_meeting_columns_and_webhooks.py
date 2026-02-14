"""Add meeting structured columns and webhook_configs table

Revision ID: a1b2c3d4e5f6
Revises: 2da00d343264
Create Date: 2026-02-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '2da00d343264'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing meeting columns and webhook_configs table."""

    # 1. Add missing columns to meetings table
    with op.batch_alter_table('meetings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agenda', sa.Text(), server_default='', nullable=True))
        batch_op.add_column(sa.Column('agenda_questions', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('agenda_rules', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('output_type', sa.String(length=20), server_default='code', nullable=True))
        batch_op.add_column(sa.Column('context_meeting_ids', sa.JSON(), nullable=True))

    # 2. Create webhook_configs table
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
