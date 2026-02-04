"""
Event model - Esports matches/tournaments.
"""
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .market import Market


class EventStatus(str, Enum):
    """Event lifecycle states."""
    SCHEDULED = "SCHEDULED"
    OPEN = "OPEN"
    LIVE = "LIVE"
    FINISHED = "FINISHED"      # Матч закончен, идет верификация маркетов
    SETTLED = "SETTLED"        # Все маркеты разрешены
    CANCELLED = "CANCELLED"


class GameType(str, Enum):
    """Supported game types."""
    CS2 = "CS2"
    DOTA2 = "DOTA2"
    LOL = "LOL"


class Event(Base, TimestampMixin):
    """
    Esports event (match).
    
    Event represents the actual match happening.
    Each event can have multiple Markets (betting markets).
    
    Example:
        Event: "NaVi vs G2 - IEM Katowice 2025"
        Markets:
          - Match Winner (NaVi / G2)
          - Total Kills > 40 (Yes / No)
          - First Blood (NaVi / G2)
    
    Attributes:
        game_type: Which game (CS2, Dota2, LoL)
        team_a: First team name
        team_b: Second team name
        tournament: Tournament/league name (optional)
        team_a_external_id: External API identifier for team A
        team_b_external_id: External API identifier for team B
        external_match_id: Match ID in external system (PandaScore, etc)
        status: Current lifecycle state
        scheduled_start: When match is planned to start
        actual_start: When match actually started
        actual_end: When match actually ended
    """
    __tablename__ = "events"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    
    # Game and teams
    game_type: Mapped[GameType] = mapped_column(nullable=False, index=True)
    team_a: Mapped[str] = mapped_column(String(100), nullable=False)
    team_b: Mapped[str] = mapped_column(String(100), nullable=False)
    tournament: Mapped[Optional[str]] = mapped_column(String(200))
    
    # External identifiers (for API integration)
    team_a_external_id: Mapped[Optional[str]] = mapped_column(String(100))
    team_b_external_id: Mapped[Optional[str]] = mapped_column(String(100))
    external_match_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    
    # Lifecycle
    status: Mapped[EventStatus] = mapped_column(
        default=EventStatus.SCHEDULED,
        nullable=False,
        index=True
    )
    
    # Timing
    scheduled_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    markets: Mapped[list["Market"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Event(id={self.id}, {self.team_a} vs {self.team_b}, status={self.status.value})>"