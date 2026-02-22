"""
Unit tests for Settlement system with Optimistic Oracle.
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
from app.services.escrow import EscrowService
from app.services.matching import MatchingService
from app.services.settlement import (
    SettlementService,
    ClaimException,
    DisputeException,
    SettlementException
)


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
def settled_market_with_contract(db, users):
    """Create settled market with active contract"""
    maker = users["maker"]
    taker = users["taker"]
    
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
    
    # Settle market (NaVi wins - match_1)
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
    db.refresh(contract)
    
    return {
        "market": market,
        "outcome_navi": outcome_navi,
        "outcome_spirit": outcome_spirit,
        "contract": contract,
        "maker": maker,
        "taker": taker
    }


class TestClaimResult:
    """Test claiming contract results"""
    
    def test_maker_claims_win(self, db, settled_market_with_contract):
        """Test Maker claiming they won"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Maker claims NaVi won
        claimed_contract = SettlementService.claim_result(
            db=db,
            contract=contract,
            claiming_user=maker,
            winning_outcome_id=outcome_navi.id
        )
        
        assert claimed_contract.status == ContractStatus.CLAIMED
        assert claimed_contract.claim_initiated_by == maker.id
        assert claimed_contract.claim_initiated_at is not None
        assert claimed_contract.challenge_deadline is not None
        
        # Challenge deadline should be ~15 minutes from now
        time_diff = claimed_contract.challenge_deadline - claimed_contract.claim_initiated_at
        assert time_diff.total_seconds() == pytest.approx(15 * 60, rel=1)
    
    def test_taker_claims_loss(self, db, settled_market_with_contract):
        """Test Taker claiming they lost (same as Maker winning)"""
        contract = settled_market_with_contract["contract"]
        taker = settled_market_with_contract["taker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Taker can also claim (acknowledging they lost)
        claimed_contract = SettlementService.claim_result(
            db=db,
            contract=contract,
            claiming_user=taker,
            winning_outcome_id=outcome_navi.id
        )
        
        assert claimed_contract.status == ContractStatus.CLAIMED
        assert claimed_contract.claim_initiated_by == taker.id
    
    def test_cannot_claim_already_claimed(self, db, settled_market_with_contract):
        """Test cannot claim already claimed contract"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        taker = settled_market_with_contract["taker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Maker claims first
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Taker tries to claim again
        with pytest.raises(ClaimException, match="Cannot claim contract"):
            SettlementService.claim_result(db, contract, taker, outcome_navi.id)
    
    def test_cannot_claim_settled_contract(self, db, settled_market_with_contract):
        """Test cannot claim already settled contract"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Settle contract first
        contract.status = ContractStatus.SETTLED
        db.commit()
        
        # Try to claim
        with pytest.raises(ClaimException, match="Cannot claim contract"):
            SettlementService.claim_result(db, contract, maker, outcome_navi.id)
    
    def test_non_participant_cannot_claim(self, db, settled_market_with_contract):
        """Test non-participant cannot claim"""
        contract = settled_market_with_contract["contract"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Create another user
        outsider = User(
            email="outsider@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        db.add(outsider)
        db.commit()
        
        # Outsider tries to claim
        with pytest.raises(ClaimException, match="Only contract participants"):
            SettlementService.claim_result(db, contract, outsider, outcome_navi.id)
    
    def test_cannot_claim_invalid_outcome(self, db, settled_market_with_contract):
        """Test cannot claim with outcome from different market"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        
        # Try to claim with invalid outcome ID
        with pytest.raises(ClaimException, match="does not belong to this market"):
            SettlementService.claim_result(db, contract, maker, 99999)


class TestDisputeClaim:
    """Test disputing claims"""
    
    def test_taker_disputes_maker_claim(self, db, settled_market_with_contract):
        """Test Taker disputing Maker's claim"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        taker = settled_market_with_contract["taker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Maker claims
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Taker disputes
        disputed_contract = SettlementService.dispute_claim(
            db=db,
            contract=contract,
            disputing_user=taker,
            reason="NaVi didn't win, Spirit won!"
        )
        
        assert disputed_contract.status == ContractStatus.DISPUTED
    
    def test_cannot_dispute_own_claim(self, db, settled_market_with_contract):
        """Test cannot dispute your own claim"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Maker claims
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Maker tries to dispute own claim
        with pytest.raises(DisputeException, match="Cannot dispute your own claim"):
            SettlementService.dispute_claim(db, contract, maker)
    
    def test_cannot_dispute_after_deadline(self, db, settled_market_with_contract):
        """Test cannot dispute after challenge period expires"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        taker = settled_market_with_contract["taker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Maker claims
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Manually expire deadline
        contract.challenge_deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        
        # Taker tries to dispute
        with pytest.raises(DisputeException, match="Challenge period has expired"):
            SettlementService.dispute_claim(db, contract, taker)
    
    def test_cannot_dispute_unclaimed_contract(self, db, settled_market_with_contract):
        """Test cannot dispute contract that hasn't been claimed"""
        contract = settled_market_with_contract["contract"]
        taker = settled_market_with_contract["taker"]
        
        # Try to dispute without claim
        with pytest.raises(DisputeException, match="Cannot dispute contract"):
            SettlementService.dispute_claim(db, contract, taker)
    
    def test_non_participant_cannot_dispute(self, db, settled_market_with_contract):
        """Test non-participant cannot dispute"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Maker claims
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Create outsider
        outsider = User(
            email="outsider@test.com",
            password_hash="hashed",
            balance_available=Decimal("1000.00"),
            balance_locked=Decimal("0.00")
        )
        db.add(outsider)
        db.commit()
        
        # Outsider tries to dispute
        with pytest.raises(DisputeException, match="Only contract participants"):
            SettlementService.dispute_claim(db, contract, outsider)


class TestSettlement:
    """Test contract settlement"""
    
    def test_settle_maker_wins(self, db, settled_market_with_contract):
        """Test settling contract where Maker wins"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        taker = settled_market_with_contract["taker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        initial_maker_available = maker.balance_available
        initial_taker_available = taker.balance_available
        
        # Settle: NaVi wins (Maker's outcome)
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
        assert settled_contract.settled_at is not None
        
        # Verify balances
        # Pool = 100 (maker) + 80 (taker) = 180
        # Profit = 80
        # Fee = 80 * 0.02 = 1.6
        # Payout to maker = 100 (returned stake) + 80 (profit) - 1.6 (fee) = 178.4
        # initial_maker_available is already without locked funds (900.00)
        # So final = 900.00 + 178.4 = 1078.40
        
        expected_maker_final = initial_maker_available + Decimal("178.40")
        expected_taker_final = initial_taker_available
        
        assert maker.balance_available == expected_maker_final
        assert maker.balance_locked == Decimal("0.00")
        assert taker.balance_available == expected_taker_final
        assert taker.balance_locked == Decimal("0.00")
        
        # Verify transactions created
        maker_txs = db.query(Transaction).filter(
            Transaction.user_id == maker.id,
            Transaction.type == TransactionType.SETTLEMENT
        ).all()
        assert len(maker_txs) == 1
        
        taker_txs = db.query(Transaction).filter(
            Transaction.user_id == taker.id,
            Transaction.type == TransactionType.SETTLEMENT
        ).all()
        assert len(taker_txs) == 1
    
    def test_settle_taker_wins(self, db, settled_market_with_contract):
        """Test settling contract where Taker wins"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        taker = settled_market_with_contract["taker"]
        outcome_spirit = settled_market_with_contract["outcome_spirit"]
        
        initial_maker_available = maker.balance_available
        initial_taker_available = taker.balance_available
        
        # Settle: Spirit wins (NOT Maker's outcome, so Taker wins)
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
        
        # Verify balances
        # Pool = 100 (maker) + 80 (taker) = 180
        # Profit = 100 (maker's stake)
        # Fee = 100 * 0.02 = 2
        # Payout to taker = 80 (returned stake) + 100 (profit) - 2 (fee) = 178
        # initial_taker_available is already without locked funds (920.00)
        # So final = 920.00 + 178 = 1098.00
        
        expected_maker_final = initial_maker_available
        expected_taker_final = initial_taker_available + Decimal("178.00")
        
        assert maker.balance_available == expected_maker_final
        assert maker.balance_locked == Decimal("0.00")
        assert taker.balance_available == expected_taker_final
        assert taker.balance_locked == Decimal("0.00")
    
    def test_fee_calculation(self, db, settled_market_with_contract):
        """Test 2% fee is correctly calculated"""
        contract = settled_market_with_contract["contract"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Settle
        SettlementService.settle_contract(db, contract, outcome_navi.id)
        
        # Check fee transaction
        fee_txs = db.query(Transaction).filter(
            Transaction.type == TransactionType.FEE,
            Transaction.contract_id == contract.id
        ).all()
        
        assert len(fee_txs) == 1
        # Fee should be 2% of profit (80 * 0.02 = 1.6)
        assert fee_txs[0].amount == Decimal("1.60")


class TestAutoSettlement:
    """Test automatic settlement of unchallenged claims"""
    
    def test_auto_settle_after_deadline(self, db, settled_market_with_contract):
        """Test auto-settlement after challenge period expires"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Claim result
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Expire deadline
        contract.challenge_deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        
        # Auto-settle
        settled_contract = SettlementService.auto_settle_unchallenged(db, contract)
        
        assert settled_contract.status == ContractStatus.SETTLED
        assert settled_contract.winner_id == maker.id
    
    def test_cannot_auto_settle_before_deadline(self, db, settled_market_with_contract):
        """Test cannot auto-settle before challenge period expires"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Claim result
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Try to auto-settle immediately
        with pytest.raises(SettlementException, match="Challenge period has not expired"):
            SettlementService.auto_settle_unchallenged(db, contract)
    
    def test_get_pending_claims(self, db, settled_market_with_contract):
        """Test getting contracts ready for auto-settlement"""
        contract = settled_market_with_contract["contract"]
        maker = settled_market_with_contract["maker"]
        outcome_navi = settled_market_with_contract["outcome_navi"]
        
        # Claim result
        SettlementService.claim_result(db, contract, maker, outcome_navi.id)
        
        # Expire deadline
        contract.challenge_deadline = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
        
        # Get pending claims
        pending = SettlementService.get_pending_claims(db)
        
        assert len(pending) == 1
        assert pending[0].id == contract.id


class TestCalculations:
    """Test settlement calculations"""
    
    def test_calculate_taker_risk(self):
        """Test taker risk calculation"""
        risk = SettlementService.calculate_taker_risk(
            Decimal("100.00"),
            Decimal("1.80")
        )
        assert risk == Decimal("80.00")
        
        risk2 = SettlementService.calculate_taker_risk(
            Decimal("50.00"),
            Decimal("2.50")
        )
        assert risk2 == Decimal("75.00")