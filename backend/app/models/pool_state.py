"""
PoolState model - Current state of liquidity pool for an outcome.
"""
from decimal import Decimal
from sqlalchemy import ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .market import Market
    from .outcome import Outcome


class PoolState(Base, TimestampMixin):
    """
    Tracks the current liquidity pool state for each outcome in a pool market.
    
    Each outcome in a pool market has its own pool of staked funds.
    This model tracks how much is staked and how many participants.
    
    AMM Pricing:
    The current odds for an outcome are calculated from pool states:
        odds = total_pool / outcome_pool
    
    Where:
        total_pool = sum of all outcome pools in the market
        outcome_pool = total_staked for this specific outcome
    
    Example:
        Market: "Match Winner" (pool market)
        Outcome 1 "NaVi": total_staked = $500, participants = 3
        Outcome 2 "G2": total_staked = $300, participants = 2
        
        Total pool = $500 + $300 = $800
        
        Current odds:
        - NaVi: 800 / 500 = 1.60x
        - G2: 800 / 300 = 2.67x
    
    Attributes:
        market_id: Which pool market
        outcome_id: Which outcome
        total_staked: Total amount staked on this outcome
        participant_count: Number of unique bettors
    """
    __tablename__ = "pool_states"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    outcome_id: Mapped[int] = mapped_column(ForeignKey("outcomes.id"), nullable=False, index=True)
    
    # Pool statistics
    total_staked: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False,
        default=Decimal("0.00")
    )
    participant_count: Mapped[int] = mapped_column(default=0, nullable=False)
    
    # Relationships
    market: Mapped["Market"] = relationship()
    outcome: Mapped["Outcome"] = relationship()
    
    # Constraint: one pool state per (market, outcome) pair
    __table_args__ = (
        UniqueConstraint('market_id', 'outcome_id', name='uq_pool_state_market_outcome'),
    )
    
    def __repr__(self) -> str:
        return (
            f"<PoolState(market_id={self.market_id}, outcome_id={self.outcome_id}, "
            f"total_staked={self.total_staked}, participants={self.participant_count})>"
        )