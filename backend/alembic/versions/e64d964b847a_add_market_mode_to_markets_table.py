"""add market_mode to markets table

Revision ID: e64d964b847a
Revises: aaba86b4ea7e
Create Date: 2026-02-05 14:50:12.674684

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e64d964b847a'
down_revision: Union[str, Sequence[str], None] = 'aaba86b4ea7e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add market_mode column to markets table."""
    # Add market_mode column with default value
    op.add_column(
        'markets',
        sa.Column(
            'market_mode',
            sa.String(),
            nullable=False,
            server_default='p2p_direct'
        )
    )
    
    # Create index for faster filtering by market_mode
    op.create_index(
        'ix_markets_market_mode',
        'markets',
        ['market_mode']
    )


def downgrade() -> None:
    """Remove market_mode column from markets table."""
    # Drop index first
    op.drop_index('ix_markets_market_mode', table_name='markets')
    
    # Drop column
    op.drop_column('markets', 'market_mode')