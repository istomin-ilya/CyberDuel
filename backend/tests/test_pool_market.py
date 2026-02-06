"""
Unit tests for Pool Market system (AMM).
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
from app.models.transaction import TransactionType
from app.services.amm import AMMCalculator, AMMException
from app.services.pool_market import PoolMarketService, PoolMarketException


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
def pool_market(db):
    """Create pool market with outcomes"""
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
    
    outcome_navi = Outcome(market_id=market.id, name="NaVi")
    outcome_g2 = Outcome(market_id=market.id, name="G2")
    db.add_all([outcome_navi, outcome_g2])
    db.flush()
    
    # Initialize pool states
    PoolMarketService.initialize_pool_states(db, market)
    
    db.commit()
    db.refresh(market)
    db.refresh(outcome_navi)
    db.refresh(outcome_g2)
    
    return {
        "market": market,
        "outcome_navi": outcome_navi,
        "outcome_g2": outcome_g2
    }


@pytest.fixture
def users(db):
    """Create test users"""
    user1 = User(
        email="user1@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00")
    )
    user2 = User(
        email="user2@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00")
    )
    user3 = User(
        email="user3@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00")
    )
    db.add_all([user1, user2, user3])
    db.commit()
    db.refresh(user1)
    db.refresh(user2)
    db.refresh(user3)
    
    return {"user1": user1, "user2": user2, "user3": user3}


class TestAMMCalculator:
    """Test AMM formula calculations"""
    
    def test_get_total_pool_empty(self, db, pool_market):
        """Test total pool calculation when empty"""
        market = pool_market["market"]
        
        total = AMMCalculator.get_total_pool(db, market.id)
        assert total == Decimal("0.00")
    
    def test_get_total_pool_with_bets(self, db, pool_market):
        """Test total pool calculation with bets"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        
        # Add stakes to pool states
        pool_navi = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_navi.id
        ).first()
        pool_navi.total_staked = Decimal("500.00")
        
        pool_g2 = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_g2.id
        ).first()
        pool_g2.total_staked = Decimal("300.00")
        
        db.commit()
        
        total = AMMCalculator.get_total_pool(db, market.id)
        assert total == Decimal("800.00")
    
    def test_get_current_odds_empty_pool(self, db, pool_market):
        """Test current odds when pool is empty"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        
        odds = AMMCalculator.get_current_odds(db, market.id, outcome_navi.id)
        # Empty pool should return default odds
        assert odds == Decimal("2.00")
    
    def test_get_current_odds_with_bets(self, db, pool_market):
        """Test current odds calculation with existing bets"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        
        # Set pool states
        pool_navi = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_navi.id
        ).first()
        pool_navi.total_staked = Decimal("500.00")
        
        pool_g2 = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_g2.id
        ).first()
        pool_g2.total_staked = Decimal("300.00")
        
        db.commit()
        
        # Total: 800, NaVi pool: 500
        # Odds = 800 / 500 = 1.60
        odds_navi = AMMCalculator.get_current_odds(db, market.id, outcome_navi.id)
        assert odds_navi == Decimal("1.60")
        
        # Total: 800, G2 pool: 300
        # Odds = 800 / 300 = 2.67
        odds_g2 = AMMCalculator.get_current_odds(db, market.id, outcome_g2.id)
        assert odds_g2 == Decimal("2.67")
    
    def test_calculate_pool_share_empty_pool(self):
        """Test pool share calculation when pool is empty (first bettor)"""
        # First bettor gets 100% of pool
        share = AMMCalculator.calculate_pool_share(
            current_pool_size=Decimal("0.00"),
            user_deposit=Decimal("100.00")
        )
        assert share == Decimal("100.000000")
    
    def test_calculate_pool_share_existing_pool(self):
        """Test pool share calculation with existing pool"""
        # Pool = 500, deposit = 300
        # New pool = 800
        # Share = 300/800 = 37.5%
        share = AMMCalculator.calculate_pool_share(
            current_pool_size=Decimal("500.00"),
            user_deposit=Decimal("300.00")
        )
        assert share == Decimal("37.500000")
    
    def test_calculate_pool_share_small_deposit(self):
        """Test pool share calculation with small deposit"""
        # Pool = 1000, deposit = 10
        # New pool = 1010
        # Share = 10/1010 = 0.990099%
        share = AMMCalculator.calculate_pool_share(
            current_pool_size=Decimal("1000.00"),
            user_deposit=Decimal("10.00")
        )
        assert share == Decimal("0.990099")
    
    def test_calculate_estimated_roi(self, db, pool_market):
        """Test estimated ROI calculation"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        
        # Set pool states
        # Pool NaVi: 700, Pool G2: 300, Total: 1000
        pool_navi = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_navi.id
        ).first()
        pool_navi.total_staked = Decimal("700.00")
        
        pool_g2 = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_g2.id
        ).first()
        pool_g2.total_staked = Decimal("300.00")
        
        db.commit()
        
        # NaVi: odds = 1000/700 = 1.43x, ROI = 43%
        roi_navi = AMMCalculator.calculate_estimated_roi(db, market.id, outcome_navi.id)
        assert roi_navi == Decimal("43.00")  # (1.43 - 1) * 100 = 43%
        
        # G2: odds = 1000/300 = 3.33x, ROI = 233%
        roi_g2 = AMMCalculator.calculate_estimated_roi(db, market.id, outcome_g2.id)
        assert roi_g2 == Decimal("233.00")  # (3.33 - 1) * 100 = 233%
    
    def test_get_all_current_odds(self, db, pool_market):
        """Test getting odds for all outcomes"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        
        # Set pool states
        pool_navi = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_navi.id
        ).first()
        pool_navi.total_staked = Decimal("500.00")
        
        pool_g2 = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_g2.id
        ).first()
        pool_g2.total_staked = Decimal("300.00")
        
        db.commit()
        
        odds_map = AMMCalculator.get_all_current_odds(db, market.id)
        
        assert odds_map[outcome_navi.id] == Decimal("1.60")
        assert odds_map[outcome_g2.id] == Decimal("2.67")


