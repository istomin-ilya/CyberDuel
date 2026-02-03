"""
Escrow service - fund locking/unlocking logic.
"""
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models.user import User
from ..models.transaction import Transaction, TransactionType


class InsufficientFundsError(Exception):
    """Raised when user doesn't have enough available balance"""
    pass


class EscrowService:
    """Service for managing fund locking/unlocking (escrow logic)"""
    
    @staticmethod
    def lock_funds(
        db: Session,
        user: User,
        amount: Decimal,
        description: str,
        order_id: int = None
    ) -> Transaction:
        """
        Lock user funds (available -> locked)
        
        Args:
            db: Database session
            user: User whose funds to lock
            amount: Amount to lock
            description: Transaction description for audit trail
            order_id: Optional order ID reference
            
        Returns:
            Transaction: Created transaction record
            
        Raises:
            InsufficientFundsError: If user doesn't have enough available balance
        """
        if user.balance_available < amount:
            raise InsufficientFundsError(
                f"Insufficient funds: available={user.balance_available}, required={amount}"
            )
        
        # Snapshots BEFORE change
        available_before = user.balance_available
        locked_before = user.balance_locked
        
        # Update balances
        user.balance_available -= amount
        user.balance_locked += amount
        
        # Create transaction for audit trail
        transaction = Transaction(
            user_id=user.id,
            type=TransactionType.ORDER_LOCK,
            amount=amount,
            balance_available_before=available_before,
            balance_available_after=user.balance_available,
            balance_locked_before=locked_before,
            balance_locked_after=user.balance_locked,
            order_id=order_id,
            description=description
        )
        
        db.add(transaction)
        return transaction
    
    @staticmethod
    def unlock_funds(
        db: Session,
        user: User,
        amount: Decimal,
        description: str,
        order_id: int = None
    ) -> Transaction:
        """
        Unlock user funds (locked -> available)
        Used when cancelling orders
        
        Args:
            db: Database session
            user: User whose funds to unlock
            amount: Amount to unlock
            description: Transaction description for audit trail
            order_id: Optional order ID reference
            
        Returns:
            Transaction: Created transaction record
            
        Raises:
            ValueError: If trying to unlock more than locked balance
        """
        if user.balance_locked < amount:
            raise ValueError(
                f"Cannot unlock more than locked: locked={user.balance_locked}, requested={amount}"
            )
        
        # Snapshots BEFORE change
        available_before = user.balance_available
        locked_before = user.balance_locked
        
        # Update balances
        user.balance_locked -= amount
        user.balance_available += amount
        
        # Create transaction for audit trail
        transaction = Transaction(
            user_id=user.id,
            type=TransactionType.ORDER_UNLOCK,
            amount=amount,
            balance_available_before=available_before,
            balance_available_after=user.balance_available,
            balance_locked_before=locked_before,
            balance_locked_after=user.balance_locked,
            order_id=order_id,
            description=description
        )
        
        db.add(transaction)
        return transaction