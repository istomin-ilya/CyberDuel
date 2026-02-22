"""
End-to-End integration tests for complete betting lifecycle.

Tests the entire flow from user registration to settlement and payout.
Simulates real user journey through the system.
"""
import pytest
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome
from app.models.order import Order, OrderStatus
from app.models.contract import Contract, ContractStatus
from app.models.transaction import Transaction, TransactionType
from app.services.auth import AuthService
from app.services.escrow import EscrowService
from app.services.matching import MatchingService
from app.services.settlement import SettlementService
from app.services.oracle import OracleService


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


class TestCompleteUserJourney:
    """Test complete user journey from registration to payout"""
    
    def test_full_lifecycle_maker_wins(self, db):
        """
        Complete lifecycle test: Maker wins
        
        Flow:
        1. Two users register
        2. Admin creates event and market
        3. Maker creates order (bets on NaVi @ 1.8 odds)
        4. Taker matches order
        5. Match finishes (NaVi wins)
        6. Oracle updates event status
        7. Maker claims result
        8. 15-minute timer expires (no dispute)
        9. Auto-settlement pays Maker
        10. Verify final balances and transaction history
        """
        
        # Step 1: User Registration
        maker = User(
            email="alice@example.com",
            password_hash=AuthService.hash_password("password123"),
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00"),
            is_admin=False
        )
        taker = User(
            email="bob@example.com",
            password_hash=AuthService.hash_password("password123"),
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00"),
            is_admin=False
        )
        admin = User(
            email="admin@example.com",
            password_hash=AuthService.hash_password("admin123"),
            balance_available=Decimal("10000.00"),
            balance_locked=Decimal("0.00"),
            is_admin=True
        )
        db.add_all([maker, taker, admin])
        db.commit()
        
        # Step 2: Admin creates event and market
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            tournament="IEM Katowice 2025",
            status=EventStatus.SCHEDULED,
            external_match_id="match_1",  # Mock provider
            scheduled_start=datetime.now(timezone.utc) + timedelta(hours=2)
        )
        db.add(event)
        db.flush()
        
        market = Market(
            event_id=event.id,
            market_type="match_winner",
            title="Match Winner",
            description="Who will win the match?",
            status=MarketStatus.PENDING
        )
        db.add(market)
        db.flush()
        
        outcome_navi = Outcome(market_id=market.id, name="NaVi")
        outcome_spirit = Outcome(market_id=market.id, name="Spirit")
        db.add_all([outcome_navi, outcome_spirit])
        db.commit()
        
        # Open market for betting
        event.status = EventStatus.OPEN
        market.status = MarketStatus.OPEN
        db.commit()
        
        # Step 3: Maker creates order (bets $200 on NaVi @ 1.8 odds)
        order = Order(
            user_id=maker.id,
            market_id=market.id,
            outcome_id=outcome_navi.id,
            amount=Decimal("200.00"),
            unfilled_amount=Decimal("200.00"),
            odds=Decimal("1.80"),
            status=OrderStatus.OPEN
        )
        db.add(order)
        db.flush()
        
        # Lock maker funds
        EscrowService.lock_funds(
            db=db,
            user=maker,
            amount=Decimal("200.00"),
            description=f"Order #{order.id} created",
            order_id=order.id
        )
        db.commit()
        db.refresh(maker)
        
        assert maker.balance_available == Decimal("800.00")
        assert maker.balance_locked == Decimal("200.00")
        
        # Step 4: Taker matches order (full match)
        contract = MatchingService.match_order(
            db=db,
            order_id=order.id,
            taker=taker,
            amount=Decimal("200.00")
        )
        db.commit()
        db.refresh(taker)
        db.refresh(order)
        
        # Taker risk = 200 * (1.8 - 1) = 160
        assert taker.balance_available == Decimal("840.00")
        assert taker.balance_locked == Decimal("160.00")
        assert order.status == OrderStatus.FILLED
        assert contract.status == ContractStatus.ACTIVE
        
        # Step 5: Match starts
        event.status = EventStatus.LIVE
        event.actual_start = datetime.now(timezone.utc)
        db.commit()
        
        # Step 6: Match finishes (NaVi wins - match_1 in mock)
        event.status = EventStatus.FINISHED
        event.actual_end = datetime.now(timezone.utc)
        db.commit()
        
        # Oracle fetches result
        oracle = OracleService(provider_name="mock")
        result = oracle.fetch_event_result(event)
        
        assert result.winner == "team_a"  # NaVi
        
        # Market settles
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        market.winning_outcome_id = winning_outcome.id
        market.status = MarketStatus.SETTLED
        db.commit()
        
        assert winning_outcome.id == outcome_navi.id
        
        # Step 7: Maker claims result
        claimed_contract = SettlementService.claim_result(
            db=db,
            contract=contract,
            claiming_user=maker,
            winning_outcome_id=outcome_navi.id
        )
        db.commit()
        
        assert claimed_contract.status == ContractStatus.CLAIMED
        assert claimed_contract.claim_initiated_by == maker.id
        
        # Step 8: Challenge period expires (simulate)
        contract.challenge_deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        
        # Step 9: Auto-settlement
        settled_contract = SettlementService.auto_settle_unchallenged(db, contract)
        db.commit()
        db.refresh(maker)
        db.refresh(taker)
        
        # Step 10: Verify final state
        assert settled_contract.status == ContractStatus.SETTLED
        assert settled_contract.winner_id == maker.id
        
        # Pool = 200 + 160 = 360
        # Profit = 160
        # Fee = 160 * 0.02 = 3.2
        # Payout = 200 + 160 - 3.2 = 356.8
        
        assert maker.balance_available == Decimal("1156.80")  # 800 + 356.8
        assert maker.balance_locked == Decimal("0.00")
        assert taker.balance_available == Decimal("840.00")  # Lost 160
        assert taker.balance_locked == Decimal("0.00")
        
        # Verify transaction history
        maker_txs = db.query(Transaction).filter(
            Transaction.user_id == maker.id
        ).order_by(Transaction.created_at).all()
        
        # Should have: ORDER_LOCK, SETTLEMENT, FEE
        assert len(maker_txs) >= 2
        
        settlement_tx = next((tx for tx in maker_txs if tx.type == TransactionType.SETTLEMENT), None)
        assert settlement_tx is not None
        assert settlement_tx.amount == Decimal("156.80")  # Net profit
    
    def test_full_lifecycle_taker_wins(self, db):
        """
        Complete lifecycle test: Taker wins
        
        Uses match_2 where team_b (Spirit) wins
        """
        
        # Setup users
        maker = User(
            email="alice@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        taker = User(
            email="bob@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        db.add_all([maker, taker])
        db.commit()
        
        # Setup event (using match_2 where team_b wins)
        event = Event(
            game_type="CS2",
            team_a="G2",
            team_b="FaZe",
            status=EventStatus.OPEN,
            external_match_id="match_2"
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
        
        outcome_g2 = Outcome(market_id=market.id, name="G2")
        outcome_faze = Outcome(market_id=market.id, name="FaZe")
        db.add_all([outcome_g2, outcome_faze])
        db.commit()
        
        # Maker bets on G2 (team_a) - will lose
        order = Order(
            user_id=maker.id,
            market_id=market.id,
            outcome_id=outcome_g2.id,
            amount=Decimal("100.00"),
            unfilled_amount=Decimal("100.00"),
            odds=Decimal("1.80"),
            status=OrderStatus.OPEN
        )
        db.add(order)
        db.flush()
        
        EscrowService.lock_funds(db, maker, Decimal("100.00"), "Order created", order.id)
        db.commit()
        
        # Taker matches (bets against G2, effectively on FaZe)
        contract = MatchingService.match_order(db, order.id, taker, Decimal("100.00"))
        db.commit()
        
        # Match finishes
        event.status = EventStatus.FINISHED
        db.commit()
        
        # Oracle: FaZe wins
        oracle = OracleService(provider_name="mock")
        result = oracle.fetch_event_result(event)
        assert result.winner == "team_b"
        
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        market.winning_outcome_id = winning_outcome.id
        market.status = MarketStatus.SETTLED
        db.commit()
        
        assert winning_outcome.id == outcome_faze.id
        
        # Taker claims win
        SettlementService.claim_result(db, contract, taker, outcome_faze.id)
        contract.challenge_deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        
        # Auto-settle
        settled_contract = SettlementService.auto_settle_unchallenged(db, contract)
        db.commit()
        db.refresh(maker)
        db.refresh(taker)
        
        # Verify: Taker wins
        assert settled_contract.winner_id == taker.id
        
        # Pool = 100 + 80 = 180
        # Profit = 100
        # Fee = 2
        # Payout = 80 + 100 - 2 = 178
        
        assert maker.balance_available == Decimal("900.00")  # Lost 100
        assert taker.balance_available == Decimal("1098.00")  # 920 + 178
    
    def test_full_lifecycle_with_dispute_admin_resolves(self, db):
        """
        Complete lifecycle with dispute resolution
        
        Flow:
        1. Users bet on match
        2. Maker claims incorrect result
        3. Taker disputes
        4. Admin resolves dispute
        5. Correct winner gets paid
        """
        
        # Setup
        maker = User(
            email="alice@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        taker = User(
            email="bob@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        admin = User(
            email="admin@example.com",
            password_hash="hashed",
            balance_available=Decimal("10000.00"),
            balance_locked=Decimal("0.00"),
            is_admin=True
        )
        db.add_all([maker, taker, admin])
        db.commit()
        
        # Create event and market
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.FINISHED,
            external_match_id="match_1"
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
        
        outcome_navi = Outcome(market_id=market.id, name="NaVi")
        outcome_spirit = Outcome(market_id=market.id, name="Spirit")
        db.add_all([outcome_navi, outcome_spirit])
        db.flush()
        
        # Oracle says NaVi won
        oracle = OracleService(provider_name="mock")
        result = oracle.fetch_event_result(event)
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        market.winning_outcome_id = winning_outcome.id
        db.commit()
        
        # Create bet and match
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
        
        EscrowService.lock_funds(db, maker, Decimal("100.00"), "Order", order.id)
        contract = MatchingService.match_order(db, order.id, taker, Decimal("100.00"))
        db.commit()
        
        # Maker tries to claim they won (correct)
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Taker disputes (incorrectly claims Spirit won)
        SettlementService.dispute_claim(db, contract, taker, "Spirit won!")
        db.commit()
        
        assert contract.status == ContractStatus.DISPUTED
        
        # Admin reviews and resolves in favor of correct result (NaVi)
        settled_contract = SettlementService.settle_contract(
            db=db,
            contract=contract,
            winning_outcome_id=outcome_navi.id  # Admin confirms NaVi won
        )
        db.commit()
        db.refresh(maker)
        db.refresh(taker)
        
        # Maker should win despite Taker's false dispute
        assert settled_contract.winner_id == maker.id
        assert maker.balance_available == Decimal("1078.40")  # Won
        assert taker.balance_available == Decimal("920.00")  # Lost


class TestPartialFillsE2E:
    """Test E2E with partial fills"""
    
    def test_multiple_takers_partial_fills(self, db):
        """
        Test one order filled by multiple takers
        
        Flow:
        1. Maker creates order for $300
        2. Taker1 takes $100
        3. Taker2 takes $150
        4. Taker3 takes $50
        5. Match finishes, all contracts settle
        """
        
        # Setup users
        maker = User(
            email="maker@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        taker1 = User(
            email="taker1@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        taker2 = User(
            email="taker2@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        taker3 = User(
            email="taker3@example.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        db.add_all([maker, taker1, taker2, taker3])
        db.commit()
        
        # Setup event
        event = Event(
            game_type="CS2",
            team_a="NaVi",
            team_b="Spirit",
            status=EventStatus.OPEN,
            external_match_id="match_1"
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
        
        outcome_navi = Outcome(market_id=market.id, name="NaVi")
        outcome_spirit = Outcome(market_id=market.id, name="Spirit")
        db.add_all([outcome_navi, outcome_spirit])
        db.commit()
        
        # Maker creates order for $300 @ 1.8
        order = Order(
            user_id=maker.id,
            market_id=market.id,
            outcome_id=outcome_navi.id,
            amount=Decimal("300.00"),
            unfilled_amount=Decimal("300.00"),
            odds=Decimal("1.80"),
            status=OrderStatus.OPEN
        )
        db.add(order)
        db.flush()
        
        EscrowService.lock_funds(db, maker, Decimal("300.00"), "Order", order.id)
        db.commit()
        
        # Taker1 takes $100
        contract1 = MatchingService.match_order(db, order.id, taker1, Decimal("100.00"))
        db.commit()
        db.refresh(order)
        
        assert order.unfilled_amount == Decimal("200.00")
        assert order.status == OrderStatus.PARTIALLY_FILLED
        
        # Taker2 takes $150
        contract2 = MatchingService.match_order(db, order.id, taker2, Decimal("150.00"))
        db.commit()
        db.refresh(order)
        
        assert order.unfilled_amount == Decimal("50.00")
        assert order.status == OrderStatus.PARTIALLY_FILLED
        
        # Taker3 takes remaining $50
        contract3 = MatchingService.match_order(db, order.id, taker3, Decimal("50.00"))
        db.commit()
        db.refresh(order)
        
        assert order.unfilled_amount == Decimal("0.00")
        assert order.status == OrderStatus.FILLED
        
        # Match finishes (NaVi wins)
        event.status = EventStatus.FINISHED
        db.commit()
        
        oracle = OracleService(provider_name="mock")
        result = oracle.fetch_event_result(event)
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        market.winning_outcome_id = winning_outcome.id
        market.status = MarketStatus.SETTLED
        db.commit()
        
        # Settle all contracts
        for contract in [contract1, contract2, contract3]:
            SettlementService.settle_contract(db, contract, outcome_navi.id)
        
        db.commit()
        db.refresh(maker)
        db.refresh(taker1)
        db.refresh(taker2)
        db.refresh(taker3)
        
        # Verify all settled
        assert contract1.status == ContractStatus.SETTLED
        assert contract2.status == ContractStatus.SETTLED
        assert contract3.status == ContractStatus.SETTLED
        
        # All takers lost
        assert taker1.balance_locked == Decimal("0.00")
        assert taker2.balance_locked == Decimal("0.00")
        assert taker3.balance_locked == Decimal("0.00")
        
        # Maker won all contracts
        # Contract1: 100 + 80 - 1.6 = 178.4
        # Contract2: 150 + 120 - 2.4 = 267.6
        # Contract3: 50 + 40 - 0.8 = 89.2
        # Total: 178.4 + 267.6 + 89.2 = 535.2
        
        expected_maker_balance = Decimal("700.00") + Decimal("535.20")
        assert maker.balance_available == expected_maker_balance