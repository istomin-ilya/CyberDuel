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
    
    def test_calculate_locked_odds(self, db, pool_market):
        """Test locked odds calculation for new bet"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        
        # Set initial pool states
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
        
        # User wants to bet 100 on NaVi
        # Current total: 800, current NaVi pool: 500
        # New total: 900, new NaVi pool: 600
        # Locked odds = 900 / 600 = 1.50
        locked_odds = AMMCalculator.calculate_locked_odds(
            db, market.id, outcome_navi.id, Decimal("100.00")
        )
        assert locked_odds == Decimal("1.50")
    
    def test_calculate_potential_payout(self):
        """Test potential payout calculation"""
        payout = AMMCalculator.calculate_potential_payout(
            locked_odds=Decimal("1.80"),
            bet_amount=Decimal("100.00")
        )
        assert payout == Decimal("180.00")
    
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
    
    def test_place_multiple_bets_updates_odds(self, db, pool_market, users):
        """Test that multiple bets update odds correctly"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        user1 = users["user1"]
        user2 = users["user2"]
        
        # User1 bets on NaVi
        bet1 = PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("100.00")
        )
        
        # User2 bets on G2 (different outcome)
        bet2 = PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_g2.id, Decimal("100.00")
        )
        
        # Both should get same odds (2.00) since pools are equal
        assert bet1.locked_odds == Decimal("2.00")
        assert bet2.locked_odds == Decimal("2.00")
        
        # User3 bets MORE on NaVi
        user3 = users["user3"]
        bet3 = PoolMarketService.place_pool_bet(
            db, user3, market.id, outcome_navi.id, Decimal("200.00")
        )
        
        # User3 should get worse odds (NaVi pool is now bigger)
        # Total before bet3: 200 (100 NaVi + 100 G2)
        # After bet3: 400 total, 300 NaVi pool
        # Locked odds: 400 / 300 = 1.33
        assert bet3.locked_odds == Decimal("1.33")
    
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
            db, user1, market.id, outcome_navi.id, Decimal("500.00")
        )
        PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_g2.id, Decimal("300.00")
        )
        
        # Get state
        state = PoolMarketService.get_pool_state(db, market.id)
        
        assert state["market_id"] == market.id
        assert state["total_pool"] == "800.00"
        assert len(state["outcomes"]) == 2
        
        # Find NaVi outcome
        navi_outcome = next(o for o in state["outcomes"] if o["name"] == "NaVi")
        assert navi_outcome["total_staked"] == "500.00"
        assert navi_outcome["participant_count"] == 1
        assert navi_outcome["current_odds"] == "1.60"
    
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