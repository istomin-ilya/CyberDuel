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