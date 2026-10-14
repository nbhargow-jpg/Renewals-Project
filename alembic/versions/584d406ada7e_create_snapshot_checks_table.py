"""create_snapshot_checks_table

Revision ID: 584d406ada7e
Revises: 2ce891c9fa53
Create Date: 2026-10-12 14:38:00.334340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '584d406ada7e'
down_revision: Union[str, Sequence[str], None] = '2ce891c9fa53'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'snapshot_checks',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('snapshot_id', sa.String(length=36), sa.ForeignKey('upload_snapshots.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workbook_name', sa.String(length=256), nullable=False),
        sa.Column('sheet_name', sa.String(length=128), nullable=False),
        sa.Column('cell_or_row', sa.String(length=128), nullable=False),
        sa.Column('metric_name', sa.String(length=128), nullable=False),
        sa.Column('excel_value', sa.String(length=256), nullable=False),
        sa.Column('website_value', sa.String(length=256), nullable=False),
        sa.Column('diff_value', sa.String(length=256), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index(op.f('ix_snapshot_checks_snapshot_id'), 'snapshot_checks', ['snapshot_id'], unique=False)
    op.create_index(op.f('ix_snapshot_checks_status'), 'snapshot_checks', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_snapshot_checks_status'), table_name='snapshot_checks')
    op.drop_index(op.f('ix_snapshot_checks_snapshot_id'), table_name='snapshot_checks')
    op.drop_table('snapshot_checks')
