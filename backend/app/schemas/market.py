# app/schemas/market.py
"""
Market and Outcome schemas for API requests and responses.
"""
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from typing import Optional

from app.models.market import MarketMode


class OutcomeCreate(BaseModel):
    """Schema for creating an outcome"""
    name: str  # "NaVi", "Over", "Yes", etc
    external_id: Optional[str] = None  # Team/player ID from external API


class OutcomeResponse(BaseModel):
    """Schema for outcome API response"""
    id: int
    market_id: int
    name: str
    external_id: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class MarketCreate(BaseModel):
    """Schema for creating a market (admin-only)"""
    event_id: int
    market_type: str  # match_winner, total_kills, first_blood, etc
    title: str  # "Match Winner", "Total Kills Over/Under"
    description: Optional[str] = None
    outcomes: list[OutcomeCreate]  # Must have at least 2 outcomes
    market_mode: Optional[MarketMode] = Field(
        default=MarketMode.P2P_DIRECT,
        description="Market mode: P2P_DIRECT for peer-to-peer order matching, POOL_MARKET for liquidity pool betting",
        example="P2P_DIRECT"
    )


class MarketUpdate(BaseModel):
    """Schema for updating a market (admin-only)"""
    status: Optional[str] = None  # PENDING, OPEN, LOCKED, SETTLED
    winning_outcome_id: Optional[int] = None  # Set after settlement


class MarketResponse(BaseModel):
    """Schema for market API response"""
    id: int
    event_id: int
    market_type: str
    title: str
    description: Optional[str] = None
    status: str  # PENDING, OPEN, LOCKED, SETTLED
    winning_outcome_id: Optional[int] = None
    market_mode: MarketMode
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # Include outcomes in response
    outcomes: list[OutcomeResponse] = []
    
    model_config = ConfigDict(from_attributes=True)


class MarketListResponse(BaseModel):
    """Schema for paginated market list"""
    markets: list[MarketResponse]
    total: int