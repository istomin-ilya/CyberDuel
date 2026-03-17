"""
Integration tests for Unified Settlement Service.
Tests settlement for both P2P_DIRECT and POOL_MARKET modes.
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
from app.models.contract import Contract, ContractStatus
from app.models.order import Order, OrderStatus
from app.models.pool_bet import PoolBet
from app.models.pool_state import PoolState
from app.services.unified_settlement import UnifiedSettlementService
from app.services.settlement import SettlementService
from app.services.pool_market import PoolMarketService


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
    admin = User(
        email="admin@test.com",
        password_hash="hashed",
        balance_available=Decimal("10000.00"),
        balance_locked=Decimal("0.00"),
        is_admin=True
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return admin


@pytest.fixture
def regular_users(db):
    """Create 3 regular users"""
    users = []
    for i in range(3):
        user = User(
            email=f"user{i}@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00"),
            is_admin=False
        )
        db.add(user)
        users.append(user)
    
    db.commit()
    for user in users:
        db.refresh(user)
    
    return users


@pytest.fixture
def event(db, admin_user):
    """Create finished event"""
    event = Event(
        game_type="CS2",
        team_a="NaVi",
        team_b="G2",
        status=EventStatus.FINISHED,
        external_match_id="match_123"
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@pytest.fixture
def p2p_market(db, event):
    """Create P2P market with outcomes and winning outcome set"""
    market = Market(
        event_id=event.id,
        market_type="match_winner",
        market_mode=MarketMode.P2P_DIRECT,
        title="Match Winner (P2P)",
        status=MarketStatus.SETTLED
    )
    db.add(market)
    db.flush()
    
    outcome_a = Outcome(market_id=market.id, name="NaVi")
    outcome_b = Outcome(market_id=market.id, name="G2")
    db.add_all([outcome_a, outcome_b])
    db.flush()
    
    # Set winning outcome
    market.winning_outcome_id = outcome_a.id
    db.commit()
    db.refresh(market)
    db.refresh(outcome_a)
    db.refresh(outcome_b)
    
    return market, outcome_a, outcome_b


@pytest.fixture
def pool_market(db, event):
    """Create Pool market with outcomes, pool states and winning outcome set"""
    market = Market(
        event_id=event.id,
        market_type="match_winner",
        market_mode=MarketMode.POOL_MARKET,
        title="Match Winner (Pool)",
        status=MarketStatus.SETTLED
    )
    db.add(market)
    db.flush()
    
    outcome_a = Outcome(market_id=market.id, name="NaVi")
    outcome_b = Outcome(market_id=market.id, name="G2")
    db.add_all([outcome_a, outcome_b])
    db.flush()
    
    # Initialize pool states
    PoolMarketService.initialize_pool_states(db, market)
    
    # Set winning outcome
    market.winning_outcome_id = outcome_a.id
    db.commit()
    db.refresh(market)
    db.refresh(outcome_a)
    db.refresh(outcome_b)
    
    return market, outcome_a, outcome_b


def test_settle_p2p_market(db, p2p_market, regular_users):
    """Test settling P2P market with multiple contracts"""
    market, outcome_a, outcome_b = p2p_market
    users = regular_users
    
    # Create 2 orders first (required for contracts)
    order1 = Order(
        market_id=market.id,
        outcome_id=outcome_a.id,
        user_id=users[0].id,
        amount=Decimal("100.00"),
        unfilled_amount=Decimal("0.00"),
        odds=Decimal("1.5"),
        status=OrderStatus.FILLED
    )
    order2 = Order(
        market_id=market.id,
        outcome_id=outcome_a.id,
        user_id=users[1].id,
        amount=Decimal("50.00"),
        unfilled_amount=Decimal("0.00"),
        odds=Decimal("2.0"),
        status=OrderStatus.FILLED
    )
    db.add_all([order1, order2])
    db.flush()
    
    # Create 2 contracts
    contract1 = Contract(
        market_id=market.id,
        order_id=order1.id,
        outcome_id=outcome_a.id,
        maker_id=users[0].id,
        taker_id=users[1].id,
        amount=Decimal("100.00"),
        odds=Decimal("1.5"),
        status=ContractStatus.ACTIVE
    )
    contract2 = Contract(
        market_id=market.id,
        order_id=order2.id,
        outcome_id=outcome_a.id,
        maker_id=users[1].id,
        taker_id=users[2].id,
        amount=Decimal("50.00"),
        odds=Decimal("2.0"),
        status=ContractStatus.ACTIVE
    )
    
    # Lock funds for contracts
    users[0].balance_available -= Decimal("100.00")
    users[0].balance_locked += Decimal("100.00")
    
    users[1].balance_available -= Decimal("100.00")  # 50 for maker + 50 taker risk
    users[1].balance_locked += Decimal("100.00")
    
    users[2].balance_available -= Decimal("50.00")
    users[2].balance_locked += Decimal("50.00")
    
    db.add_all([contract1, contract2])
    db.commit()
    
    # Settle market
    result = UnifiedSettlementService.settle_market(market.id, db)
    
    # Verify result
    assert result["mode"] == "p2p_direct"
    assert result["market_id"] == market.id
    assert result["total_contracts"] == 2
    assert result["settled"] == 2
    assert result["errors"] == 0
    
    # Verify contracts are settled
    db.refresh(contract1)
    db.refresh(contract2)
    assert contract1.status == ContractStatus.SETTLED
    assert contract2.status == ContractStatus.SETTLED


def test_settle_pool_market(db, pool_market, regular_users):
    """Test settling Pool market with multiple bets"""
    market, outcome_a, outcome_b = pool_market
    users = regular_users
    
    # Change market status to OPEN to allow betting
    market.status = MarketStatus.OPEN
    db.commit()
    
    # Create 3 pool bets
    # User 0: 200 on outcome_a (winner)
    PoolMarketService.place_pool_bet(
        db=db,
        user=users[0],
        market_id=market.id,
        outcome_id=outcome_a.id,
        amount=Decimal("200.00")
    )
    
    # User 1: 300 on outcome_a (winner)
    PoolMarketService.place_pool_bet(
        db=db,
        user=users[1],
        market_id=market.id,
        outcome_id=outcome_a.id,
        amount=Decimal("300.00")
    )
    
    # User 2: 500 on outcome_b (loser)
    PoolMarketService.place_pool_bet(
        db=db,
        user=users[2],
        market_id=market.id,
        outcome_id=outcome_b.id,
        amount=Decimal("500.00")
    )
    
    # Set market back to SETTLED for settlement
    market.status = MarketStatus.SETTLED
    db.commit()
    
    # Settle market
    result = UnifiedSettlementService.settle_market(market.id, db)
    
    # Verify result
    assert result["mode"] == "pool_market"
    assert result["market_id"] == market.id
    assert Decimal(result["total_market_pool"]) == Decimal("1000.00")
    assert Decimal(result["winning_pool_total"]) == Decimal("500.00")
    assert result["winners_count"] == 2
    assert result["losers_count"] == 1
    
    # Verify all bets are settled
    bets = db.query(PoolBet).filter(PoolBet.market_id == market.id).all()
    assert len(bets) == 3
    for bet in bets:
        assert bet.settled is True


def test_settle_market_not_found(db):
    """Test settlement of non-existent market"""
    with pytest.raises(ValueError, match="Market not found"):
        UnifiedSettlementService.settle_market(99999, db)


def test_settle_market_not_settled_status(db, event):
    """Test settlement of market not in SETTLED status"""
    market = Market(
        event_id=event.id,
        market_type="match_winner",
        market_mode=MarketMode.P2P_DIRECT,
        title="Test Market",
        status=MarketStatus.OPEN  # Not SETTLED
    )
    db.add(market)
    db.commit()
    
    with pytest.raises(ValueError, match="Market must be in SETTLED status"):
        UnifiedSettlementService.settle_market(market.id, db)


def test_settle_market_no_winning_outcome(db, event):
    """Test settlement of market without winning outcome set"""
    market = Market(
        event_id=event.id,
        market_type="match_winner",
        market_mode=MarketMode.P2P_DIRECT,
        title="Test Market",
        status=MarketStatus.SETTLED,
        winning_outcome_id=None  # No winning outcome
    )
    db.add(market)
    db.commit()
    
    with pytest.raises(ValueError, match="Market must have winning_outcome_id set"):
        UnifiedSettlementService.settle_market(market.id, db)


def test_p2p_settlement_wrapper_no_contracts(db, p2p_market):
    """Test P2P settlement when there are no contracts"""
    market, outcome_a, outcome_b = p2p_market
    
    # Don't create any contracts
    result = SettlementService.settle_market(market.id, db)
    
    # Verify result
    assert result["market_id"] == market.id
    assert result["total_contracts"] == 0
    assert result["settled"] == 0
    assert "No contracts to settle" in result.get("message", "")


def test_p2p_settlement_wrapper_already_settled(db, p2p_market, regular_users):
    """Test P2P settlement with mix of SETTLED and ACTIVE contracts"""
    market, outcome_a, outcome_b = p2p_market
    users = regular_users
    
    # Create orders first
    order1 = Order(
        market_id=market.id,
        outcome_id=outcome_a.id,
        user_id=users[0].id,
        amount=Decimal("100.00"),
        unfilled_amount=Decimal("0.00"),
        odds=Decimal("1.5"),
        status=OrderStatus.FILLED
    )
    order2 = Order(
        market_id=market.id,
        outcome_id=outcome_a.id,
        user_id=users[1].id,
        amount=Decimal("50.00"),
        unfilled_amount=Decimal("0.00"),
        odds=Decimal("2.0"),
        status=OrderStatus.FILLED
    )
    db.add_all([order1, order2])
    db.flush()
    
    # Create 1 already settled contract
    contract1 = Contract(
        market_id=market.id,
        order_id=order1.id,
        outcome_id=outcome_a.id,
        maker_id=users[0].id,
        taker_id=users[1].id,
        amount=Decimal("100.00"),
        odds=Decimal("1.5"),
        status=ContractStatus.SETTLED,
        winner_id=users[0].id
    )
    
    # Create 1 active contract
    contract2 = Contract(
        market_id=market.id,
        order_id=order2.id,
        outcome_id=outcome_a.id,
        maker_id=users[1].id,
        taker_id=users[2].id,
        amount=Decimal("50.00"),
        odds=Decimal("2.0"),
        status=ContractStatus.ACTIVE
    )
    
    # Lock funds for active contract
    users[1].balance_available -= Decimal("50.00")
    users[1].balance_locked += Decimal("50.00")
    users[2].balance_available -= Decimal("50.00")
    users[2].balance_locked += Decimal("50.00")
    
    db.add_all([contract1, contract2])
    db.commit()
    
    # Settle market
    result = SettlementService.settle_market(market.id, db)
    
    # Verify result
    # Note: settle_market only processes ACTIVE/CLAIMED contracts, not already SETTLED ones
    assert result["market_id"] == market.id
    assert result["total_contracts"] == 1  # Only finds ACTIVE contracts
    assert result["settled"] == 1  # Only ACTIVE was settled
    assert result["already_settled"] == 0  # SETTLED contracts are not included in query


def test_market_mode_in_response(db, p2p_market, pool_market, regular_users):
    """Test that settlement response includes correct market mode"""
    p2p_mkt, p2p_outcome_a, p2p_outcome_b = p2p_market
    pool_mkt, pool_outcome_a, pool_outcome_b = pool_market
    users = regular_users
    
    # Create order for P2P market
    order = Order(
        market_id=p2p_mkt.id,
        outcome_id=p2p_outcome_a.id,
        user_id=users[0].id,
        amount=Decimal("100.00"),
        unfilled_amount=Decimal("0.00"),
        odds=Decimal("1.5"),
        status=OrderStatus.FILLED
    )
    db.add(order)
    db.flush()
    
    # Create contract for P2P market
    contract = Contract(
        market_id=p2p_mkt.id,
        order_id=order.id,
        outcome_id=p2p_outcome_a.id,
        maker_id=users[0].id,
        taker_id=users[1].id,
        amount=Decimal("100.00"),
        odds=Decimal("1.5"),
        status=ContractStatus.ACTIVE
    )
    users[0].balance_available -= Decimal("100.00")
    users[0].balance_locked += Decimal("100.00")
    users[1].balance_available -= Decimal("50.00")
    users[1].balance_locked += Decimal("50.00")
    db.add(contract)
    db.commit()
    
    # Settle P2P market
    p2p_result = UnifiedSettlementService.settle_market(p2p_mkt.id, db)
    assert p2p_result["mode"] == "p2p_direct"
    
    # Create bet for Pool market
    pool_mkt.status = MarketStatus.OPEN
    db.commit()
    PoolMarketService.place_pool_bet(
        db=db,
        user=users[2],
        market_id=pool_mkt.id,
        outcome_id=pool_outcome_a.id,
        amount=Decimal("100.00")
    )
    pool_mkt.status = MarketStatus.SETTLED
    db.commit()
    
    # Settle Pool market
    pool_result = UnifiedSettlementService.settle_market(pool_mkt.id, db)
    assert pool_result["mode"] == "pool_market"
