# app/api/admin.py
"""
Admin endpoints for dispute resolution and management.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..api.admin_deps import get_admin_user
from ..models.user import User
from ..models.contract import Contract, ContractStatus
from ..models.market import Market
from ..schemas.settlement import (
    AdminResolveDisputeRequest,
    SettlementResponse,
    DisputeListResponse,
    ContractDetailResponse
)
from ..services.settlement import SettlementService, SettlementException

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/disputes", response_model=DisputeListResponse)
def list_disputed_contracts(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    List all disputed contracts requiring admin resolution.
    
    Admin-only endpoint.
    Returns contracts in DISPUTED status.
    """
    # Get all disputed contracts
    query = db.query(Contract).filter(
        Contract.status == ContractStatus.DISPUTED
    ).order_by(Contract.claim_initiated_at.desc())
    
    total = query.count()
    contracts = query.offset(skip).limit(limit).all()
    
    return DisputeListResponse(
        contracts=contracts,
        total=total
    )


@router.post("/disputes/{contract_id}/resolve", response_model=SettlementResponse)
def resolve_dispute(
    contract_id: int,
    resolution_data: AdminResolveDisputeRequest,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Manually resolve a disputed contract (admin-only).
    
    Admin reviews the dispute and determines the correct winning outcome.
    Contract is then settled based on admin's decision.
    
    Flow:
    1. Admin reviews dispute details
    2. Admin determines correct winning outcome
    3. System settles contract with admin's decision
    4. Funds distributed accordingly
    
    Args:
        contract_id: ID of disputed contract
        resolution_data: Admin's resolution decision
        
    Returns:
        SettlementResponse: Settlement details
    """
    # Get contract
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify contract is disputed
    if contract.status != ContractStatus.DISPUTED:
        raise HTTPException(
            status_code=400,
            detail=f"Contract is not disputed (status: {contract.status})"
        )
    
    # Get market to verify outcome
    market = db.query(Market).filter(Market.id == contract.market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    try:
        # Settle contract with admin's decision
        settled_contract = SettlementService.settle_contract(
            db=db,
            contract=contract,
            winning_outcome_id=resolution_data.winning_outcome_id
        )
        
        # Calculate response data
        maker_stake = settled_contract.amount
        taker_risk = SettlementService.calculate_taker_risk(
            maker_stake,
            settled_contract.odds
        )
        pool = maker_stake + taker_risk
        
        # Determine profit and fee
        if settled_contract.outcome_id == resolution_data.winning_outcome_id:
            profit = taker_risk
        else:
            profit = maker_stake
        
        fee = profit * SettlementService.FEE_RATE
        
        # Determine winner/loser
        winner_id = settled_contract.winner_id
        loser_id = (
            settled_contract.taker_id 
            if winner_id == settled_contract.maker_id 
            else settled_contract.maker_id
        )
        
        winner_stake = maker_stake if winner_id == settled_contract.maker_id else taker_risk
        payout = winner_stake + profit - fee
        
        return SettlementResponse(
            contract_id=settled_contract.id,
            winner_id=winner_id,
            loser_id=loser_id,
            pool=pool,
            profit=profit,
            fee=fee,
            payout=payout,
            status=settled_contract.status,
            settled_at=settled_contract.settled_at
        )
    
    except SettlementException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to resolve dispute: {str(e)}"
        )


@router.get("/contracts/{contract_id}", response_model=ContractDetailResponse)
def get_contract_for_admin(
    contract_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Get detailed contract information (admin view).
    
    Admin can view any contract, not just their own.
    Useful for reviewing disputes.
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    return contract


@router.post("/users/{user_id}/make-admin")
def make_user_admin(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Grant admin privileges to a user.
    
    Admin-only endpoint.
    Useful for promoting users to admin role.
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if user.is_admin:
        raise HTTPException(status_code=400, detail="User is already admin")
    
    user.is_admin = True
    db.commit()
    
    return {"message": f"User {user.email} is now an admin"}


@router.delete("/users/{user_id}/remove-admin")
def remove_admin_privileges(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(get_admin_user)
):
    """
    Remove admin privileges from a user.
    
    Admin-only endpoint.
    Cannot remove admin from yourself.
    """
    if user_id == admin_user.id:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove admin privileges from yourself"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    if not user.is_admin:
        raise HTTPException(status_code=400, detail="User is not an admin")
    
    user.is_admin = False
    db.commit()
    
    return {"message": f"Admin privileges removed from {user.email}"}