"""0003_add_column_order_to_upload_snapshots

Revision ID: 0003_column_order
Revises: 584d406ada7e
Create Date: 2026-10-14 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0003_column_order'
down_revision: Union[str, Sequence[str], None] = '584d406ada7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'upload_snapshots',
        sa.Column('column_order', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('upload_snapshots', 'column_order')
