# app/services/matching.py
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Tuple

from app.models.user import User
from app.models.order import Order, OrderStatus
from app.models.contract import Contract, ContractStatus
from app.models.transaction import TransactionType
from app.services.escrow import EscrowService, InsufficientFundsError


class MatchingError(Exception):
    """Base exception for matching errors"""
    pass


class OrderNotAvailableError(MatchingError):
    """Raised when order cannot be matched (filled, cancelled, etc)"""
    pass


class MatchingService:
    """Service for P2P order matching and contract creation"""
    
    @staticmethod
    def calculate_taker_risk(maker_amount: Decimal, odds: Decimal) -> Decimal:
        """
        Calculate how much Taker needs to risk for a given Maker amount and odds
        
        Formula: taker_risk = maker_amount * (odds - 1)
        
        Example:
            Maker stakes $100 @ 1.8 odds
            Taker risk = 100 * (1.8 - 1) = 100 * 0.8 = $80
            
            If Maker wins: gets $100 + $80 = $180 (profit = $80)
            If Taker wins: gets $100 + $80 = $180 (profit = $100)
        
        Args:
            maker_amount: Amount Maker staked
            odds: Decimal odds (e.g., 1.80)
            
        Returns:
            Decimal: Amount Taker needs to risk
        """
        return maker_amount * (odds - Decimal("1.0"))
    
    @staticmethod
    def match_order(
        db: Session,
        order_id: int,
        taker: User,
        amount: Decimal
    ) -> Contract:
        """
        Match an order (Taker takes liquidity from Maker)
        
        Flow:
        1. Lock order for update (prevent race conditions)
        2. Validate order is available and has enough unfilled amount
        3. Calculate taker risk
        4. Lock taker funds
        5. Create contract
        6. Update order unfilled_amount
        7. Update order status if fully filled
        
        Args:
            db: Database session
            order_id: ID of order to match
            taker: User who is taking the order
            amount: Amount Taker wants to take (Maker's stake amount)
            
        Returns:
            Contract: Created contract
            
        Raises:
            OrderNotAvailableError: If order is not available for matching
            InsufficientFundsError: If taker doesn't have enough funds
            MatchingError: For other matching errors
        """
        
        # Lock order for update to prevent race conditions
        # with_for_update() ensures no other transaction can modify this order
        # until we commit
        # NOTE: with_for_update() is silently ignored on SQLite (no row-level locking support).
        # For production, migrate to PostgreSQL where this provides actual SELECT FOR UPDATE.
        # On SQLite this is safe for MVP since it's single-process with no true concurrency.
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        
        if not order:
            raise OrderNotAvailableError(f"Order {order_id} not found")
        
        # Validate order status
        if order.status not in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
            raise OrderNotAvailableError(
                f"Order {order_id} is not available (status: {order.status})"
            )
        
        # Validate taker is not the maker
        if order.user_id == taker.id:
            raise MatchingError("Cannot match your own order")
        
        # Validate amount doesn't exceed unfilled
        if amount > order.unfilled_amount:
            raise MatchingError(
                f"Requested amount ({amount}) exceeds unfilled amount ({order.unfilled_amount})"
            )
        
        # Calculate taker risk
        taker_risk = MatchingService.calculate_taker_risk(amount, order.odds)
        
        # Lock taker funds
        EscrowService.lock_funds(
            db=db,
            user=taker,
            amount=taker_risk,
            description=f"Contract with Order #{order_id}: taker risk {taker_risk}",
            order_id=order_id
        )
        
        # Create contract
        contract = Contract(
            market_id=order.market_id,
            order_id=order.id,
            maker_id=order.user_id,
            taker_id=taker.id,
            outcome_id=order.outcome_id,
            amount=amount,  # Maker's stake in this contract
            odds=order.odds,
            status=ContractStatus.ACTIVE
        )
        db.add(contract)
        db.flush()  # Get contract.id
        
        # Update order unfilled amount
        order.unfilled_amount -= amount
        
        # Update order status if fully filled
        if order.unfilled_amount == 0:
            order.status = OrderStatus.FILLED
        elif order.unfilled_amount < order.amount:
            order.status = OrderStatus.PARTIALLY_FILLED
        
        return contract