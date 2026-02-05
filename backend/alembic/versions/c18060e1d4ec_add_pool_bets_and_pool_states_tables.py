"""add pool_bets and pool_states tables

Revision ID: c18060e1d4ec
Revises: e64d964b847a
Create Date: 2026-02-05 21:04:05.753775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c18060e1d4ec'
down_revision: Union[str, Sequence[str], None] = 'e64d964b847a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create pool_bets and pool_states tables for AMM pool market system."""
    
    # Create pool_bets table
    op.create_table(
        'pool_bets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('market_id', sa.Integer(), nullable=False),
        sa.Column('outcome_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('locked_odds', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('potential_payout', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('settled', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('settled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('actual_payout', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['market_id'], ['markets.id'], ),
        sa.ForeignKeyConstraint(['outcome_id'], ['outcomes.id'], ),
    )
    
    # Create indexes for pool_bets
    op.create_index('ix_pool_bets_id', 'pool_bets', ['id'])
    op.create_index('ix_pool_bets_user_id', 'pool_bets', ['user_id'])
    op.create_index('ix_pool_bets_market_id', 'pool_bets', ['market_id'])
    op.create_index('ix_pool_bets_outcome_id', 'pool_bets', ['outcome_id'])
    op.create_index('ix_pool_bets_settled', 'pool_bets', ['settled'])
    
    # Create pool_states table
    op.create_table(
        'pool_states',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('market_id', sa.Integer(), nullable=False),
        sa.Column('outcome_id', sa.Integer(), nullable=False),
        sa.Column('total_staked', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0.00'),
        sa.Column('participant_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['market_id'], ['markets.id'], ),
        sa.ForeignKeyConstraint(['outcome_id'], ['outcomes.id'], ),
        sa.UniqueConstraint('market_id', 'outcome_id', name='uq_pool_state_market_outcome'),
    )
    
    # Create indexes for pool_states
    op.create_index('ix_pool_states_id', 'pool_states', ['id'])
    op.create_index('ix_pool_states_market_id', 'pool_states', ['market_id'])
    op.create_index('ix_pool_states_outcome_id', 'pool_states', ['outcome_id'])


def downgrade() -> None:
    """Drop pool_bets and pool_states tables."""
    
    # Drop indexes first
    op.drop_index('ix_pool_states_outcome_id', table_name='pool_states')
    op.drop_index('ix_pool_states_market_id', table_name='pool_states')
    op.drop_index('ix_pool_states_id', table_name='pool_states')
    
    op.drop_index('ix_pool_bets_settled', table_name='pool_bets')
    op.drop_index('ix_pool_bets_outcome_id', table_name='pool_bets')
    op.drop_index('ix_pool_bets_market_id', table_name='pool_bets')
    op.drop_index('ix_pool_bets_user_id', table_name='pool_bets')
    op.drop_index('ix_pool_bets_id', table_name='pool_bets')
    
    # Drop tables
    op.drop_table('pool_states')
    op.drop_table('pool_bets')