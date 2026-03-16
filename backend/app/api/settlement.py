# app/api/settlement.py
"""
Settlement API endpoints for Optimistic Oracle.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from sqlalchemy import or_

from ..api.admin_deps import get_admin_user
from ..database import get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..models.contract import Contract, ContractStatus
from ..models.market import Market, MarketStatus
from ..schemas.settlement import (
    ClaimRequest,
    ClaimResponse,
    DisputeRequest,
    DisputeResponse,
    SettlementResponse,
    ContractDetailResponse,
    MyContractsResponse
)
from ..services.settlement import (
    SettlementService,
    ClaimException,
    DisputeException,
    SettlementException
)

router = APIRouter(prefix="/api/settlement", tags=["settlement"])


@router.post("/contracts/{contract_id}/claim", response_model=ClaimResponse)
def claim_contract_result(
    contract_id: int,
    claim_data: ClaimRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Claim result for a contract (Optimistic Oracle).
    
    Initiates 15-minute challenge period. If no dispute is raised,
    contract will auto-settle after deadline.
    
    Flow:
    1. User claims winning outcome
    2. 15-minute timer starts
    3. Other participant can dispute
    4. If no dispute → auto-settle
    
    Only contract participants (Maker or Taker) can claim.
    """
    # Get contract
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify market is settled first
    market = db.query(Market).filter(Market.id == contract.market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    if market.status != MarketStatus.SETTLED:
        raise HTTPException(
            status_code=400,
            detail="Cannot claim contract until market is settled"
        )
    
    try:
        # Claim result
        updated_contract = SettlementService.claim_result(
            db=db,
            contract=contract,
            claiming_user=current_user,
            winning_outcome_id=claim_data.winning_outcome_id
        )
        
        return ClaimResponse(
            contract_id=updated_contract.id,
            claim_initiated_by=updated_contract.claim_initiated_by,
            claim_initiated_at=updated_contract.claim_initiated_at,
            challenge_deadline=updated_contract.challenge_deadline,
            winning_outcome_id=claim_data.winning_outcome_id,
            status=updated_contract.status
        )
    
    except ClaimException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to claim contract: {str(e)}"
        )


@router.post("/contracts/{contract_id}/dispute", response_model=DisputeResponse)
def dispute_contract_claim(
    contract_id: int,
    dispute_data: DisputeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Dispute a claimed contract result.
    
    Must be called within 15-minute challenge period.
    Moves contract to DISPUTED status for admin resolution.
    
    Only the OTHER participant (not the claimer) can dispute.
    """
    # Get contract
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    try:
        # Dispute claim
        updated_contract = SettlementService.dispute_claim(
            db=db,
            contract=contract,
            disputing_user=current_user,
            reason=dispute_data.reason
        )
        
        return DisputeResponse(
            contract_id=updated_contract.id,
            status=updated_contract.status,
            disputed_by=current_user.id,
            disputed_at=updated_contract.claim_initiated_at  # Using this temporarily
        )
    
    except DisputeException as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to dispute claim: {str(e)}"
        )


@router.post("/contracts/{contract_id}/settle", response_model=SettlementResponse)
def manual_settle_contract(
    contract_id: int,
    winning_outcome_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Manually settle a contract (admin-only or after auto-settle).
    
    Used for:
    - Admin resolving disputes
    - Testing/debugging
    - Manual settlement after oracle confirmation
    
    TODO: Add admin-only check in production
    """
    # TODO: Add admin check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    # Get contract
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    try:
        # Settle contract
        settled_contract = SettlementService.settle_contract(
            db=db,
            contract=contract,
            winning_outcome_id=winning_outcome_id
        )
        
        # Get participants for response
        maker = db.query(User).filter(User.id == settled_contract.maker_id).first()
        taker = db.query(User).filter(User.id == settled_contract.taker_id).first()
        
        # Calculate amounts for response
        maker_stake = settled_contract.amount
        taker_risk = SettlementService.calculate_taker_risk(
            maker_stake,
            settled_contract.odds
        )
        pool = maker_stake + taker_risk
        
        # Determine profit and fee
        if settled_contract.outcome_id == winning_outcome_id:
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
            detail=f"Failed to settle contract: {str(e)}"
        )


@router.get("/contracts/my", response_model=MyContractsResponse)
def get_my_contracts(
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all contracts where current user is maker or taker.

    Optional filter:
    - status: ACTIVE | CLAIMED | SETTLED | DISPUTED
    """
    query = db.query(Contract).filter(
        or_(
            Contract.maker_id == current_user.id,
            Contract.taker_id == current_user.id,
        )
    )

    if status:
        normalized_status = status.upper()
        valid_statuses = {contract_status.value for contract_status in ContractStatus}
        if normalized_status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status filter. Allowed: {', '.join(sorted(valid_statuses))}",
            )
        query = query.filter(Contract.status == ContractStatus(normalized_status))

    contracts = query.order_by(Contract.created_at.desc()).all()

    return MyContractsResponse(contracts=contracts, total=len(contracts))


@router.get("/contracts/{contract_id}", response_model=ContractDetailResponse)
def get_contract_details(
    contract_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed contract information including settlement data.
    
    Shows:
    - Contract details
    - Claim status and deadline
    - Dispute information
    - Settlement result
    """
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    # Verify user is participant
    if current_user.id not in [contract.maker_id, contract.taker_id]:
        raise HTTPException(
            status_code=403,
            detail="You can only view your own contracts"
        )
    
    return contract


@router.get("/contracts/pending-claims", response_model=list[ContractDetailResponse])
def get_pending_claims(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_admin_user)
):
    """
    Get contracts with pending claims (for testing/monitoring).
    
    Shows contracts in CLAIMED status that are ready for auto-settlement.
    
    TODO: Make admin-only in production
    """
    contracts = SettlementService.get_pending_claims(db)
    return contracts