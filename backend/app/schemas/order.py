"""
Order schemas for request/response validation.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, ConfigDict


class OrderCreate(BaseModel):
    """Schema for creating a new order (Maker provides liquidity)"""
    market_id: int
    outcome_id: int
    amount: Decimal = Field(
        gt=0, 
        decimal_places=2, 
        description="Maker's stake amount"
    )
    odds: Decimal = Field(
        gt=1.0, 
        decimal_places=2, 
        description="Odds coefficient (e.g., 1.80)"
    )


class OrderResponse(BaseModel):
    """Schema for order API response"""
    id: int
    user_id: int
    market_id: int
    outcome_id: int
    amount: Decimal
    unfilled_amount: Decimal
    odds: Decimal
    status: str  # OPEN, PARTIALLY_FILLED, FILLED, CANCELLED
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class OrderListResponse(BaseModel):
    """Schema for paginated order list"""
    orders: list[OrderResponse]
    total: int

class MatchOrderRequest(BaseModel):
    """Schema for matching an order (Taker takes liquidity)"""
    amount: Decimal = Field(
        gt=0,
        decimal_places=2,
        description="Amount Taker wants to take (can be partial)"
    )


class ContractResponse(BaseModel):
    """Schema for contract API response"""
    id: int
    market_id: int
    order_id: int
    maker_id: int
    taker_id: int
    outcome_id: int
    amount: Decimal  # Maker's stake in this contract
    odds: Decimal
    status: str  # ACTIVE, CLAIMED, SETTLED, DISPUTED
    created_at: datetime
    
    # Optimistic Oracle fields
    claim_initiated_by: Optional[int] = None
    claim_initiated_at: Optional[datetime] = None
    challenge_deadline: Optional[datetime] = None
    
    # Settlement fields
    winner_id: Optional[int] = None
    settled_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)