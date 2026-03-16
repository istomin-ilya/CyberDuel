"""
Transaction schemas for request/response validation.
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class TransactionResponse(BaseModel):
    """Schema for transaction API response"""
    id: int
    type: str
    amount: Decimal
    description: Optional[str] = None

    balance_available_before: Decimal
    balance_available_after: Decimal
    balance_locked_before: Decimal
    balance_locked_after: Decimal

    order_id: Optional[int] = None
    contract_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    """Schema for paginated transaction list"""
    transactions: list[TransactionResponse]
    total: int
    page: int
    page_size: int
