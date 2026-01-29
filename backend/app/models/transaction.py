"""
Transaction model - Audit log for all balance changes.
"""
from decimal import Decimal
from enum import Enum
from sqlalchemy import Numeric, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import Optional, TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class TransactionType(str, Enum):
    """Types of balance operations."""
    DEPOSIT = "DEPOSIT"
    WITHDRAWAL = "WITHDRAWAL"
    ORDER_LOCK = "ORDER_LOCK"
    ORDER_UNLOCK = "ORDER_UNLOCK"
    CONTRACT_LOCK = "CONTRACT_LOCK"
    SETTLEMENT = "SETTLEMENT"
    FEE = "FEE"


class Transaction(Base, TimestampMixin):
    """
    Immutable audit log of all balance changes.
    
    Every change to user balance creates a transaction record.
    This provides complete financial audit trail.
    
    Attributes:
        user_id: Whose balance changed
        type: What kind of operation
        amount: How much changed (positive or negative)
        balance_available_before: Available balance before operation
        balance_available_after: Available balance after operation
        balance_locked_before: Locked balance before operation
        balance_locked_after: Locked balance after operation
        order_id: Related order (if applicable)
        contract_id: Related contract (if applicable)
        description: Human-readable explanation
    """
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    
    type: Mapped[TransactionType] = mapped_column(nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    
    # Balance snapshots (for audit)
    balance_available_before: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    balance_available_after: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    balance_locked_before: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    balance_locked_after: Mapped[Decimal] = mapped_column(Numeric(precision=10, scale=2), nullable=False)
    
    # References
    order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("orders.id"))
    contract_id: Mapped[Optional[int]] = mapped_column(ForeignKey("contracts.id"))
    
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    user: Mapped["User"] = relationship(back_populates="transactions")
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, user={self.user_id}, type={self.type.value}, amount={self.amount})>"