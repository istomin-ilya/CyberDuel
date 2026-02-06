"""
PoolBet model - Liquidity contribution to a pool market.
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
    Liquidity contribution to a pool market (DeFi-style).
    
    In pool markets, users add liquidity to a specific outcome's pool.
    They receive a share of that pool based on their contribution.
    When the outcome wins, winners split the entire market pool proportionally.
    
    Key Concept - Pool Share:
    User's share = user_deposit / (pool_size + user_deposit)
    
    Example:
        Pool NaVi = 500$ (existing)
        User adds 300$:
        - New pool = 800$
        - User share = 300/800 = 37.5%
        - If NaVi wins and total market = 1000$, user gets 37.5% × 1000$ = 375$ (before fee)
    
    Attributes:
        user_id: Who added liquidity
        market_id: Which pool market
        outcome_id: Which outcome they backed
        amount: How much they contributed
        initial_pool_share_percentage: Their share of the outcome pool at bet time (snapshot)
        pool_size_at_bet: Size of outcome pool before this bet
        settled: Whether bet has been settled
        settled_at: When settlement occurred
        actual_payout: Final payout after settlement (0 if outcome lost)
    """
    __tablename__ = "pool_bets"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    outcome_id: Mapped[int] = mapped_column(ForeignKey("outcomes.id"), nullable=False, index=True)
    
    # Liquidity contribution details
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=20, scale=2),
        nullable=False
    )
    initial_pool_share_percentage: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6),  # e.g., 37.500000 for 37.5%
        nullable=False
    )
    pool_size_at_bet: Mapped[Decimal] = mapped_column(
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
            f"amount={self.amount}, pool_share={self.pool_share_percentage}%, "
            f"settled={self.settled})>"
        )