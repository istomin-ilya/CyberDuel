"""
Unit tests for Pool Market models.
"""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus, MarketMode
from app.models.outcome import Outcome
from app.models.pool_bet import PoolBet
from app.models.pool_state import PoolState


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


class TestPoolModels:
    """Test Pool Market models are created correctly"""
    
    def test_market_mode_enum(self):
        """Test MarketMode enum values"""
        assert MarketMode.P2P_DIRECT.value == "p2p_direct"
        assert MarketMode.POOL_MARKET.value == "pool_market"
    
    def test_create_pool_market(self, db):
        """Test creating a pool market"""
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="G2",
            status=EventStatus.SCHEDULED
        )
        db.add(event)
        db.flush()
        
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            market_mode=MarketMode.POOL_MARKET,
            title="Match Winner (Pool)",
            status=MarketStatus.PENDING
        )
        db.add(market)
        db.commit()
        db.refresh(market)
        
        assert market.id is not None
        assert market.market_mode == MarketMode.POOL_MARKET
    
    def test_create_pool_bet(self, db):
        """Test creating a pool bet"""
        # Create user
        user = User(
            email="user@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00")
        )
        db.add(user)
        db.flush()
        
        # Create event
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="G2",
            status=EventStatus.OPEN
        )
        db.add(event)
        db.flush()
        
        # Create pool market
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            market_mode=MarketMode.POOL_MARKET,
            title="Match Winner (Pool)",
            status=MarketStatus.OPEN
        )
        db.add(market)
        db.flush()
        
        # Create outcome
        outcome = Outcome(
            market_id=market.id,
            name="NaVi"
        )
        db.add(outcome)
        db.flush()
        
        # Create pool bet
        pool_bet = PoolBet(
            user_id=user.id,
            market_id=market.id,
            outcome_id=outcome.id,
            amount=Decimal("100.00"),
            initial_pool_share_percentage=Decimal("100.000000"),  # 100% of pool
            pool_size_at_bet=Decimal("0.00"),  # First bet, pool was empty
            settled=False
        )
        db.add(pool_bet)
        db.commit()
        db.refresh(pool_bet)
        
        assert pool_bet.id is not None
        assert pool_bet.user_id == user.id
        assert pool_bet.amount == Decimal("100.00")
        assert pool_bet.initial_pool_share_percentage == Decimal("100.000000")
        assert pool_bet.pool_size_at_bet == Decimal("0.00")
        assert pool_bet.settled == False
    
    def test_create_pool_state(self, db):
        """Test creating pool state"""
        # Create event
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="G2",
            status=EventStatus.OPEN
        )
        db.add(event)
        db.flush()
        
        # Create pool market
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            market_mode=MarketMode.POOL_MARKET,
            title="Match Winner (Pool)",
            status=MarketStatus.OPEN
        )
        db.add(market)
        db.flush()
        
        # Create outcome
        outcome = Outcome(
            market_id=market.id,
            name="NaVi"
        )
        db.add(outcome)
        db.flush()
        
        # Create pool state
        pool_state = PoolState(
            market_id=market.id,
            outcome_id=outcome.id,
            total_staked=Decimal("500.00"),
            participant_count=3
        )
        db.add(pool_state)
        db.commit()
        db.refresh(pool_state)
        
        assert pool_state.id is not None
        assert pool_state.market_id == market.id
        assert pool_state.outcome_id == outcome.id
        assert pool_state.total_staked == Decimal("500.00")
        assert pool_state.participant_count == 3
    
    def test_pool_state_unique_constraint(self, db):
        """Test unique constraint on (market_id, outcome_id)"""
        # Create event, market, outcome
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="G2",
            status=EventStatus.OPEN
        )
        db.add(event)
        db.flush()
        
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            market_mode=MarketMode.POOL_MARKET,
            title="Match Winner (Pool)",
            status=MarketStatus.OPEN
        )
        db.add(market)
        db.flush()
        
        outcome = Outcome(
            market_id=market.id,
            name="NaVi"
        )
        db.add(outcome)
        db.flush()
        
        # Create first pool state
        pool_state1 = PoolState(
            market_id=market.id,
            outcome_id=outcome.id,
            total_staked=Decimal("500.00"),
            participant_count=3
        )
        db.add(pool_state1)
        db.commit()
        
        # Try to create duplicate
        pool_state2 = PoolState(
            market_id=market.id,
            outcome_id=outcome.id,
            total_staked=Decimal("600.00"),
            participant_count=4
        )
        db.add(pool_state2)
        
        with pytest.raises(Exception):  # SQLite raises IntegrityError
            db.commit()
    
    def test_user_pool_bets_relationship(self, db):
        """Test User -> PoolBet relationship"""
        # Create user
        user = User(
            email="user@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00")
        )
        db.add(user)
        db.flush()
        
        # Create event, market, outcome
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="G2",
            status=EventStatus.OPEN
        )
        db.add(event)
        db.flush()
        
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            market_mode=MarketMode.POOL_MARKET,
            title="Match Winner (Pool)",
            status=MarketStatus.OPEN
        )
        db.add(market)
        db.flush()
        
        outcome = Outcome(
            market_id=market.id,
            name="NaVi"
        )
        db.add(outcome)
        db.flush()
        
        # Create pool bets
        bet1 = PoolBet(
            user_id=user.id,
            market_id=market.id,
            outcome_id=outcome.id,
            amount=Decimal("100.00"),
            initial_pool_share_percentage=Decimal("100.000000"),  # First bet: 100%
            pool_size_at_bet=Decimal("0.00")  # Pool was empty
        )
        bet2 = PoolBet(
            user_id=user.id,
            market_id=market.id,
            outcome_id=outcome.id,
            amount=Decimal("50.00"),
            initial_pool_share_percentage=Decimal("33.333333"),  # 50/(100+50) = 33.33%
            pool_size_at_bet=Decimal("100.00")  # Pool had 100 before this bet
        )
        db.add_all([bet1, bet2])
        db.commit()