"""
Market model - Betting market within an event.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .event import Event
    from .outcome import Outcome
    from .order import Order
    from .contract import Contract


class MarketType(str, Enum):
    """Types of betting markets."""
    MATCH_WINNER = "match_winner"           # Who wins the match
    TOTAL_KILLS = "total_kills"             # Over/Under kills
    FIRST_BLOOD = "first_blood"             # Who gets first kill
    ROUND_WINNER = "round_winner"           # Specific round winner
    MAP_WINNER = "map_winner"               # Specific map winner (BO3/BO5)
    HANDICAP = "handicap"                   # Score handicap
    CUSTOM = "custom"                       # Custom market


class MarketStatus(str, Enum):
    """Market lifecycle states."""
    PENDING = "PENDING"                     # Not open for betting yet
    OPEN = "OPEN"                           # Accepting bets
    LOCKED = "LOCKED"                       # No new bets (match started)
    PENDING_VERIFICATION = "PENDING_VERIFICATION"  # Waiting for result
    DISPUTED = "DISPUTED"                   # Result contested
    SETTLED = "SETTLED"                     # Final result confirmed
    CANCELLED = "CANCELLED"                 # Market cancelled, refunds issued


class MarketMode(str, Enum):
    """Market trading modes."""
    P2P_DIRECT = "p2p_direct"               # 1v1 order matching (existing system)
    POOL_MARKET = "pool_market"             # AMM-based pool betting (new system)


class Market(Base, TimestampMixin):
    """
    Betting market within an event.
    
    A Market represents a specific question/proposition within an event.
    Each market has multiple possible Outcomes that users can bet on.
    
    Market Modes:
    - P2P_DIRECT: Users create orders with custom odds, matched 1v1
    - POOL_MARKET: Shared liquidity pool with AMM-based dynamic odds
    
    Example:
        Event: "NaVi vs G2"
        Market 1: "Match Winner" (P2P_DIRECT)
          - Outcome 1: "NaVi"
          - Outcome 2: "G2"
        Market 2: "Total Kills > 40.5" (POOL_MARKET)
          - Outcome 1: "Over"
          - Outcome 2: "Under"
    
    Attributes:
        event_id: Parent event
        market_type: Type of market (match_winner, total_kills, etc)
        market_mode: Trading mode (p2p_direct or pool_market)
        title: Human-readable title ("Match Winner", "Total Kills Over 40.5")
        description: Detailed description of market rules
        status: Current state
        settled_at: When market was resolved
        winning_outcome_id: Which outcome won (after settlement)
    """
    __tablename__ = "markets"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    
    market_type: Mapped[MarketType] = mapped_column(nullable=False, index=True)
    market_mode: Mapped[MarketMode] = mapped_column(
        default=MarketMode.P2P_DIRECT,
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    status: Mapped[MarketStatus] = mapped_column(
        default=MarketStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Settlement
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    winning_outcome_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outcomes.id"))
    
    # Relationships
    event: Mapped["Event"] = relationship(back_populates="markets")
    outcomes: Mapped[list["Outcome"]] = relationship(
        back_populates="market",
        cascade="all, delete-orphan",
        foreign_keys="Outcome.market_id"
    )
    orders: Mapped[list["Order"]] = relationship(
        back_populates="market",
        cascade="all, delete-orphan"
    )
    contracts: Mapped[list["Contract"]] = relationship(
        back_populates="market",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Market(id={self.id}, mode={self.market_mode.value}, type={self.market_type.value}, title='{self.title}')>"