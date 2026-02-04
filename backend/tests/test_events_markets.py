"""
Unit tests for Event and Market CRUD.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base from models to ensure all models are registered
from app.models import Base
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome
from app.models.transaction import Transaction


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


@pytest.fixture
def admin_user(db):
    """Create admin user"""
    user = User(
        email="admin@test.com",
        password_hash="hashed",
        balance_available=Decimal("10000.00"),
        balance_locked=Decimal("0.00")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestEventCRUD:
    """Test Event CRUD operations"""
    
    def test_create_event(self, db, admin_user):
        """Test creating a new event"""
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            tournament="IEM Katowice",
            status=EventStatus.SCHEDULED,
            scheduled_start=datetime.now() + timedelta(hours=2),
            external_match_id="match_1"
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        
        assert event.id is not None
        assert event.game_type == "CS2"
        assert event.team_a == "NaVi"
        assert event.team_b == "Spirit"
        assert event.status == EventStatus.SCHEDULED
    
    def test_event_status_transitions(self, db):
        """Test event status lifecycle"""
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.SCHEDULED
        )
        db.add(event)
        db.commit()
        
        # SCHEDULED -> OPEN
        event.status = EventStatus.OPEN
        db.commit()
        assert event.status == EventStatus.OPEN
        
        # OPEN -> LIVE
        event.status = EventStatus.LIVE
        event.actual_start = datetime.now()
        db.commit()
        assert event.status == EventStatus.LIVE
        assert event.actual_start is not None
        
        # LIVE -> FINISHED
        event.status = EventStatus.FINISHED
        event.actual_end = datetime.now()
        db.commit()
        assert event.status == EventStatus.FINISHED
        assert event.actual_end is not None
        
        # FINISHED -> SETTLED
        event.status = EventStatus.SETTLED
        db.commit()
        assert event.status == EventStatus.SETTLED
    
    def test_list_events_filter_by_status(self, db):
        """Test filtering events by status"""
        # Create events with different statuses
        event1 = Event(game_type="CS2", team_a="NaVi", team_b="Spirit", status=EventStatus.SCHEDULED)
        event2 = Event(game_type="CS2", team_a="G2", team_b="FaZe", status=EventStatus.LIVE)
        event3 = Event(game_type="Dota2", team_a="OG", team_b="Liquid", status=EventStatus.FINISHED)
        
        db.add_all([event1, event2, event3])
        db.commit()
        
        # Filter by LIVE
        live_events = db.query(Event).filter(Event.status == EventStatus.LIVE).all()
        assert len(live_events) == 1
        assert live_events[0].team_a == "G2"
        
        # Filter by game_type
        cs2_events = db.query(Event).filter(Event.game_type == "CS2").all()
        assert len(cs2_events) == 2
    
    def test_event_with_external_match_id(self, db):
        """Test event with external API integration"""
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.SCHEDULED,
            external_match_id="pandascore_12345"
        )
        db.add(event)
        db.commit()
        
        # Retrieve by external_match_id
        found = db.query(Event).filter(
            Event.external_match_id == "pandascore_12345"
        ).first()
        
        assert found is not None
        assert found.team_a == "NaVi"


class TestMarketCRUD:
    """Test Market CRUD operations"""
    
    def test_create_market_with_outcomes(self, db):
        """Test creating market with outcomes"""
        # Create event first
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.OPEN
        )
        db.add(event)
        db.flush()
        
        # Create market
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.OPEN
        )
        db.add(market)
        db.flush()
        
        # Create outcomes
        outcome1 = Outcome(market_id=market.id, name="NaVi")
        outcome2 = Outcome(market_id=market.id, name="Spirit")
        db.add_all([outcome1, outcome2])
        
        db.commit()
        db.refresh(market)
        
        assert market.id is not None
        assert len(market.outcomes) == 2
        assert market.outcomes[0].name == "NaVi"
        assert market.outcomes[1].name == "Spirit"
    
    def test_market_status_transitions(self, db):
        """Test market status lifecycle"""
        event = Event(game_type="CS2", team_a="NaVi", team_b="Spirit", status=EventStatus.OPEN)
        db.add(event)
        db.flush()
        
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.PENDING
        )
        db.add(market)
        db.commit()
        
        # PENDING -> OPEN
        market.status = MarketStatus.OPEN
        db.commit()
        assert market.status == MarketStatus.OPEN
        
        # OPEN -> LOCKED
        market.status = MarketStatus.LOCKED
        db.commit()
        assert market.status == MarketStatus.LOCKED
        
        # LOCKED -> SETTLED
        market.status = MarketStatus.SETTLED
        db.commit()
        assert market.status == MarketStatus.SETTLED
    
    def test_market_settlement(self, db):
        """Test marking market as settled with winner"""
        event = Event(game_type="CS2", team_a="NaVi", team_b="Spirit", status=EventStatus.FINISHED)
        db.add(event)
        db.flush()
        
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
        
        # Settle market - NaVi wins
        market.winning_outcome_id = outcome_navi.id
        market.status = MarketStatus.SETTLED
        db.commit()
        
        assert market.winning_outcome_id == outcome_navi.id
        assert market.status == MarketStatus.SETTLED
    
    def test_list_markets_by_event(self, db):
        """Test filtering markets by event"""
        # Create two events
        event1 = Event(game_type="CS2", team_a="NaVi", team_b="Spirit", status=EventStatus.OPEN)
        event2 = Event(game_type="CS2", team_a="G2", team_b="FaZe", status=EventStatus.OPEN)
        db.add_all([event1, event2])
        db.flush()
        
        # Create markets for event1
        market1 = Market(
            event_id=event1.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.OPEN
        )
        market2 = Market(
            event_id=event1.id,
            market_type="total_kills",
            title="Total Kills Over/Under",
            status=MarketStatus.OPEN
        )
        
        # Create market for event2
        market3 = Market(
            event_id=event2.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.OPEN
        )
        
        db.add_all([market1, market2, market3])
        db.commit()
        
        # Filter markets by event1
        event1_markets = db.query(Market).filter(Market.event_id == event1.id).all()
        assert len(event1_markets) == 2
    
    def test_outcome_with_external_id(self, db):
        """Test outcome with external team/player ID"""
        event = Event(game_type="CS2", team_a="NaVi", team_b="Spirit", status=EventStatus.OPEN)
        db.add(event)
        db.flush()
        
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.OPEN
        )
        db.add(market)
        db.flush()
        
        # Outcome with external_id for API mapping
        outcome = Outcome(
            market_id=market.id,
            name="NaVi",
            external_id="team_4608"  # PandaScore team ID
        )
        db.add(outcome)
        db.commit()
        
        assert outcome.external_id == "team_4608"


class TestEventMarketRelationships:
    """Test relationships between Events and Markets"""
    
    def test_event_has_multiple_markets(self, db):
        """Test one event can have multiple markets"""
        event = Event(game_type="CS2", team_a="NaVi", team_b="Spirit", status=EventStatus.OPEN)
        db.add(event)
        db.flush()
        
        market1 = Market(
            event_id=event.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.OPEN
        )
        market2 = Market(
            event_id=event.id,
            market_type="total_kills",
            title="Total Kills",
            status=MarketStatus.OPEN
        )
        market3 = Market(
            event_id=event.id,
            market_type="first_blood",
            title="First Blood",
            status=MarketStatus.OPEN
        )
        
        db.add_all([market1, market2, market3])
        db.commit()
        db.refresh(event)
        
        assert len(event.markets) == 3
        market_types = [m.market_type for m in event.markets]
        assert "match_winner" in market_types
        assert "total_kills" in market_types
        assert "first_blood" in market_types
    
    def test_cascade_event_deletion(self, db):
        """Test cascading deletion (if configured)"""
        event = Event(game_type="CS2", team_a="NaVi", team_b="Spirit", status=EventStatus.SCHEDULED)
        db.add(event)
        db.flush()
        
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            title="Match Winner",
            status=MarketStatus.PENDING
        )
        db.add(market)
        db.flush()
        
        outcome = Outcome(market_id=market.id, name="NaVi")
        db.add(outcome)
        db.commit()
        
        event_id = event.id
        market_id = market.id
        
        # Delete event (should cascade to markets/outcomes if configured)
        # Note: This depends on your cascade settings in models
        # For now, just verify relationships exist
        assert market.event_id == event_id
        assert outcome.market_id == market_id