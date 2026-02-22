# app/services/settlement.py
"""
Settlement service for contract resolution with Optimistic Oracle.

Flow:
1. User claims result → 15min challenge period starts
2. If no dispute → auto-settle after deadline
3. If disputed → admin resolves manually
"""
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.contract import Contract, ContractStatus
from app.models.market import Market, MarketStatus
from app.models.outcome import Outcome
from app.models.user import User
from app.models.transaction import TransactionType
from app.services.escrow import EscrowService


def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware (UTC).
    
    SQLite doesn't fully support timezone-aware datetimes, so we need to
    explicitly add UTC timezone to naive datetimes from the database.
    
    Args:
        dt: Datetime that may or may not be timezone-aware
        
    Returns:
        Timezone-aware datetime in UTC, or None if input is None
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetimes from DB are in UTC
        return dt.replace(tzinfo=timezone.utc)
    return dt


class SettlementException(Exception):
    """Base exception for settlement errors"""
    pass


class ClaimException(SettlementException):
    """Raised when claim operation fails"""
    pass


class DisputeException(SettlementException):
    """Raised when dispute operation fails"""
    pass


class SettlementService:
    """
    Service for contract settlement with Optimistic Oracle.
    
    Implements trustless settlement with challenge period.
    """
    
    # Platform fee (2%)
    FEE_RATE = Decimal("0.02")
    
    # Challenge period (15 minutes)
    CHALLENGE_PERIOD_MINUTES = 15
    
    @staticmethod
    def claim_result(
        db: Session,
        contract: Contract,
        claiming_user: User,
        winning_outcome_id: int
    ) -> Contract:
        """
        Initiate claim for contract result.
        
        Starts 15-minute challenge period. If no dispute, contract
        auto-settles after deadline.
        
        Args:
            db: Database session
            contract: Contract to claim
            claiming_user: User making the claim (Maker or Taker)
            winning_outcome_id: Claimed winning outcome
            
        Returns:
            Contract: Updated contract with claim data
            
        Raises:
            ClaimException: If claim is invalid
        """
        # Validate contract status
        if contract.status != ContractStatus.ACTIVE:
            raise ClaimException(
                f"Cannot claim contract with status {contract.status}"
            )
        
        # Validate user is participant
        if claiming_user.id not in [contract.maker_id, contract.taker_id]:
            raise ClaimException(
                "Only contract participants can claim results"
            )
        
        # Validate outcome belongs to contract's market
        outcome = db.query(Outcome).filter(
            Outcome.id == winning_outcome_id,
            Outcome.market_id == contract.market_id
        ).first()
        
        if not outcome:
            raise ClaimException(
                f"Outcome {winning_outcome_id} does not belong to this market"
            )
        
        # Set claim data
        contract.claim_initiated_by = claiming_user.id
        contract.claim_initiated_at = datetime.now(timezone.utc)
        contract.challenge_deadline = (
            datetime.now(timezone.utc) + 
            timedelta(minutes=SettlementService.CHALLENGE_PERIOD_MINUTES)
        )
        contract.status = ContractStatus.CLAIMED
        
        # Store claimed outcome (we'll use winner_id temporarily)
        # In production, add a separate field for claimed_outcome_id
        contract.winner_id = None  # Will be set on settlement
        
        # Store claimed outcome in a way we can retrieve it
        # For now, we'll determine winner based on outcome
        # This is a simplification - in production add claimed_outcome_id field
        
        db.commit()
        db.refresh(contract)
        
        return contract
    
    @staticmethod
    def dispute_claim(
        db: Session,
        contract: Contract,
        disputing_user: User,
        reason: Optional[str] = None
    ) -> Contract:
        """
        Dispute a claimed result.
        
        Must be done within challenge period. Moves contract to
        DISPUTED status for admin resolution.
        
        Args:
            db: Database session
            contract: Contract to dispute
            disputing_user: User disputing the claim
            reason: Optional reason for dispute
            
        Returns:
            Contract: Updated contract with dispute data
            
        Raises:
            DisputeException: If dispute is invalid
        """
        # Validate contract is claimed
        if contract.status != ContractStatus.CLAIMED:
            raise DisputeException(
                f"Cannot dispute contract with status {contract.status}"
            )
        
        # Validate within challenge period
        challenge_deadline = _ensure_utc(contract.challenge_deadline)
        if datetime.now(timezone.utc) > challenge_deadline:
            raise DisputeException(
                "Challenge period has expired"
            )
        
        # Validate user is the OTHER participant
        if disputing_user.id == contract.claim_initiated_by:
            raise DisputeException(
                "Cannot dispute your own claim"
            )
        
        if disputing_user.id not in [contract.maker_id, contract.taker_id]:
            raise DisputeException(
                "Only contract participants can dispute"
            )
        
        # Set dispute data
        # Note: In production, add disputed_by and disputed_at fields to Contract model
        contract.status = ContractStatus.DISPUTED
        
        db.commit()
        db.refresh(contract)
        
        return contract
    
    @staticmethod
    def auto_settle_unchallenged(db: Session, contract: Contract) -> Contract:
        """
        Automatically settle contract after challenge period expires.
        
        Called by background task for contracts in CLAIMED status
        where challenge_deadline has passed.
        
        Args:
            db: Database session
            contract: Contract to settle
            
        Returns:
            Contract: Settled contract
            
        Raises:
            SettlementException: If auto-settlement fails
        """
        # Validate status
        if contract.status != ContractStatus.CLAIMED:
            raise SettlementException(
                f"Cannot auto-settle contract with status {contract.status}"
            )
        
        # Validate deadline passed
        challenge_deadline = _ensure_utc(contract.challenge_deadline)
        if datetime.now(timezone.utc) < challenge_deadline:
            raise SettlementException(
                "Challenge period has not expired yet"
            )
        
        # Get market to determine actual winner
        market = db.query(Market).filter(Market.id == contract.market_id).first()
        if not market or not market.winning_outcome_id:
            raise SettlementException(
                "Market has not been settled yet"
            )
        
        # Settle contract
        return SettlementService.settle_contract(
            db=db,
            contract=contract,
            winning_outcome_id=market.winning_outcome_id,
            auto_commit=False
        )
    
    @staticmethod
    def settle_contract(
        db: Session,
        contract: Contract,
        winning_outcome_id: int,
        auto_commit: bool = True
    ) -> Contract:
        """
        Settle contract and distribute funds.
        
        Flow:
        1. Determine winner (Maker or Taker)
        2. Calculate pool, profit, fee, payout
        3. Unlock loser funds (they lose their stake)
        4. Unlock winner funds and add payout
        5. Record settlement transaction
        
        Args:
            db: Database session
            contract: Contract to settle
            winning_outcome_id: Actual winning outcome
            auto_commit: Whether to commit immediately (default True). 
                        Set to False when settling multiple contracts in a transaction.
            
        Returns:
            Contract: Settled contract
        """
        # Get participants
        maker = db.query(User).filter(User.id == contract.maker_id).first()
        taker = db.query(User).filter(User.id == contract.taker_id).first()
        
        if not maker or not taker:
            raise SettlementException("Contract participants not found")
        
        # Calculate amounts
        maker_stake = contract.amount
        taker_risk = SettlementService.calculate_taker_risk(
            maker_stake, 
            contract.odds
        )
        
        pool = maker_stake + taker_risk
        
        # Determine winner
        if contract.outcome_id == winning_outcome_id:
            # Maker's outcome won
            winner = maker
            loser = taker
            winner_stake = maker_stake
            loser_stake = taker_risk
            profit = taker_risk
        else:
            # Taker won (bet against Maker's outcome)
            winner = taker
            loser = maker
            winner_stake = taker_risk
            loser_stake = maker_stake
            profit = maker_stake
        
        # Calculate fee and payout
        fee = profit * SettlementService.FEE_RATE
        payout = winner_stake + profit - fee
        
        # Unlock loser funds (they lose everything)
        loser.balance_locked -= loser_stake
        
        # Record loser transaction
        from app.models.transaction import Transaction
        loser_tx = Transaction(
            user_id=loser.id,
            type=TransactionType.SETTLEMENT,
            amount=-loser_stake,
            balance_available_before=loser.balance_available,
            balance_available_after=loser.balance_available,
            balance_locked_before=loser.balance_locked + loser_stake,
            balance_locked_after=loser.balance_locked,
            contract_id=contract.id,
            description=f"Contract #{contract.id} settled: LOSS"
        )
        db.add(loser_tx)
        
        # Unlock winner funds and add payout
        winner.balance_locked -= winner_stake
        winner.balance_available += payout
        
        # Record winner transaction
        winner_tx = Transaction(
            user_id=winner.id,
            type=TransactionType.SETTLEMENT,
            amount=payout - winner_stake,  # Net profit
            balance_available_before=winner.balance_available - payout,
            balance_available_after=winner.balance_available,
            balance_locked_before=winner.balance_locked + winner_stake,
            balance_locked_after=winner.balance_locked,
            contract_id=contract.id,
            description=f"Contract #{contract.id} settled: WIN (fee: {fee})"
        )
        db.add(winner_tx)
        
        # Record fee transaction (platform revenue)
        # Note: In production, transfer fee to platform account
        fee_tx = Transaction(
            user_id=winner.id,
            type=TransactionType.FEE,
            amount=fee,
            balance_available_before=winner.balance_available,
            balance_available_after=winner.balance_available,
            balance_locked_before=winner.balance_locked,
            balance_locked_after=winner.balance_locked,
            contract_id=contract.id,
            description=f"Platform fee (2%)"
        )
        db.add(fee_tx)
        
        # Update contract
        contract.winner_id = winner.id
        contract.status = ContractStatus.SETTLED
        contract.settled_at = datetime.now(timezone.utc)
        
        if auto_commit:
            db.commit()
            db.refresh(contract)
        else:
            db.flush()
        
        return contract
    
    @staticmethod
    def calculate_taker_risk(maker_amount: Decimal, odds: Decimal) -> Decimal:
        """
        Calculate taker's risk amount.
        
        Formula: taker_risk = maker_amount * (odds - 1)
        
        Args:
            maker_amount: Maker's stake
            odds: Odds coefficient
            
        Returns:
            Decimal: Taker's risk amount
        """
        return maker_amount * (odds - Decimal("1.0"))
    
    @staticmethod
    def get_pending_claims(db: Session) -> list[Contract]:
        """
        Get contracts with expired challenge periods ready for auto-settlement.
        
        Used by background task.
        
        Args:
            db: Database session
            
        Returns:
            list[Contract]: Contracts ready to auto-settle
        """
        # For SQLite, convert timezone-aware datetime to naive UTC for comparison
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        
        contracts = db.query(Contract).filter(
            Contract.status == ContractStatus.CLAIMED,
            Contract.challenge_deadline <= now
        ).all()
        
        return contracts
    
    @staticmethod
    def settle_market(market_id: int, db: Session) -> dict:
        """
        Settle all contracts for a P2P market.
        
        Processes all ACTIVE and CLAIMED contracts for the market and settles them
        based on the market's winning outcome.
        
        Args:
            market_id: Market ID to settle
            db: Database session
            
        Returns:
            dict: Settlement statistics with keys:
                - market_id: Market ID
                - total_contracts: Total contracts found
                - settled: Number of newly settled contracts
                - already_settled: Number of already settled contracts
                - errors: Number of errors encountered
                - error_details: List of error details (if any)
                
        Raises:
            ValueError: If market not found, not SETTLED, or no winning outcome
        """
        # Получить маркет
        market = db.query(Market).filter(Market.id == market_id).first()
        if not market:
            raise ValueError("Market not found")
        
        # Проверить что маркет в статусе SETTLED
        if market.status != MarketStatus.SETTLED:
            raise ValueError("Market must be in SETTLED status")
        
        # Проверить что есть winning outcome
        if not market.winning_outcome_id:
            raise ValueError("Market must have winning_outcome_id set")
        
        # Найти все контракты маркета (ACTIVE или CLAIMED)
        contracts = db.query(Contract).filter(
            Contract.market_id == market_id,
            Contract.status.in_([ContractStatus.ACTIVE, ContractStatus.CLAIMED])
        ).all()
        
        # Если контрактов нет, вернуть раньше
        if not contracts:
            return {
                "market_id": market_id,
                "total_contracts": 0,
                "settled": 0,
                "already_settled": 0,
                "errors": 0,
                "error_details": None,
                "message": "No contracts to settle"
            }
        
        # Счетчики
        settled_count = 0
        already_settled_count = 0
        error_count = 0
        errors = []
        
        # Settlement каждого контракта
        for contract in contracts:
            try:
                # Пропустить уже settled контракты
                if contract.status == ContractStatus.SETTLED:
                    already_settled_count += 1
                    continue
                
                # Settle контракт (без auto_commit для batch operation)
                SettlementService.settle_contract(
                    db=db,
                    contract=contract,
                    winning_outcome_id=market.winning_outcome_id,
                    auto_commit=False
                )
                settled_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append({
                    "contract_id": contract.id,
                    "error": str(e)
                })
                # Continue - не прерывать весь процесс
                continue
        
        # Commit транзакции
        db.commit()
        
        # Return результат
        return {
            "market_id": market_id,
            "total_contracts": len(contracts),
            "settled": settled_count,
            "already_settled": already_settled_count,
            "errors": error_count,
            "error_details": errors if errors else None
        }