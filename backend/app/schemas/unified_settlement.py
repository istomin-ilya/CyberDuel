# app/schemas/unified_settlement.py
"""
Unified settlement response schemas.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.models.market import MarketMode


class UnifiedSettlementResponse(BaseModel):
    """Response from unified settlement endpoint"""
    
    mode: MarketMode = Field(
        description="Market mode that was settled"
    )
    market_id: int = Field(
        description="ID of the settled market"
    )
    
    # P2P-specific fields (optional)
    total_contracts: Optional[int] = Field(
        None,
        description="Total contracts in market (P2P mode only)"
    )
    settled: Optional[int] = Field(
        None,
        description="Number of contracts settled (P2P mode only)"
    )
    already_settled: Optional[int] = Field(
        None,
        description="Number of contracts already settled (P2P mode only)"
    )
    errors: Optional[int] = Field(
        None,
        description="Number of settlement errors (P2P mode only)"
    )
    error_details: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Details of settlement errors (P2P mode only)"
    )
    
    # Pool-specific fields (optional)
    total_market_pool: Optional[str] = Field(
        None,
        description="Total market pool (Pool mode only)"
    )
    winning_pool_total: Optional[str] = Field(
        None,
        description="Total staked on winning outcome (Pool mode only)"
    )
    total_distributed: Optional[str] = Field(
        None,
        description="Total distributed to winners (Pool mode only)"
    )
    total_fees: Optional[str] = Field(
        None,
        description="Total platform fees collected (Pool mode only)"
    )
    winners_count: Optional[int] = Field(
        None,
        description="Number of winning bets (Pool mode only)"
    )
    losers_count: Optional[int] = Field(
        None,
        description="Number of losing bets (Pool mode only)"
    )
    winning_outcome_id: Optional[int] = Field(
        None,
        description="Winning outcome ID (Pool mode only)"
    )
    
    class Config:
        from_attributes = True
