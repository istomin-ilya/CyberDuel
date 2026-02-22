# app/services/oracle/mock.py
"""
Mock oracle provider for development and testing.
Returns fake data without calling external APIs.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from ..base import OracleProvider, MatchResult, MatchNotFoundException


class MockOracleProvider(OracleProvider):
    """
    Mock provider that returns fake data.
    
    Useful for:
    - Development without API keys
    - Testing
    - Demos
    """
    
    # Fake match database
    MOCK_MATCHES = {
        "match_1": {
            "id": "match_1",
            "team_a": "NaVi",
            "team_b": "Spirit",
            "game_type": "CS2",
            "winner": "team_a",
            "score_a": 16,
            "score_b": 12,
            "status": "finished",
            "started_at": datetime.now(timezone.utc) - timedelta(hours=3),
            "finished_at": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        "match_2": {
            "id": "match_2",
            "team_a": "G2",
            "team_b": "FaZe",
            "game_type": "CS2",
            "winner": "team_b",
            "score_a": 13,
            "score_b": 16,
            "status": "finished",
            "started_at": datetime.now(timezone.utc) - timedelta(hours=5),
            "finished_at": datetime.now(timezone.utc) - timedelta(hours=3),
        },
        "match_3": {
            "id": "match_3",
            "team_a": "OG",
            "team_b": "Liquid",
            "game_type": "Dota2",
            "winner": None,
            "score_a": 0,
            "score_b": 0,
            "status": "scheduled",
            "started_at": datetime.now(timezone.utc) + timedelta(hours=2),
            "finished_at": None,
        },
    }
    
    def __init__(self, api_key: Optional[str] = None, **kwargs):
        """Initialize mock provider (no API key needed)"""
        super().__init__(api_key, **kwargs)
    
    def fetch_match_result(self, external_match_id: str) -> MatchResult:
        """
        Fetch mock match result.
        
        Args:
            external_match_id: Match ID (e.g., "match_1")
            
        Returns:
            MatchResult: Fake match result
            
        Raises:
            MatchNotFoundException: If match_id not in MOCK_MATCHES
        """
        match_data = self.MOCK_MATCHES.get(external_match_id)
        
        if not match_data:
            raise MatchNotFoundException(
                f"Mock match {external_match_id} not found. "
                f"Available: {list(self.MOCK_MATCHES.keys())}"
            )
        
        return MatchResult(
            match_id=match_data["id"],
            winner=match_data["winner"] or "unknown",
            score_a=match_data["score_a"],
            score_b=match_data["score_b"],
            status=match_data["status"],
            started_at=match_data["started_at"],
            finished_at=match_data["finished_at"],
            metadata={
                "team_a": match_data["team_a"],
                "team_b": match_data["team_b"],
                "game_type": match_data["game_type"],
            }
        )
    
    def verify_match_exists(self, external_match_id: str) -> bool:
        """
        Verify mock match exists.
        
        Args:
            external_match_id: Match ID to check
            
        Returns:
            bool: True if exists in MOCK_MATCHES
        """
        return external_match_id in self.MOCK_MATCHES
    
    def get_upcoming_matches(
        self,
        game_type: Optional[str] = None,
        limit: int = 10
    ) -> list[Dict[str, Any]]:
        """
        Get list of upcoming mock matches.
        
        Args:
            game_type: Filter by game (CS2, Dota2, etc)
            limit: Maximum matches to return
            
        Returns:
            list: List of upcoming matches
        """
        matches = []
        
        for match_id, match_data in self.MOCK_MATCHES.items():
            # Filter by status (only scheduled/live)
            if match_data["status"] not in ["scheduled", "live"]:
                continue
            
            # Filter by game_type if specified
            if game_type and match_data["game_type"] != game_type:
                continue
            
            matches.append({
                "id": match_id,
                "team_a": match_data["team_a"],
                "team_b": match_data["team_b"],
                "game_type": match_data["game_type"],
                "scheduled_start": match_data["started_at"],
                "status": match_data["status"],
            })
            
            if len(matches) >= limit:
                break
        
        return matches