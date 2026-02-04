"""
Unit tests for Oracle system.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome
from app.services.oracle import OracleFactory, OracleService, MatchNotFoundException


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create test database session"""
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


class TestOracleFactory:
    """Test Oracle Factory pattern"""
    
    def test_create_mock_provider(self):
        """Test creating mock provider"""
        oracle = OracleFactory.create("mock")
        
        assert oracle is not None
        assert oracle.__class__.__name__ == "MockOracleProvider"
    
    def test_list_providers(self):
        """Test listing available providers"""
        providers = OracleFactory.list_providers()
        
        assert "mock" in providers
        assert len(providers) >= 1
    
    def test_create_invalid_provider(self):
        """Test creating non-existent provider raises error"""
        with pytest.raises(ValueError, match="Unknown oracle provider"):
            OracleFactory.create("nonexistent")


class TestMockProvider:
    """Test Mock Oracle Provider"""
    
    def test_fetch_match_result_match1(self):
        """Test fetching mock match result"""
        oracle = OracleFactory.create("mock")
        
        result = oracle.fetch_match_result("match_1")
        
        assert result.match_id == "match_1"
        assert result.winner == "team_a"
        assert result.score_a == 16
        assert result.score_b == 12
        assert result.status == "finished"
        assert result.metadata["team_a"] == "NaVi"
        assert result.metadata["team_b"] == "Spirit"
    
    def test_fetch_match_result_match2(self):
        """Test fetching different mock match"""
        oracle = OracleFactory.create("mock")
        
        result = oracle.fetch_match_result("match_2")
        
        assert result.match_id == "match_2"
        assert result.winner == "team_b"
        assert result.score_a == 13
        assert result.score_b == 16
    
    def test_fetch_scheduled_match(self):
        """Test fetching scheduled match (not finished)"""
        oracle = OracleFactory.create("mock")
        
        result = oracle.fetch_match_result("match_3")
        
        assert result.status == "scheduled"
        assert result.winner == "unknown"
        assert result.score_a == 0
        assert result.score_b == 0
    
    def test_fetch_nonexistent_match(self):
        """Test fetching non-existent match raises error"""
        oracle = OracleFactory.create("mock")
        
        with pytest.raises(MatchNotFoundException):
            oracle.fetch_match_result("match_999")
    
    def test_verify_match_exists(self):
        """Test verifying match existence"""
        oracle = OracleFactory.create("mock")
        
        assert oracle.verify_match_exists("match_1") is True
        assert oracle.verify_match_exists("match_2") is True
        assert oracle.verify_match_exists("match_999") is False
    
    def test_get_upcoming_matches(self):
        """Test getting upcoming matches"""
        oracle = OracleFactory.create("mock")
        
        matches = oracle.get_upcoming_matches()
        
        # Should only return scheduled/live matches
        assert len(matches) >= 0
        for match in matches:
            assert match["status"] in ["scheduled", "live"]
    
    def test_get_upcoming_matches_filter_by_game(self):
        """Test filtering upcoming matches by game type"""
        oracle = OracleFactory.create("mock")
        
        cs2_matches = oracle.get_upcoming_matches(game_type="CS2")
        dota_matches = oracle.get_upcoming_matches(game_type="Dota2")
        
        # Verify filtering works (depends on mock data)
        for match in cs2_matches:
            assert match["game_type"] == "CS2"


class TestOracleService:
    """Test high-level Oracle Service"""
    
    def test_fetch_event_result(self, db):
        """Test fetching result for an event"""
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.LIVE,
            external_match_id="match_1"
        )
        db.add(event)
        db.commit()
        
        oracle = OracleService(provider_name="mock")
        result = oracle.fetch_event_result(event)
        
        assert result.match_id == "match_1"
        assert result.winner == "team_a"
        assert result.status == "finished"
    
    def test_fetch_event_without_external_id(self, db):
        """Test fetching result for event without external_match_id"""
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.LIVE,
            external_match_id=None
        )
        db.add(event)
        db.commit()
        
        oracle = OracleService(provider_name="mock")
        
        with pytest.raises(ValueError, match="has no external_match_id"):
            oracle.fetch_event_result(event)
    
    def test_determine_winning_outcome(self, db):
        """Test determining winning outcome from match result"""
        # Create event
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.FINISHED,
            external_match_id="match_1"
        )
        db.add(event)
        db.flush()
        
        # Create market with outcomes
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.LOCKED
        )
        db.add(market)
        db.flush()
        
        outcome_navi = Outcome(market_id=market.id, name="NaVi")
        outcome_spirit = Outcome(market_id=market.id, name="Spirit")
        db.add_all([outcome_navi, outcome_spirit])
        db.commit()
        
        # Fetch result and determine winner
        oracle = OracleService(provider_name="mock")
        result = oracle.fetch_event_result(event)
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        
        # match_1 winner is team_a (NaVi)
        assert winning_outcome is not None
        assert winning_outcome.name == "NaVi"
        assert winning_outcome.id == outcome_navi.id
    
    def test_verify_event_can_settle(self, db):
        """Test verifying if event can be settled"""
        # Finished event
        event_finished = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.FINISHED,
            external_match_id="match_1"
        )
        db.add(event_finished)
        
        # Scheduled event
        event_scheduled = Event(
            game_type="CS2",
            team_a="OG",
            team_b="Liquid",
            status=EventStatus.SCHEDULED,
            external_match_id="match_3"
        )
        db.add(event_scheduled)
        
        # Event without external_match_id
        event_no_id = Event(
            game_type="CS2",
            team_a="G2",
            team_b="FaZe",
            status=EventStatus.FINISHED,
            external_match_id=None
        )
        db.add(event_no_id)
        
        db.commit()
        
        oracle = OracleService(provider_name="mock")
        
        # Finished event can settle
        assert oracle.verify_event_can_settle(event_finished) is True
        
        # Scheduled event cannot settle yet
        assert oracle.verify_event_can_settle(event_scheduled) is False
        
        # Event without external_match_id cannot settle
        assert oracle.verify_event_can_settle(event_no_id) is False
    
    def test_get_upcoming_matches_for_events(self):
        """Test getting upcoming matches for event creation"""
        oracle = OracleService(provider_name="mock")
        
        matches = oracle.get_upcoming_matches_for_events(limit=5)
        
        assert isinstance(matches, list)
        # Should contain upcoming matches
        for match in matches:
            assert "id" in match
            assert "team_a" in match
            assert "team_b" in match
            assert "game_type" in match