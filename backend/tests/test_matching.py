"""
Unit tests for matching engine.
"""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import Base from models to ensure all models are registered
from app.models import Base
from app.models.user import User
from app.models.event import Event
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome
from app.models.order import Order, OrderStatus
from app.models.contract import Contract, ContractStatus
from app.models.transaction import Transaction
from app.services.matching import MatchingService, OrderNotAvailableError, MatchingError
from app.services.escrow import InsufficientFundsError


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True to see SQL queries
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db():
    """Create test database session"""
    # Create all tables
    Base.metadata.create_all(bind=engine)
    
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def maker_user(db):
    """Create maker user with balance"""
    user = User(
        email="maker@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00"),
        balance_locked=Decimal("0.00")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def taker_user(db):
    """Create taker user with balance"""
    user = User(
        email="taker@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00"),
        balance_locked=Decimal("0.00")
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def market(db):
    """Create test event and market"""
    event = Event(
        game_type="CS2",
        team_a="NaVi",
        team_b="Spirit",
        status="OPEN"
    )
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
    
    outcome = Outcome(
        market_id=market.id,
        name="NaVi"
    )
    db.add(outcome)
    db.commit()
    db.refresh(market)
    db.refresh(outcome)
    
    return market, outcome


@pytest.fixture
def open_order(db, maker_user, market):
    """Create open order from maker"""
    market_obj, outcome = market
    
    order = Order(
        user_id=maker_user.id,
        market_id=market_obj.id,
        outcome_id=outcome.id,
        amount=Decimal("100.00"),
        unfilled_amount=Decimal("100.00"),
        odds=Decimal("1.80"),
        status=OrderStatus.OPEN
    )
    db.add(order)
    
    # Lock maker funds
    maker_user.balance_available -= Decimal("100.00")
    maker_user.balance_locked += Decimal("100.00")
    
    db.commit()
    db.refresh(order)
    return order


class TestCalculateTakerRisk:
    """Test taker risk calculation"""
    
    def test_calculate_risk_basic(self):
        """Test basic risk calculation"""
        maker_amount = Decimal("100.00")
        odds = Decimal("1.80")
        
        risk = MatchingService.calculate_taker_risk(maker_amount, odds)
        
        assert risk == Decimal("80.00")  # 100 * (1.8 - 1) = 80
    
    def test_calculate_risk_different_odds(self):
        """Test risk calculation with different odds"""
        maker_amount = Decimal("50.00")
        odds = Decimal("2.50")
        
        risk = MatchingService.calculate_taker_risk(maker_amount, odds)
        
        assert risk == Decimal("75.00")  # 50 * (2.5 - 1) = 75
    
    def test_calculate_risk_low_odds(self):
        """Test risk calculation with low odds"""
        maker_amount = Decimal("100.00")
        odds = Decimal("1.10")
        
        risk = MatchingService.calculate_taker_risk(maker_amount, odds)
        
        assert risk == Decimal("10.00")  # 100 * (1.1 - 1) = 10


