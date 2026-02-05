# app/schemas/settlement.py
"""
Settlement and claim schemas.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from decimal import Decimal
from typing import Optional


class ClaimRequest(BaseModel):
    """Schema for claiming contract result"""
    winning_outcome_id: int


class ClaimResponse(BaseModel):
    """Schema for claim response"""
    contract_id: int
    claim_initiated_by: int
    claim_initiated_at: datetime
    challenge_deadline: datetime
    winning_outcome_id: int
    status: str  # CLAIMED
    
    model_config = ConfigDict(from_attributes=True)


class DisputeRequest(BaseModel):
    """Schema for disputing a claim"""
    reason: Optional[str] = None


class DisputeResponse(BaseModel):
    """Schema for dispute response"""
    contract_id: int
    status: str  # DISPUTED
    disputed_by: int
    disputed_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SettlementResponse(BaseModel):
    """Schema for settlement result"""
    contract_id: int
    winner_id: int
    loser_id: int
    pool: Decimal
    profit: Decimal
    fee: Decimal
    payout: Decimal
    status: str  # SETTLED
    settled_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class ContractDetailResponse(BaseModel):
    """Schema for detailed contract info with settlement data"""
    id: int
    market_id: int
    order_id: int
    maker_id: int
    taker_id: int
    outcome_id: int
    amount: Decimal
    odds: Decimal
    status: str
    
    # Optimistic Oracle fields
    claim_initiated_by: Optional[int] = None
    claim_initiated_at: Optional[datetime] = None
    challenge_deadline: Optional[datetime] = None
    
    # Dispute fields
    disputed_by: Optional[int] = None
    disputed_at: Optional[datetime] = None
    
    # Settlement fields
    winner_id: Optional[int] = None
    settled_at: Optional[datetime] = None
    
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AdminResolveDisputeRequest(BaseModel):
    """Schema for admin dispute resolution"""
    winning_outcome_id: int
    resolution_notes: Optional[str] = None


class DisputeListResponse(BaseModel):
    """Schema for list of disputed contracts"""
    contracts: list[ContractDetailResponse]
    total: int