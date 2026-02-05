"""
PoolBet model - Bet placed in a pool market (AMM).
"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .market import Market
    from .outcome import Outcome


class PoolBet(Base, TimestampMixin):
    """
    Bet placed in a pool market with AMM-based pricing.
    
    In pool markets, users don't match with specific opponents.
    Instead, they bet into a shared liquidity pool with dynamic odds.
    
    Key Concept - Locked Odds:
    When a user places a bet, their odds are "locked in" at that moment.
    Even if the pool changes after their bet, they keep their locked odds.
    This is fair to early bettors who take more risk.
    
    Example:
        User bets $100 on "NaVi" when odds are 1.80
        - locked_odds = 1.80
        - potential_payout = 100 * 1.80 = 180
        
        Even if odds later drop to 1.50, this user still gets 1.80x payout.
    
    Attributes:
        user_id: Who placed the bet
        market_id: Which pool market
        outcome_id: Which outcome they bet on
        amount: How much they staked
        locked_odds: Odds at the moment of bet placement
        potential_payout: amount * locked_odds (what they win if correct)
        settled: Whether bet has been settled
        settled_at: When settlement occurred
        actual_payout: Final payout after settlement (may differ if insufficient liquidity)
    """
    __tablename__ = "pool_bets"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    outcome_id: Mapped[int] = mapped_column(ForeignKey("outcomes.id"), nullable=False, index=True)
    
    # Bet details
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False
    )
    locked_odds: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False
    )
    potential_payout: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False
    )
    
    # Settlement
    settled: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_payout: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(precision=20, scale=2)
    )
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="pool_bets")
    market: Mapped["Market"] = relationship()
    outcome: Mapped["Outcome"] = relationship()
    
    def __repr__(self) -> str:
        return (
            f"<PoolBet(id={self.id}, user_id={self.user_id}, "
            f"amount={self.amount}, locked_odds={self.locked_odds}, "
            f"settled={self.settled})>"
        )