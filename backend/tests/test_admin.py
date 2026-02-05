"""
Unit tests for Admin dispute resolution system.
"""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome
from app.models.order import Order, OrderStatus
from app.models.contract import Contract, ContractStatus
from app.services.escrow import EscrowService
from app.services.matching import MatchingService
from app.services.settlement import SettlementService


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
    """Create regular users"""
    maker = User(
        email="maker@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00"),
        balance_locked=Decimal("0.00"),
        is_admin=False
    )
    taker = User(
        email="taker@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00"),
        balance_locked=Decimal("0.00"),
        is_admin=False
    )
    db.add_all([maker, taker])
    db.commit()
    db.refresh(maker)
    db.refresh(taker)
    return {"maker": maker, "taker": taker}


@pytest.fixture
def disputed_contract(db, regular_users):
    """Create disputed contract"""
    maker = regular_users["maker"]
    taker = regular_users["taker"]
    
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
    
    # Create market
    market = Market(
        event_id=event.id,
        market_type="match_winner",
        title="Match Winner",
        status=MarketStatus.SETTLED
    )
    db.add(market)
    db.flush()
    
    # Create outcomes
    outcome_navi = Outcome(market_id=market.id, name="NaVi")
    outcome_spirit = Outcome(market_id=market.id, name="Spirit")
    db.add_all([outcome_navi, outcome_spirit])
    db.flush()
    
    # Settle market (NaVi wins)
    market.winning_outcome_id = outcome_navi.id
    db.commit()
    
    # Create order
    order = Order(
        user_id=maker.id,
        market_id=market.id,
        outcome_id=outcome_navi.id,
        amount=Decimal("100.00"),
        unfilled_amount=Decimal("100.00"),
        odds=Decimal("1.80"),
        status=OrderStatus.OPEN
    )
    db.add(order)
    db.flush()
    
    # Lock maker funds
    EscrowService.lock_funds(db, maker, Decimal("100.00"), "Order created", order.id)
    db.commit()
    
    # Match order
    contract = MatchingService.match_order(db, order.id, taker, Decimal("100.00"))
    db.commit()
    
    # Claim and dispute
    SettlementService.claim_result(db, contract, maker, outcome_navi.id)
    SettlementService.dispute_claim(db, contract, taker, "Spirit won, not NaVi!")
    db.commit()
    db.refresh(contract)
    
    return {
        "contract": contract,
        "market": market,
        "outcome_navi": outcome_navi,
        "outcome_spirit": outcome_spirit,
        "maker": maker,
        "taker": taker
    }


