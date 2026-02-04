# app/services/oracle/base.py
"""
Base interface for external API oracle providers.
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime


class MatchResult:
    """Standardized match result format across all providers"""
    def __init__(
        self,
        match_id: str,
        winner: str,  # "team_a" or "team_b"
        score_a: int,
        score_b: int,
        status: str,  # "finished", "live", "scheduled", "cancelled"
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.match_id = match_id
        self.winner = winner
        self.score_a = score_a
        self.score_b = score_b
        self.status = status
        self.started_at = started_at
        self.finished_at = finished_at
        self.metadata = metadata or {}


class OracleProvider(ABC):
    """
    Abstract base class for oracle providers.
    
    All oracle providers (PandaScore, Mock, HLTV, etc) must implement
    these methods. This allows switching providers without changing code.
    """
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """
        Initialize provider.
        
        Args:
            api_key: API key for authenticated providers
            **kwargs: Additional provider-specific config
        """
        self.api_key = api_key
        self.config = kwargs
    
    @abstractmethod
    def fetch_match_result(self, external_match_id: str) -> MatchResult:
        """
        Fetch match result from external API.
        
        Args:
            external_match_id: ID of the match in external system
            
        Returns:
            MatchResult: Standardized match result
            
        Raises:
            MatchNotFoundException: If match not found
            OracleAPIException: If API call fails
        """
        pass
    
    @abstractmethod
    def verify_match_exists(self, external_match_id: str) -> bool:
        """
        Verify that a match exists in external system.
        
        Args:
            external_match_id: ID to verify
            
        Returns:
            bool: True if match exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_upcoming_matches(
        self,
        game_type: Optional[str] = None,
        limit: int = 10
    ) -> list[Dict[str, Any]]:
        """
        Get list of upcoming matches.
        
        Useful for creating events programmatically.
        
        Args:
            game_type: Filter by game (CS2, Dota2, LoL, etc)
            limit: Maximum number of matches to return
            
        Returns:
            list: List of match data dictionaries
        """
        pass


# Custom exceptions
class OracleException(Exception):
    """Base exception for oracle errors"""
    pass


class MatchNotFoundException(OracleException):
    """Raised when match is not found in external API"""
    pass


class OracleAPIException(OracleException):
    """Raised when external API returns an error"""
    pass