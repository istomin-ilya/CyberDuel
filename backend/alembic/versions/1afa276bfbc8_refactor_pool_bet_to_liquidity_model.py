"""refactor_pool_bet_to_liquidity_model

Revision ID: 1afa276bfbc8
Revises: c18060e1d4ec
Create Date: 2026-02-06 12:55:20.741751

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1afa276bfbc8'
down_revision: Union[str, Sequence[str], None] = 'c18060e1d4ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.
    
    Changes to pool_bets table:
    - Remove locked_odds column (old AMM with locked odds model)
    - Remove potential_payout column (old AMM with locked odds model)
    - Add pool_share_percentage column (new liquidity pool model)
    - Add pool_size_at_bet column (new liquidity pool model)
    """
    # For SQLite, we need to use batch operations
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        # Drop old columns
        batch_op.drop_column('potential_payout')
        batch_op.drop_column('locked_odds')
    
    # Add new columns in a separate batch
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pool_share_percentage', sa.Numeric(precision=10, scale=6), nullable=True))
    
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pool_size_at_bet', sa.Numeric(precision=20, scale=2), nullable=True))
    
    # Update existing rows with default values
    op.execute("""
        UPDATE pool_bets 
        SET pool_share_percentage = 0.0,
            pool_size_at_bet = 0.0
        WHERE pool_share_percentage IS NULL
    """)


def downgrade() -> None:
    """Downgrade schema.
    
    Restore old AMM with locked odds model.
    """
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        # Drop new columns
        batch_op.drop_column('pool_size_at_bet')
        batch_op.drop_column('pool_share_percentage')
    
    # Add back old columns
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('potential_payout', sa.Numeric(precision=20, scale=2), nullable=True))
    
    with op.batch_alter_table('pool_bets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('locked_odds', sa.Numeric(precision=10, scale=2), nullable=True))
    
    # Set default values for old columns
    op.execute("""
        UPDATE pool_bets 
        SET locked_odds = 1.0,
            potential_payout = amount
        WHERE locked_odds IS NULL
    """)
