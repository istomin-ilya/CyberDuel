"""
Outcome model - Possible result of a market.
"""
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .market import Market
    from .order import Order
    from .contract import Contract


class Outcome(Base, TimestampMixin):
    """
    Possible outcome of a betting market.
    
    Each Market has 2+ possible Outcomes.
    Users bet on specific Outcomes via Orders.
    
    Example:
        Market: "Match Winner"
          - Outcome 1: name="NaVi", external_id="team_12345"
          - Outcome 2: name="G2", external_id="team_67890"
        
        Market: "Total Kills > 40.5"
          - Outcome 1: name="Over", external_id=null
          - Outcome 2: name="Under", external_id=null
    
    Attributes:
        market_id: Parent market
        name: Outcome name (e.g., "NaVi", "Over", "Yes")
        external_id: External identifier (team ID, player ID, etc) - optional
    """
    __tablename__ = "outcomes"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    market_id: Mapped[int] = mapped_column(ForeignKey("markets.id"), nullable=False, index=True)
    
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(100))
    
    # Relationships
    market: Mapped["Market"] = relationship(
        back_populates="outcomes",
        foreign_keys=[market_id]
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="outcome",
        cascade="all, delete-orphan"
    )
    contracts: Mapped[list["Contract"]] = relationship(
        back_populates="outcome",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Outcome(id={self.id}, name='{self.name}', market={self.market_id})>"