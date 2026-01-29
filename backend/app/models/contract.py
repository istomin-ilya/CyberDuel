"""
Contract model - Matched position between Maker and Taker.
"""
from decimal import Decimal
from datetime import datetime
from enum import Enum
from sqlalchemy import Numeric, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User
    from .market import Market
    from .outcome import Outcome
    from .order import Order


class ContractStatus(str, Enum):
    """Contract lifecycle states."""
    ACTIVE = "ACTIVE"
    CLAIMED = "CLAIMED"
    DISPUTED = "DISPUTED"
    SETTLED = "SETTLED"


class Contract(Base, TimestampMixin):
    """
    Matched position between two users on a market outcome.
    
    When Taker matches Maker's order, a Contract is created.
    Contract locks in:
      - Who is on which side
      - How much each risks
      - What odds are locked
    
    Attributes:
        market_id: Which market
        order_id: Source order that was matched
        maker_id: User who created the order
        taker_id: User who matched the order
        outcome_id: Which outcome Maker is backing (Taker bets against)
        amount: Contract size (Maker's stake)
        odds: Locked-in odds from order
        status: Current lifecycle state
        
        # Optimistic Oracle fields
        claim_initiated_by: User who claimed result
        claim_initiated_at: When claim was made
        challenge_deadline: Until when claim can be disputed
        
        # Settlement
        winner_id: User who won the contract
        settled_at: When final payout was made
    """
    __tablename__ = "contracts"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    
    # Parties
    maker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    taker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    # Terms
    outcome_id: Mapped[int] = mapped_column(ForeignKey("outcomes.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    odds: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), nullable=False)
    
    status: Mapped[ContractStatus] = mapped_column(default=ContractStatus.ACTIVE, nullable=False, index=True)
    
    # Optimistic Oracle
    claim_initiated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    claim_initiated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    challenge_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Settlement
    winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    market: Mapped["Market"] = relationship(back_populates="contracts")
    order: Mapped["Order"] = relationship(back_populates="contracts")
    outcome: Mapped["Outcome"] = relationship(back_populates="contracts")
    maker: Mapped["User"] = relationship(
        foreign_keys=[maker_id],
        back_populates="contracts_as_maker"
    )
    taker: Mapped["User"] = relationship(
        foreign_keys=[taker_id],
        back_populates="contracts_as_taker"
    )
    
    def __repr__(self) -> str:
        return f"<Contract(id={self.id}, market={self.market_id}, maker={self.maker_id}, taker={self.taker_id})>"