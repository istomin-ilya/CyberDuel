"""
Order model - Maker liquidity provision.
"""
from decimal import Decimal
from enum import Enum
from sqlalchemy import Numeric, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .market import Market
    from .outcome import Outcome
    from .contract import Contract


class OrderStatus(str, Enum):
    """Order fill state."""
    OPEN = "OPEN"
    PARTIALLY_FILLED = "PARTIALLY"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"


class Order(Base, TimestampMixin):
    """
    Order created by Maker offering liquidity.
    
    Maker creates an order backing a specific Outcome in a Market.
    Takers can match against this order.
    
    Example:
        Market: "Match Winner"
        Outcome: "NaVi"
        Order: User bets 100 at odds 1.8 on NaVi winning
    
    Attributes:
        user_id: Who created the order (Maker)
        market_id: Which market
        outcome_id: Which outcome Maker is backing
        amount: Initial order size
        unfilled_amount: Remaining unmatched portion
        odds: Decimal odds (e.g., 1.8 means 1.8x return)
        status: Current fill state
    """
    __tablename__ = "orders"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    outcome_id: Mapped[int] = mapped_column(ForeignKey("outcomes.id"), nullable=False, index=True)
    
    # Amounts
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    unfilled_amount: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    
    # Odds (stored as decimal, e.g., 1.80)
    odds: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), nullable=False)
    
    status: Mapped[OrderStatus] = mapped_column(default=OrderStatus.OPEN, nullable=False, index=True)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="orders")
    market: Mapped["Market"] = relationship(back_populates="orders")
    outcome: Mapped["Outcome"] = relationship(back_populates="orders")
    contracts: Mapped[list["Contract"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Order(id={self.id}, market={self.market_id}, outcome={self.outcome_id}, {self.unfilled_amount}/{self.amount})>"