"""rename_pool_share_percentage_to_initial

Revision ID: f448b649718b
Revises: 1afa276bfbc8
Create Date: 2026-02-06 14:11:30.854037

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f448b649718b'
down_revision: Union[str, Sequence[str], None] = '1afa276bfbc8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: rename pool_share_percentage to initial_pool_share_percentage."""
    # SQLite supports column rename with batch operations
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.alter_column(
            'pool_share_percentage',
            new_column_name='initial_pool_share_percentage',
            existing_type=sa.Numeric(precision=10, scale=6),
            nullable=False
        )


def downgrade() -> None:
    """Downgrade schema: rename back to pool_share_percentage."""
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.alter_column(
            'initial_pool_share_percentage',
            new_column_name='pool_share_percentage',
            existing_type=sa.Numeric(precision=10, scale=6),
            nullable=False
        )
