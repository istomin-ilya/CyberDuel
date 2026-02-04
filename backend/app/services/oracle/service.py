# app/services/oracle/service.py
"""
High-level Oracle Service for match result verification.

This service provides a clean interface for the rest of the application
to interact with oracle providers without knowing implementation details.
"""
from typing import Optional
from sqlalchemy.orm import Session

from .factory import OracleFactory
from .base import MatchResult, MatchNotFoundException, OracleAPIException
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome


class OracleService:
    """
    Service for fetching and verifying match results.
    
    Acts as a bridge between the application and external APIs.
    """
    
    def __init__(self, provider_name: str = "mock", api_key: Optional[str] = None):
        """
        Initialize oracle service with a provider.
        
        Args:
            provider_name: Oracle provider to use ("mock", "pandascore", etc)
            api_key: API key if required by provider
        """
        self.provider = OracleFactory.create(provider_name, api_key=api_key)
    
    def fetch_event_result(self, event: Event) -> MatchResult:
        """
        Fetch result for an event.
        
        Args:
            event: Event object with external_match_id
            
        Returns:
            MatchResult: Match result from provider
            
        Raises:
            ValueError: If event has no external_match_id
            MatchNotFoundException: If match not found in provider
            OracleAPIException: If API call fails
        """
        if not event.external_match_id:
            raise ValueError(f"Event {event.id} has no external_match_id")
        
        return self.provider.fetch_match_result(event.external_match_id)
    
    def determine_winning_outcome(
        self,
        db: Session,
        market: Market,
        match_result: MatchResult
    ) -> Optional[Outcome]:
        """
        Determine which outcome won based on match result.
        
        Maps external match result to internal market outcome.
        
        Args:
            db: Database session
            market: Market to resolve
            match_result: Result from oracle provider
            
        Returns:
            Outcome: Winning outcome, or None if cannot determine
            
        Example:
            Market: "Match Winner"
            Outcomes: ["NaVi", "Spirit"]
            Result: winner="team_a"
            
            -> Returns outcome with name="NaVi"
        """
        # Get event to map team_a/team_b
        event = db.query(Event).filter(Event.id == market.event_id).first()
        if not event:
            return None
        
        # Map winner to team name
        if match_result.winner == "team_a":
            winning_team = event.team_a
        elif match_result.winner == "team_b":
            winning_team = event.team_b
        else:
            return None  # Draw or unknown
        
        # Find matching outcome
        outcome = db.query(Outcome).filter(
            Outcome.market_id == market.id,
            Outcome.name == winning_team
        ).first()
        
        return outcome
    
    def verify_event_can_settle(self, event: Event) -> bool:
        """
        Verify that an event can be settled.
        
        Checks:
        - Event has external_match_id
        - Match exists in provider
        - Match is finished
        
        Args:
            event: Event to verify
            
        Returns:
            bool: True if event can be settled
        """
        if not event.external_match_id:
            return False
        
        try:
            # Check if match exists
            if not self.provider.verify_match_exists(event.external_match_id):
                return False
            
            # Check if match is finished
            result = self.provider.fetch_match_result(event.external_match_id)
            return result.status == "finished"
            
        except (MatchNotFoundException, OracleAPIException):
            return False
    
    def get_upcoming_matches_for_events(
        self,
        game_type: Optional[str] = None,
        limit: int = 10
    ) -> list[dict]:
        """
        Get upcoming matches from provider for creating events.
        
        Useful for automatically importing events from external API.
        
        Args:
            game_type: Filter by game type
            limit: Maximum matches to return
            
        Returns:
            list: List of match data suitable for Event creation
        """
        return self.provider.get_upcoming_matches(game_type, limit)