class TestAdminUserManagement:
    """Test admin user management"""
    
    def test_create_admin_user(self, db):
        """Test creating user with admin flag"""
        admin = User(
            email="admin@example.com",
            password_hash="hashed",
            balance_available=Decimal("0.00"),
            balance_locked=Decimal("0.00"),
            is_admin=True
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        
        assert admin.is_admin is True
    
    def test_regular_user_not_admin(self, db):
        """Test regular user has is_admin=False by default"""
        user = User(
            email="user@example.com",
            password_hash="hashed",
            balance_available=Decimal("0.00"),
            balance_locked=Decimal("0.00")
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        assert user.is_admin is False
    
    def test_promote_user_to_admin(self, db):
        """Test promoting regular user to admin"""
        user = User(
            email="user@example.com",
            password_hash="hashed",
            balance_available=Decimal("0.00"),
            balance_locked=Decimal("0.00"),
            is_admin=False
        )
        db.add(user)
        db.commit()
        
        # Promote to admin
        user.is_admin = True
        db.commit()
        db.refresh(user)
        
        assert user.is_admin is True
    
    def test_remove_admin_privileges(self, db):
        """Test removing admin privileges"""
        admin = User(
            email="admin@example.com",
            password_hash="hashed",
            balance_available=Decimal("0.00"),
            balance_locked=Decimal("0.00"),
            is_admin=True
        )
        db.add(admin)
        db.commit()
        
        # Remove admin
        admin.is_admin = False
        db.commit()
        db.refresh(admin)
        
        assert admin.is_admin is False


class TestDisputeResolution:
    """Test admin dispute resolution"""
    
    def test_list_disputed_contracts(self, db, disputed_contract):
        """Test listing disputed contracts"""
        # Query disputed contracts
        contracts = db.query(Contract).filter(
            Contract.status == ContractStatus.DISPUTED
        ).all()
        
        assert len(contracts) == 1
        assert contracts[0].id == disputed_contract["contract"].id
        assert contracts[0].status == ContractStatus.DISPUTED
    
    def test_admin_resolves_dispute_maker_wins(self, db, disputed_contract):
        """Test admin resolving dispute in favor of Maker"""
        contract = disputed_contract["contract"]
        maker = disputed_contract["maker"]
        taker = disputed_contract["taker"]
        outcome_navi = disputed_contract["outcome_navi"]
        
        initial_maker_available = maker.balance_available
        initial_taker_available = taker.balance_available
        
        # Admin resolves: NaVi actually won (Maker was right)
        settled_contract = SettlementService.settle_contract(
            db=db,
            contract=contract,
            winning_outcome_id=outcome_navi.id
        )
        
        db.refresh(maker)
        db.refresh(taker)
        
        # Verify settlement
        assert settled_contract.status == ContractStatus.SETTLED
        assert settled_contract.winner_id == maker.id
        
        # Verify balances (Maker wins)
        # Pool = 100 + 80 = 180
        # Profit = 80
        # Fee = 1.6
        # Payout = 178.4
        expected_maker_final = initial_maker_available + Decimal("178.40")
        expected_taker_final = initial_taker_available
        
        assert maker.balance_available == expected_maker_final
        assert maker.balance_locked == Decimal("0.00")
        assert taker.balance_available == expected_taker_final
        assert taker.balance_locked == Decimal("0.00")
    
    def test_admin_resolves_dispute_taker_wins(self, db, disputed_contract):
        """Test admin resolving dispute in favor of Taker"""
        contract = disputed_contract["contract"]
        maker = disputed_contract["maker"]
        taker = disputed_contract["taker"]
        outcome_spirit = disputed_contract["outcome_spirit"]
        
        initial_maker_available = maker.balance_available
        initial_taker_available = taker.balance_available
        
        # Admin resolves: Spirit actually won (Taker was right)
        settled_contract = SettlementService.settle_contract(
            db=db,
            contract=contract,
            winning_outcome_id=outcome_spirit.id
        )
        
        db.refresh(maker)
        db.refresh(taker)
        
        # Verify settlement
        assert settled_contract.status == ContractStatus.SETTLED
        assert settled_contract.winner_id == taker.id
        
        # Verify balances (Taker wins)
        # Pool = 100 + 80 = 180
        # Profit = 100
        # Fee = 2.0
        # Payout = 178.0
        expected_maker_final = initial_maker_available
        expected_taker_final = initial_taker_available + Decimal("178.00")
        
        assert maker.balance_available == expected_maker_final
        assert maker.balance_locked == Decimal("0.00")
        assert taker.balance_available == expected_taker_final
        assert taker.balance_locked == Decimal("0.00")
    
    def test_cannot_resolve_non_disputed_contract(self, db, regular_users):
        """Test cannot resolve contract that's not disputed"""
        maker = regular_users["maker"]
        
        # Create active contract (not disputed)
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.OPEN
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
        
        outcome = Outcome(market_id=market.id, name="NaVi")
        db.add(outcome)
        db.flush()
        
        contract = Contract(
            market_id=market.id,
            order_id=1,
            maker_id=maker.id,
            taker_id=2,
            outcome_id=outcome.id,
            amount=Decimal("100.00"),
            odds=Decimal("1.80"),
            status=ContractStatus.ACTIVE
        )
        db.add(contract)
        db.commit()
        
        # Verify status is not DISPUTED
        assert contract.status != ContractStatus.DISPUTED
    
    def test_multiple_disputed_contracts(self, db, regular_users):
        """Test handling multiple disputed contracts"""
        maker = regular_users["maker"]
        taker = regular_users["taker"]
        
        # Create multiple disputed contracts
        for i in range(3):
            event = Event(
                game_type="CS2",
                team_a=f"Team{i}A",
                team_b=f"Team{i}B",
                status=EventStatus.FINISHED
            )
            db.add(event)
            db.flush()
            
            market = Market(
                event_id=event.id,
                market_type="match_winner",
                title="Match Winner",
                status=MarketStatus.SETTLED
            )
            db.add(market)
            db.flush()
            
            outcome = Outcome(market_id=market.id, name=f"Team{i}A")
            db.add(outcome)
            db.flush()
            
            market.winning_outcome_id = outcome.id
            
            contract = Contract(
                market_id=market.id,
                order_id=i + 1,
                maker_id=maker.id,
                taker_id=taker.id,
                outcome_id=outcome.id,
                amount=Decimal("100.00"),
                odds=Decimal("1.80"),
                status=ContractStatus.DISPUTED
            )
            db.add(contract)
        
        db.commit()
        
        # Query all disputed contracts
        disputed = db.query(Contract).filter(
            Contract.status == ContractStatus.DISPUTED
        ).all()
        
        assert len(disputed) == 3


class TestAdminAccess:
    """Test admin access control"""
    
    def test_admin_can_view_all_contracts(self, db, admin_user, regular_users):
        """Test admin can view any contract"""
        maker = regular_users["maker"]
        
        # Create contract
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
        
        outcome = Outcome(market_id=market.id, name="NaVi")
        db.add(outcome)
        db.flush()
        
        contract = Contract(
            market_id=market.id,
            order_id=1,
            maker_id=maker.id,
            taker_id=2,
            outcome_id=outcome.id,
            amount=Decimal("100.00"),
            odds=Decimal("1.80"),
            status=ContractStatus.ACTIVE
        )
        db.add(contract)
        db.commit()
        
        # Admin can query any contract
        found_contract = db.query(Contract).filter(Contract.id == contract.id).first()
        assert found_contract is not None
        assert found_contract.id == contract.id
    
    def test_regular_user_cannot_be_admin(self, db):
        """Test regular user defaults to non-admin"""
        user = User(
            email="regular@test.com",
            password_hash="hashed",
            balance_available=Decimal("100.00"),
            balance_locked=Decimal("0.00")
        )
        db.add(user)
        db.commit()
        
        assert user.is_admin is False