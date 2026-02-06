"""
Integration tests for Pool Market Service.
Tests complete user flows with pool betting.
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
from app.models.transaction import Transaction, TransactionType
from app.services.pool_market import PoolMarketService, PoolMarketException
from app.services.escrow import InsufficientFundsError


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
        balance_available=Decimal("500.00")
    )
    db.add_all([user1, user2, user3])
    db.commit()
    db.refresh(user1)
    db.refresh(user2)
    db.refresh(user3)
    
    return {"user1": user1, "user2": user2, "user3": user3}


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
    db.commit()
    db.refresh(market)
    db.refresh(outcome_navi)
    db.refresh(outcome_g2)
    
    return {
        "market": market,
        "outcome_navi": outcome_navi,
        "outcome_g2": outcome_g2
    }


class TestPoolBettingFlow:
    """Test complete pool betting flows"""
    
    def test_single_user_bet_and_win(self, db, pool_market, users):
        """Test user bets, wins, and receives payout from liquidity pool"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        user1 = users["user1"]
        user2 = users["user2"]
        
        # Test case: Equal pools
        # Pool NaVi: 500$ (User1)
        # Pool G2: 500$ (User2)
        # Total: 1000$
        
        # User1 bets on NaVi
        bet1 = PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("500.00")
        )
        
        # User2 bets on G2
        bet2 = PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_g2.id, Decimal("500.00")
        )
        
        db.refresh(user1)
        db.refresh(user2)
        
        # Check balances after betting
        assert user1.balance_available == Decimal("500.00")
        assert user1.balance_locked == Decimal("500.00")
        assert user2.balance_available == Decimal("500.00")
        assert user2.balance_locked == Decimal("500.00")
        
        # Check pool shares
        assert bet1.initial_pool_share_percentage == Decimal("100.000000")  # 100% of NaVi pool
        assert bet2.initial_pool_share_percentage == Decimal("100.000000")  # 100% of G2 pool
        
        # Settle market (NaVi wins)
        market.status = MarketStatus.SETTLED
        market.winning_outcome_id = outcome_navi.id
        db.commit()
        
        # Settle pool market
        result = PoolMarketService.settle_pool_market(
            db, market.id, outcome_navi.id
        )
        
        db.refresh(user1)
        db.refresh(user2)
        
        # User1 wins: gets 100% of total pool (1000$)
        # Profit = 1000 - 500 = 500$
        # Fee = 500 * 0.02 = 10$
        # Final payout = 1000 - 10 = 990$
        # Total balance = 500 (initial remaining) + 990 (payout) = 1490$
        assert user1.balance_available == Decimal("1490.00")
        assert user1.balance_locked == Decimal("0.00")
        
        # User2 loses their stake  
        # 500 (initial remaining after bet)
        assert user2.balance_available == Decimal("500.00")
        assert user2.balance_locked == Decimal("0.00")
        
        # Check settlement result
        assert result["winners_count"] == 1
        assert result["losers_count"] == 1
        assert result["total_market_pool"] == "1000.00"
        assert result["winning_pool_total"] == "500.00"
    
    def test_multiple_winners_share_pool(self, db, pool_market, users):
        """Test multiple winners sharing the liquidity pool proportionally"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        user1 = users["user1"]
        user2 = users["user2"]
        user3 = users["user3"]
        
        # Test case from spec:
        # Pool NaVi: 700$ (User1: 500$, User3: 200$)
        # Pool G2: 300$ (User2: 300$)
        # Total: 1000$
        
        # User1 bets on NaVi
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("500.00")
        )
        
        # User3 adds to NaVi pool
        PoolMarketService.place_pool_bet(
            db, user3, market.id, outcome_navi.id, Decimal("200.00")
        )
        
        # User2 bets on G2
        PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_g2.id, Decimal("300.00")
        )
        
        # Settle market (NaVi wins)
        market.status = MarketStatus.SETTLED
        market.winning_outcome_id = outcome_navi.id
        db.commit()
        
        # Settle pool
        result = PoolMarketService.settle_pool_market(
            db, market.id, outcome_navi.id
        )
        
        db.refresh(user1)
        db.refresh(user3)
        db.refresh(user2)
        
        # User1: share = 500/700 = 71.43%
        #        payout before fee = 71.43% × 1000 = 714.28...
        #        profit = 214.28, fee = 4.28
        #        final payout ≈ 710
        #        total balance = 500 (remaining) + 710 (payout) ≈ 1210
        assert user1.balance_available >= Decimal("1209.00") and user1.balance_available <= Decimal("1211.00")
        
        # User3: share = 200/700 = 28.57%
        #        payout before fee = 28.57% × 1000 = 285.71...
        #        profit = 85.71, fee = 1.71
        #        final payout ≈ 284
        #        total balance = 300 (remaining) + 284 (payout) ≈ 584
        assert user3.balance_available >= Decimal("583.00") and user3.balance_available <= Decimal("585.00")
        
        # User2 loses
        assert user2.balance_available == Decimal("700.00")
        
        # Check settlement result
        assert result["winners_count"] == 2
        assert result["losers_count"] == 1
    
    def test_dominant_pool_wins(self, db, pool_market, users):
        """Test when dominant pool wins (small profit scenario)"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        outcome_g2 = pool_market["outcome_g2"]
        user1 = users["user1"]
        user2 = users["user2"]
        
        # Test case from spec:
        # Pool NaVi: 900$ (User1)
        # Pool G2: 100$ (User2)
        # Total: 1000$
        
        # User1 bets big on NaVi
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("900.00")
        )
        
        # User2 bets small on G2
        PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_g2.id, Decimal("100.00")
        )
        
        # Settle market (NaVi wins)
        market.status = MarketStatus.SETTLED
        market.winning_outcome_id = outcome_navi.id
        db.commit()
        
        # Settle pool
        result = PoolMarketService.settle_pool_market(
            db, market.id, outcome_navi.id
        )
        
        db.refresh(user1)
        db.refresh(user2)
        
        # User1: share = 100% of NaVi pool
        #        payout before fee = 100% × 1000 = 1000$
        #        profit = 100$, fee = 2$
        #        final payout = 998$
        #        total balance = 100 (remaining) + 998 (payout) = 1098$
        assert user1.balance_available == Decimal("1098.00")
        assert user1.balance_locked == Decimal("0.00")
        
        # User2 loses
        assert user2.balance_available == Decimal("900.00")  # Lost 100
        
        assert result["winners_count"] == 1
        assert result["losers_count"] == 1
    
    def test_transactions_created(self, db, pool_market, users):
        """Test that all transactions are recorded"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        user1 = users["user1"]
        
        # Place bet
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("100.00")
        )
        
        # Check ORDER_LOCK transaction created
        txs = db.query(Transaction).filter(
            Transaction.user_id == user1.id,
            Transaction.type == TransactionType.ORDER_LOCK
        ).all()
        
        assert len(txs) == 1
        assert txs[0].amount == Decimal("100.00")
    
    def test_cannot_bet_insufficient_funds(self, db, pool_market, users):
        """Test cannot bet more than available balance"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        user1 = users["user1"]
        
        # Try to bet more than balance
        with pytest.raises(InsufficientFundsError):
            PoolMarketService.place_pool_bet(
                db, user1, market.id, outcome_navi.id, Decimal("10000.00")
            )
    
    def test_pool_state_updates_correctly(self, db, pool_market, users):
        """Test pool state updates after each bet"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        user1 = users["user1"]
        user2 = users["user2"]
        
        # First bet
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("100.00")
        )
        
        state1 = PoolMarketService.get_pool_state(db, market.id)
        assert state1["total_pool"] == "100.00"
        
        navi_outcome1 = next(o for o in state1["outcomes"] if o["name"] == "NaVi")
        assert navi_outcome1["total_staked"] == "100.00"
        assert navi_outcome1["participant_count"] == 1
        
        # Second bet (same user, same outcome)
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("50.00")
        )
        
        state2 = PoolMarketService.get_pool_state(db, market.id)
        navi_outcome2 = next(o for o in state2["outcomes"] if o["name"] == "NaVi")
        assert navi_outcome2["total_staked"] == "150.00"
        assert navi_outcome2["participant_count"] == 1  # Same user
        
        # Third bet (different user)
        PoolMarketService.place_pool_bet(
            db, user2, market.id, outcome_navi.id, Decimal("25.00")
        )
        
        state3 = PoolMarketService.get_pool_state(db, market.id)
        navi_outcome3 = next(o for o in state3["outcomes"] if o["name"] == "NaVi")
        assert navi_outcome3["total_staked"] == "175.00"
        assert navi_outcome3["participant_count"] == 2  # Different user
    
    def test_get_user_bets_filtering(self, db, pool_market, users):
        """Test filtering user's bets"""
        market = pool_market["market"]
        outcome_navi = pool_market["outcome_navi"]
        user1 = users["user1"]
        
        # Place bets
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("100.00")
        )
        PoolMarketService.place_pool_bet(
            db, user1, market.id, outcome_navi.id, Decimal("50.00")
        )
        
        # Get unsettled bets
        unsettled = PoolMarketService.get_user_pool_bets(
            db, user1.id, market.id, settled=False
        )
        assert len(unsettled) == 2
        
        # Get settled bets (should be empty)
        settled = PoolMarketService.get_user_pool_bets(
            db, user1.id, market.id, settled=True
        )
        assert len(settled) == 0