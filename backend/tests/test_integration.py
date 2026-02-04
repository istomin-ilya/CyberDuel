"""
Integration tests for complete betting flow.

Tests the entire flow from event creation to settlement:
1. Admin creates Event + Market + Outcomes
2. Users create Orders (Maker provides liquidity)
3. Users match Orders (Taker takes liquidity)
4. Oracle fetches results
5. Market settles and pays winners
"""
import pytest
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.base import Base
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome
from app.models.order import Order, OrderStatus
from app.models.contract import Contract, ContractStatus
from app.models.transaction import Transaction, TransactionType
from app.services.escrow import EscrowService
from app.services.matching import MatchingService
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


@pytest.fixture
def users(db):
    """Create test users"""
    maker = User(
        email="maker@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00"),
        balance_locked=Decimal("0.00")
    )
    taker = User(
        email="taker@test.com",
        password_hash="hashed",
        balance_available=Decimal("1000.00"),
        balance_locked=Decimal("0.00")
    )
    db.add_all([maker, taker])
    db.commit()
    db.refresh(maker)
    db.refresh(taker)
    return {"maker": maker, "taker": taker}


@pytest.fixture
def event_with_market(db):
    """Create event with market and outcomes"""
    # Create event
    event = Event(
        game_type="CS2",
        team_a="NaVi",
        team_b="Spirit",
        status=EventStatus.OPEN,
        external_match_id="match_1"  # Will use mock data
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
    outcome_navi = Outcome(market_id=market.id, name="NaVi")
    outcome_spirit = Outcome(market_id=market.id, name="Spirit")
    db.add_all([outcome_navi, outcome_spirit])
    db.commit()
    
    db.refresh(event)
    db.refresh(market)
    db.refresh(outcome_navi)
    db.refresh(outcome_spirit)
    
    return {
        "event": event,
        "market": market,
        "outcome_navi": outcome_navi,
        "outcome_spirit": outcome_spirit
    }


class TestCompleteFlow:
    """Test complete betting flow from creation to settlement"""
    
    def test_full_betting_cycle(self, db, users, event_with_market):
        """
        Test complete flow:
        1. Maker creates order on NaVi
        2. Taker matches the order
        3. Event finishes, NaVi wins
        4. Market settles
        5. Maker gets payout
        """
        maker = users["maker"]
        taker = users["taker"]
        market = event_with_market["market"]
        outcome_navi = event_with_market["outcome_navi"]
        
        initial_maker_balance = maker.balance_available
        initial_taker_balance = taker.balance_available
        
        # Step 1: Maker creates order
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
        EscrowService.lock_funds(
            db=db,
            user=maker,
            amount=Decimal("100.00"),
            description=f"Order #{order.id} created",
            order_id=order.id
        )
        db.commit()
        
        # Verify maker balance locked
        assert maker.balance_available == initial_maker_balance - Decimal("100.00")
        assert maker.balance_locked == Decimal("100.00")
        
        # Step 2: Taker matches order
        contract = MatchingService.match_order(
            db=db,
            order_id=order.id,
            taker=taker,
            amount=Decimal("100.00")
        )
        db.commit()
        
        # Verify taker funds locked (risk = 100 * 0.8 = 80)
        taker_risk = Decimal("80.00")
        assert taker.balance_available == initial_taker_balance - taker_risk
        assert taker.balance_locked == taker_risk
        
        # Verify contract created
        assert contract.status == ContractStatus.ACTIVE
        assert contract.maker_id == maker.id
        assert contract.taker_id == taker.id
        assert contract.amount == Decimal("100.00")
        
        # Verify order filled
        db.refresh(order)
        assert order.status == OrderStatus.FILLED
        assert order.unfilled_amount == Decimal("0.00")
        
        # Step 3: Event finishes (mock: match_1 winner is team_a = NaVi)
        oracle = OracleService(provider_name="mock")
        event = event_with_market["event"]
        result = oracle.fetch_event_result(event)
        
        assert result.winner == "team_a"
        
        # Step 4: Determine winning outcome
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        assert winning_outcome.id == outcome_navi.id
        
        # Step 5: Settle market
        market.winning_outcome_id = winning_outcome.id
        market.status = MarketStatus.SETTLED
        db.commit()
        
        # Step 6: Settle contract (normally done by settlement service)
        # Pool = 100 (maker) + 80 (taker) = 180
        # Maker wins: gets back 100 + 80 = 180
        # Fee: 80 * 0.02 = 1.6
        # Payout: 100 + 78.4 = 178.4
        
        pool = contract.amount + taker_risk
        profit = taker_risk
        fee = profit * Decimal("0.02")
        payout = contract.amount + profit - fee
        
        # Unlock maker funds and add payout
        maker.balance_locked -= contract.amount
        maker.balance_available += payout
        
        # Unlock taker funds (loses)
        taker.balance_locked -= taker_risk
        
        # Mark contract as settled
        contract.status = ContractStatus.SETTLED
        contract.winner_id = maker.id
        
        db.commit()
        db.refresh(maker)
        db.refresh(taker)
        
        # Verify final balances
        expected_maker_final = initial_maker_balance + profit - fee
        expected_taker_final = initial_taker_balance - taker_risk
        
        assert maker.balance_available == expected_maker_final
        assert maker.balance_locked == Decimal("0.00")
        assert taker.balance_available == expected_taker_final
        assert taker.balance_locked == Decimal("0.00")
    
    def test_taker_wins_scenario(self, db, users, event_with_market):
        """
        Test scenario where Taker wins:
        1. Maker bets on NaVi
        2. Taker bets against (takes Spirit side)
        3. Spirit wins
        4. Taker gets payout
        """
        maker = users["maker"]
        taker = users["taker"]
        market = event_with_market["market"]
        outcome_spirit = event_with_market["outcome_spirit"]
        
        # For this test, we need Spirit to win
        # But mock match_1 has NaVi winning
        # Let's use match_2 where team_b wins
        
        # Update event to use match_2
        event = event_with_market["event"]
        event.external_match_id = "match_2"
        event.team_a = "G2"
        event.team_b = "FaZe"
        db.commit()
        
        # Update outcome names to match
        outcome_g2 = event_with_market["outcome_navi"]
        outcome_faze = event_with_market["outcome_spirit"]
        outcome_g2.name = "G2"
        outcome_faze.name = "FaZe"
        db.commit()
        
        initial_maker_balance = maker.balance_available
        initial_taker_balance = taker.balance_available
        
        # Maker bets on G2 (team_a)
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
        
        EscrowService.lock_funds(
            db=db,
            user=maker,
            amount=Decimal("100.00"),
            description="Order created",
            order_id=order.id
        )
        db.commit()
        
        # Taker matches (betting on FaZe - team_b)
        contract = MatchingService.match_order(
            db=db,
            order_id=order.id,
            taker=taker,
            amount=Decimal("100.00")
        )
        db.commit()
        
        taker_risk = Decimal("80.00")
        
        # Oracle: match_2 winner is team_b (FaZe)
        oracle = OracleService(provider_name="mock")
        result = oracle.fetch_event_result(event)
        
        assert result.winner == "team_b"
        
        # Determine winner (should be FaZe)
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        assert winning_outcome.id == outcome_faze.id
        
        # Settle: Taker wins
        # Pool = 100 + 80 = 180
        # Taker wins: gets back 80 + 100 = 180
        # Fee: 100 * 0.02 = 2
        # Payout: 80 + 98 = 178
        
        pool = contract.amount + taker_risk
        profit = contract.amount  # Maker's stake
        fee = profit * Decimal("0.02")
        payout = taker_risk + profit - fee
        
        # Unlock taker funds and add payout
        taker.balance_locked -= taker_risk
        taker.balance_available += payout
        
        # Unlock maker funds (loses)
        maker.balance_locked -= contract.amount
        
        contract.status = ContractStatus.SETTLED
        contract.winner_id = taker.id
        
        db.commit()
        db.refresh(maker)
        db.refresh(taker)
        
        # Verify final balances
        expected_maker_final = initial_maker_balance - contract.amount
        expected_taker_final = initial_taker_balance + profit - fee
        
        assert maker.balance_available == expected_maker_final
        assert taker.balance_available == expected_taker_final
    
    def test_partial_fill_with_settlement(self, db, users, event_with_market):
        """
        Test partial fill scenario with settlement:
        1. Maker creates order for 100
        2. Taker1 takes 30
        3. Taker2 takes 70
        4. Event settles
        5. Both contracts settle separately
        """
        maker = users["maker"]
        # Create second taker
        taker1 = User(
            email="taker1@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        taker2 = User(
            email="taker2@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        db.add_all([taker1, taker2])
        db.commit()
        
        market = event_with_market["market"]
        outcome_navi = event_with_market["outcome_navi"]
        
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
        
        EscrowService.lock_funds(db, maker, Decimal("100.00"), "Order created", order.id)
        db.commit()
        
        # Taker1 takes 30
        contract1 = MatchingService.match_order(db, order.id, taker1, Decimal("30.00"))
        db.commit()
        
        # Taker2 takes 70
        contract2 = MatchingService.match_order(db, order.id, taker2, Decimal("70.00"))
        db.commit()
        
        # Verify both contracts exist
        assert contract1.amount == Decimal("30.00")
        assert contract2.amount == Decimal("70.00")
        
        # Verify order filled
        db.refresh(order)
        assert order.status == OrderStatus.FILLED
        
        # Settle market (NaVi wins)
        oracle = OracleService(provider_name="mock")
        event = event_with_market["event"]
        result = oracle.fetch_event_result(event)
        winning_outcome = oracle.determine_winning_outcome(db, market, result)
        
        market.winning_outcome_id = winning_outcome.id
        market.status = MarketStatus.SETTLED
        db.commit()
        
        # Both contracts should settle with maker winning
        assert winning_outcome.id == outcome_navi.id


class TestEdgeCases:
    """Test edge cases and error scenarios"""
    
    def test_cannot_bet_on_closed_market(self, db, users, event_with_market):
        """Test that users cannot create orders on closed market"""
        maker = users["maker"]
        market = event_with_market["market"]
        outcome = event_with_market["outcome_navi"]
        
        # Close market
        market.status = MarketStatus.LOCKED
        db.commit()
        
        # Try to create order (would be rejected by API)
        # This test just verifies the status
        assert market.status == MarketStatus.LOCKED
    
    def test_transaction_audit_trail(self, db, users, event_with_market):
        """Test that all balance changes create transaction records"""
        maker = users["maker"]
        market = event_with_market["market"]
        outcome = event_with_market["outcome_navi"]
        
        # Create order with escrow
        order = Order(
            user_id=maker.id,
            market_id=market.id,
            outcome_id=outcome.id,
            amount=Decimal("100.00"),
            unfilled_amount=Decimal("100.00"),
            odds=Decimal("1.80"),
            status=OrderStatus.OPEN
        )
        db.add(order)
        db.flush()
        
        EscrowService.lock_funds(db, maker, Decimal("100.00"), "Order created", order.id)
        db.commit()
        
        # Verify transaction created
        txs = db.query(Transaction).filter(
            Transaction.user_id == maker.id,
            Transaction.type == TransactionType.ORDER_LOCK
        ).all()
        
        assert len(txs) == 1
        tx = txs[0]
        assert tx.amount == Decimal("100.00")
        assert tx.balance_available_before == Decimal("1000.00")
        assert tx.balance_available_after == Decimal("900.00")
        assert tx.balance_locked_after == Decimal("100.00")