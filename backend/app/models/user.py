# app/models/user.py
"""
User model - Authentication and balance management.
"""
from decimal import Decimal
from sqlalchemy import String, Numeric, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from typing import TYPE_CHECKING

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .order import Order
    from .contract import Contract
    from .transaction import Transaction
    from .pool_bet import PoolBet


class User(Base, TimestampMixin):
    """
    User account with authentication and balance tracking.
    
    Attributes:
        email: Unique user identifier
        password_hash: Argon2 hashed password
        balance_available: Funds available for new orders
        balance_locked: Funds currently in active orders/contracts
        is_admin: Admin privileges flag
    
    Invariant: total_balance = balance_available + balance_locked
    """
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Balance tracking (using Decimal for precision)
    balance_available: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        default=Decimal("0.00"),
        nullable=False
    )
    balance_locked: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        default=Decimal("0.00"),
        nullable=False
    )
    
    # Admin flag
    is_admin: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False
    )
    
    # Relationships (P2P Direct)
    orders: Mapped[list["Order"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    contracts_as_maker: Mapped[list["Contract"]] = relationship(
        foreign_keys="Contract.maker_id",
        back_populates="maker",
        cascade="all, delete-orphan"
    )
    contracts_as_taker: Mapped[list["Contract"]] = relationship(
        foreign_keys="Contract.taker_id",
        back_populates="taker",
        cascade="all, delete-orphan"
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    # Relationships (Pool Market)
    pool_bets: Mapped[list["PoolBet"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', admin={self.is_admin}, available={self.balance_available})>"