class TestPoolMarketService:
    """Test Pool Market service operations"""
    
    def test_initialize_pool_states(self, db, pool_market):
        """Test pool state initialization"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        
        # Already initialized in fixture, check they exist
        pool_navi = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_navi.id
        ).first()
        
        pool_g2 = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_g2.id
        ).first()
        
        assert pool_navi is not None
        assert pool_navi.total_staked == Decimal("0.00")
        assert pool_navi.participant_count == 0
        
        assert pool_g2 is not None
        assert pool_g2.total_staked == Decimal("0.00")
        assert pool_g2.participant_count == 0
    
    def test_place_pool_bet(self, db, pool_market, users):
        """Test placing a bet in pool market"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        user1 = users["user1"]
        
        # Place bet
        bet = PoolMarketService.place_pool_bet(
            db=db,
            user=user1,
            market_id=market.id,
            outcome_id=outcome_navi.id,
            amount=Decimal("100.00")
        )
        
        db.refresh(user1)
        
        # Check bet created
        assert bet.id is not None
        assert bet.user_id == user1.id
        assert bet.amount == Decimal("100.00")
        assert bet.initial_pool_share_percentage == Decimal("100.000000")  # First bet = 100%
        assert bet.pool_size_at_bet == Decimal("0.00")  # Pool was empty
        assert bet.settled == False
        
        # Check user balance
        assert user1.balance_available == Decimal("900.00")
        assert user1.balance_locked == Decimal("100.00")
        
        # Check pool state updated
        pool_state = db.query(PoolState).filter(
            PoolState.market_id == market.id,
            PoolState.outcome_id == outcome_navi.id
        ).first()
        
        assert pool_state.total_staked == Decimal("100.00")
        assert pool_state.participant_count == 1
    
    def test_place_multiple_bets_updates_shares(self, db, pool_market, users):
        """Test that multiple bets calculate pool shares correctly"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        user1 = users["user1"]
        user2 = users["user2"]
        
        # User1 bets on NaVi (first bet, gets 100%)
        bet1 = PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("500.00")
        )
        assert bet1.initial_pool_share_percentage == Decimal("100.000000")
        assert bet1.pool_size_at_bet == Decimal("0.00")
        
        # User2 bets on G2 (first bet on G2, gets 100% of G2 pool)
        bet2 = PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_g2.id, Decimal("300.00")
        )
        assert bet2.initial_pool_share_percentage == Decimal("100.000000")
        assert bet2.pool_size_at_bet == Decimal("0.00")
        
        # User3 adds more to NaVi pool
        # Current NaVi pool = 500, adding 200
        # New pool = 700, share = 200/700 = 28.57%
        user3 = users["user3"]
        bet3 = PoolMarketService.place_pool_bet(
            db, user3, market.id, outcome_navi.id, Decimal("200.00")
        )
        assert bet3.initial_pool_share_percentage == Decimal("28.571429")  # 200/700
        assert bet3.pool_size_at_bet == Decimal("500.00")
    
    def test_cannot_bet_on_closed_market(self, db, pool_market, users):
        """Test cannot place bet on closed market"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        user1 = users["user1"]
        
        # Close market
        market.status = MarketStatus.LOCKED
        db.commit()
        
        # Try to bet
        with pytest.raises(PoolMarketException, match="not open for betting"):
            PoolMarketService.place_pool_bet(
                db, user1, market.id, outcome_navi.id, Decimal("100.00")
            )
    
    def test_cannot_bet_on_p2p_market(self, db, users):
        """Test cannot place pool bet on P2P market"""
        user1 = users["user1"]
        
        # Create P2P market
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
            market_mode=MarketMode.P2P_DIRECT,  # P2P not Pool
            title="Match Winner (P2P)",
            status=MarketStatus.OPEN
        )
        db.add(market)
        db.flush()
        
        outcome = Outcome(market_id=market.id, name="NaVi")
        db.add(outcome)
        db.commit()
        
        # Try to place pool bet
        with pytest.raises(PoolMarketException, match="not a pool market"):
            PoolMarketService.place_pool_bet(
                db, user1, market.id, outcome.id, Decimal("100.00")
            )
    
    def test_get_pool_state(self, db, pool_market, users):
        """Test getting pool state"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        user1 = users["user1"]
        user2 = users["user2"]
        
        # Place some bets
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("700.00")
        )
        PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_g2.id, Decimal("300.00")
        )
        
        # Get state
        state = PoolMarketService.get_pool_state(db, market.id)
        
        assert state["market_id"] == market.id
        assert state["total_pool"] == "1000.00"
        assert len(state["outcomes"]) == 2
        
        # Find NaVi outcome
        navi_outcome = next(o for o in state["outcomes"] if o["name"] == "NaVi")
        assert navi_outcome["total_staked"] == "700.00"
        assert navi_outcome["participant_count"] == 1
        assert navi_outcome["estimated_odds"] == "1.43"  # 1000/700
        assert navi_outcome["estimated_roi"] == "43.00"  # (1.43 - 1) * 100
        
        # Find G2 outcome
        g2_outcome = next(o for o in state["outcomes"] if o["name"] == "G2")
        assert g2_outcome["total_staked"] == "300.00"
        assert g2_outcome["estimated_odds"] == "3.33"  # 1000/300
        assert g2_outcome["estimated_roi"] == "233.00"  # (3.33 - 1) * 100
    
    def test_get_user_pool_bets(self, db, pool_market, users):
        """Test getting user's pool bets"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        user1 = users["user1"]
        
        # Place bets
        bet1 = PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("100.00")
        )
        bet2 = PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("50.00")
        )
        
        # Get user's bets
        bets = PoolMarketService.get_user_pool_bets(db, user1.id)
        
        assert len(bets) == 2
        assert bets[0].id in [bet1.id, bet2.id]
        assert bets[1].id in [bet1.id, bet2.id]