class TestMatchOrder:
    """Test order matching"""
    
    def test_full_match(self, db, open_order, taker_user, market):
        """Test full order match (taker takes entire order)"""
        initial_taker_available = taker_user.balance_available
        initial_maker_locked = db.query(User).filter(User.id == open_order.user_id).first().balance_locked
        
        # Taker takes full order
        contract = MatchingService.match_order(
            db=db,
            order_id=open_order.id,
            taker=taker_user,
            amount=Decimal("100.00")
        )
        
        db.commit()
        db.refresh(open_order)
        db.refresh(taker_user)
        
        # Verify contract created
        assert contract is not None
        assert contract.maker_id == open_order.user_id
        assert contract.taker_id == taker_user.id
        assert contract.amount == Decimal("100.00")
        assert contract.odds == Decimal("1.80")
        assert contract.status == ContractStatus.ACTIVE
        
        # Verify order filled
        assert open_order.unfilled_amount == Decimal("0.00")
        assert open_order.status == OrderStatus.FILLED
        
        # Verify taker funds locked (risk = 100 * 0.8 = 80)
        assert taker_user.balance_available == initial_taker_available - Decimal("80.00")
        assert taker_user.balance_locked == Decimal("80.00")
    
    def test_partial_match(self, db, open_order, taker_user, market):
        """Test partial order match (taker takes part of order)"""
        initial_taker_available = taker_user.balance_available
        
        # Taker takes 50 out of 100
        contract = MatchingService.match_order(
            db=db,
            order_id=open_order.id,
            taker=taker_user,
            amount=Decimal("50.00")
        )
        
        db.commit()
        db.refresh(open_order)
        db.refresh(taker_user)
        
        # Verify contract created for partial amount
        assert contract.amount == Decimal("50.00")
        assert contract.odds == Decimal("1.80")
        
        # Verify order partially filled
        assert open_order.unfilled_amount == Decimal("50.00")
        assert open_order.status == OrderStatus.PARTIALLY_FILLED
        
        # Verify taker funds locked (risk = 50 * 0.8 = 40)
        assert taker_user.balance_available == initial_taker_available - Decimal("40.00")
        assert taker_user.balance_locked == Decimal("40.00")
    
    def test_multiple_partial_matches(self, db, open_order, market):
        """Test multiple takers taking parts of same order"""
        # Create second taker
        taker1 = User(
            email="taker1@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        db.add(taker1)
        
        taker2 = User(
            email="taker2@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        db.add(taker2)
        db.commit()
        
        # Taker1 takes 30
        contract1 = MatchingService.match_order(
            db=db,
            order_id=open_order.id,
            taker=taker1,
            amount=Decimal("30.00")
        )
        db.commit()
        db.refresh(open_order)
        
        assert open_order.unfilled_amount == Decimal("70.00")
        assert open_order.status == OrderStatus.PARTIALLY_FILLED
        
        # Taker2 takes 70 (rest)
        contract2 = MatchingService.match_order(
            db=db,
            order_id=open_order.id,
            taker=taker2,
            amount=Decimal("70.00")
        )
        db.commit()
        db.refresh(open_order)
        
        assert open_order.unfilled_amount == Decimal("0.00")
        assert open_order.status == OrderStatus.FILLED
        
        # Verify both contracts exist
        assert contract1.amount == Decimal("30.00")
        assert contract2.amount == Decimal("70.00")
    
    def test_insufficient_funds(self, db, open_order, taker_user, market):
        """Test matching fails when taker has insufficient funds"""
        # Reduce taker balance
        taker_user.balance_available = Decimal("10.00")
        db.commit()
        
        # Try to take 100 (needs 80 risk, only has 10)
        with pytest.raises(InsufficientFundsError):
            MatchingService.match_order(
                db=db,
                order_id=open_order.id,
                taker=taker_user,
                amount=Decimal("100.00")
            )
    
    def test_match_own_order(self, db, open_order, maker_user, market):
        """Test user cannot match their own order"""
        with pytest.raises(MatchingError, match="Cannot match your own order"):
            MatchingService.match_order(
                db=db,
                order_id=open_order.id,
                taker=maker_user,  # Same as order creator
                amount=Decimal("50.00")
            )
    
    def test_match_cancelled_order(self, db, open_order, taker_user, market):
        """Test cannot match cancelled order"""
        # Cancel order
        open_order.status = OrderStatus.CANCELLED
        db.commit()
        
        with pytest.raises(OrderNotAvailableError):
            MatchingService.match_order(
                db=db,
                order_id=open_order.id,
                taker=taker_user,
                amount=Decimal("50.00")
            )
    
    def test_match_filled_order(self, db, open_order, taker_user, market):
        """Test cannot match already filled order"""
        # Fill order
        open_order.unfilled_amount = Decimal("0.00")
        open_order.status = OrderStatus.FILLED
        db.commit()
        
        with pytest.raises(OrderNotAvailableError):
            MatchingService.match_order(
                db=db,
                order_id=open_order.id,
                taker=taker_user,
                amount=Decimal("50.00")
            )
    
    def test_match_amount_exceeds_unfilled(self, db, open_order, taker_user, market):
        """Test cannot match more than unfilled amount"""
        with pytest.raises(MatchingError, match="exceeds unfilled amount"):
            MatchingService.match_order(
                db=db,
                order_id=open_order.id,
                taker=taker_user,
                amount=Decimal("150.00")  # Order only has 100 unfilled
            )
    
    def test_nonexistent_order(self, db, taker_user):
        """Test matching nonexistent order"""
        with pytest.raises(OrderNotAvailableError, match="not found"):
            MatchingService.match_order(
                db=db,
                order_id=99999,
                taker=taker_user,
                amount=Decimal("50.00")
            )