"""
Schemas for Pool Market endpoints.
"""
from decimal import Decimal
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class PoolBetCreate(BaseModel):
    """Request to place a bet in pool market"""
    outcome_id: int = Field(..., description="Outcome to bet on")
    amount: Decimal = Field(..., gt=0, description="Bet amount (must be positive)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "outcome_id": 1,
            "amount": "100.00"
        }
    })


class PoolBetResponse(BaseModel):
    """Response for pool bet"""
    id: int
    user_id: int
    market_id: int
    outcome_id: int
    amount: Decimal
    initial_pool_share_percentage: Decimal
    pool_size_at_bet: Decimal
    settled: bool
    settled_at: Optional[datetime] = None
    actual_payout: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class OutcomePoolState(BaseModel):
    """Pool state for single outcome"""
    outcome_id: int
    outcome_name: str
    total_staked: Decimal
    participant_count: int
    estimated_odds: Decimal
    estimated_roi: Decimal
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "outcome_id": 1,
            "outcome_name": "NaVi",
            "total_staked": "700.00",
            "participant_count": 2,
            "estimated_odds": "1.43",
            "estimated_roi": "43.00"
        }
    })


class PoolStateResponse(BaseModel):
    """Current state of pool market"""
    market_id: int
    total_pool: Decimal
    outcomes: List[OutcomePoolState]
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "market_id": 5,
            "total_pool": "1000.00",
            "outcomes": [
                {
                    "outcome_id": 1,
                    "outcome_name": "NaVi",
                    "total_staked": "700.00",
                    "participant_count": 2,
                    "estimated_odds": "1.43",
                    "estimated_roi": "43.00"
                },
                {
                    "outcome_id": 2,
                    "outcome_name": "G2",
                    "total_staked": "300.00",
                    "participant_count": 1,
                    "estimated_odds": "3.33",
                    "estimated_roi": "233.00"
                }
            ]
        }
    })


class PoolBetListResponse(BaseModel):
    """List of pool bets with pagination"""
    bets: List[PoolBetResponse]
    total: int
    page: int
    page_size: int
    
    model_config = ConfigDict(from_attributes=True)


class PoolSettlementResponse(BaseModel):
    """Settlement result for pool market"""
    market_id: int
    winning_outcome_id: int
    winners_count: int
    losers_count: int
    total_market_pool: Decimal
    winning_pool_total: Decimal
    total_distributed: Decimal
    total_fees: Decimal
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "market_id": 5,
            "winning_outcome_id": 1,
            "winners_count": 2,
            "losers_count": 1,
            "total_market_pool": "1000.00",
            "winning_pool_total": "700.00",
            "total_distributed": "994.00",
            "total_fees": "6.00"
        }
    })