# app/api/markets.py
"""
Market API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..models.event import Event
from ..models.market import Market, MarketStatus
from ..models.outcome import Outcome
from ..schemas.market import (
    MarketCreate,
    MarketUpdate,
    MarketResponse,
    MarketListResponse
)

router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.post("", response_model=MarketResponse, status_code=status.HTTP_201_CREATED)
def create_market(
    market_data: MarketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new market with outcomes (admin-only)
    
    Creates a market for an event and its possible outcomes.
    Initial status is PENDING.
    """
    # TODO: Add admin check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    # Validate event exists
    event = db.query(Event).filter(Event.id == market_data.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Validate at least 2 outcomes
    if len(market_data.outcomes) < 2:
        raise HTTPException(
            status_code=400,
            detail="Market must have at least 2 outcomes"
        )
    
    # Create market
    market = Market(
        event_id=market_data.event_id,
        market_type=market_data.market_type,
        title=market_data.title,
        description=market_data.description,
        status=MarketStatus.PENDING
    )
    db.add(market)
    db.flush()  # Get market.id
    
    # Create outcomes
    for outcome_data in market_data.outcomes:
        outcome = Outcome(
            market_id=market.id,
            name=outcome_data.name,
            external_id=outcome_data.external_id
        )
        db.add(outcome)
    
    db.commit()
    db.refresh(market)
    
    return market


@router.get("", response_model=MarketListResponse)
def list_markets(
    event_id: Optional[int] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get list of markets (public)
    
    Filters:
    - event_id: Markets for specific event
    - status: PENDING, OPEN, LOCKED, SETTLED
    """
    
    query = db.query(Market)
    
    # Apply filters
    if event_id:
        query = query.filter(Market.event_id == event_id)
    if status:
        query = query.filter(Market.status == status)
    
    total = query.count()
    markets = query.offset(skip).limit(limit).all()
    
    return MarketListResponse(markets=markets, total=total)


@router.get("/{market_id}", response_model=MarketResponse)
def get_market(
    market_id: int,
    db: Session = Depends(get_db)
):
    """Get details of a specific market with outcomes (public)"""
    
    market = db.query(Market).filter(Market.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    return market


@router.patch("/{market_id}", response_model=MarketResponse)
def update_market(
    market_id: int,
    market_data: MarketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update market (admin-only)
    
    Used to progress market through lifecycle:
    PENDING → OPEN → LOCKED → SETTLED
    
    Also used to set winning_outcome_id after settlement.
    """
    # TODO: Add admin check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    market = db.query(Market).filter(Market.id == market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    # Update status
    if market_data.status is not None:
        # Validate status transition
        valid_statuses = ["PENDING", "OPEN", "LOCKED", "SETTLED"]
        if market_data.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {market_data.status}"
            )
        market.status = market_data.status
    
    # Update winning outcome (settlement)
    if market_data.winning_outcome_id is not None:
        # Validate outcome belongs to this market
        outcome = db.query(Outcome).filter(
            Outcome.id == market_data.winning_outcome_id,
            Outcome.market_id == market_id
        ).first()
        
        if not outcome:
            raise HTTPException(
                status_code=400,
                detail="Outcome does not belong to this market"
            )
        
        market.winning_outcome_id = market_data.winning_outcome_id
        market.status = MarketStatus.SETTLED
    
    db.commit()
    db.refresh(market)
    
    return market