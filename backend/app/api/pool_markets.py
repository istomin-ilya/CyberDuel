"""
Pool Market API endpoints.

Handles:
- Placing bets in pool markets
- Getting pool state (current odds, liquidity)
- Viewing user's pool bets
- Viewing all pool bets (admin/public)
"""
from decimal import Decimal
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.market import Market
from app.models.pool_bet import PoolBet
from app.api.deps import get_current_user
from app.schemas.pool_market import (
    PoolBetCreate,
    PoolBetResponse,
    PoolStateResponse,
    PoolBetListResponse,
    OutcomePoolState
)
from app.services.pool_market import PoolMarketService, PoolMarketException


router = APIRouter(prefix="/api/pool-markets", tags=["pool-markets"])


@router.post("/{market_id}/bet", response_model=PoolBetResponse, status_code=201)
def place_pool_bet(
    market_id: int,
    bet_data: PoolBetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Place a bet in a pool market.
    
    The odds are locked at the moment of bet placement.
    Early bettors get better odds (more risk).
    
    Args:
        market_id: Pool market ID
        bet_data: Bet details (outcome_id, amount)
        
    Returns:
        Created pool bet with locked odds
        
    Raises:
        400: Invalid bet (insufficient funds, market closed, etc)
        404: Market or outcome not found
    """
    try:
        pool_bet = PoolMarketService.place_pool_bet(
            db=db,
            user=current_user,
            market_id=market_id,
            outcome_id=bet_data.outcome_id,
            amount=bet_data.amount
        )
        return pool_bet
    except PoolMarketException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{market_id}/state", response_model=PoolStateResponse)
def get_pool_state(
    market_id: int,
    db: Session = Depends(get_db)
):
    """
    Get current pool state for a market.
    
    Shows:
    - Total liquidity in the pool
    - Per-outcome statistics (staked, participants, current odds)
    - Current odds update dynamically as bets are placed
    
    Args:
        market_id: Pool market ID
        
    Returns:
        Pool state with current odds for all outcomes
        
    Raises:
        404: Market not found
        400: Market is not a pool market
    """
    try:
        state_dict = PoolMarketService.get_pool_state(db, market_id)
        
        # Convert to schema format
        outcomes = [
            OutcomePoolState(
                outcome_id=o["outcome_id"],
                outcome_name=o["name"],
                total_staked=Decimal(o["total_staked"]),
                participant_count=o["participant_count"],
                estimated_odds=Decimal(o["estimated_odds"]),
                estimated_roi=Decimal(o["estimated_roi"])
            )
            for o in state_dict["outcomes"]
        ]
        
        return PoolStateResponse(
            market_id=state_dict["market_id"],
            total_pool=Decimal(state_dict["total_pool"]),
            outcomes=outcomes
        )
    except PoolMarketException as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{market_id}/my-bets", response_model=PoolBetListResponse)
def get_my_pool_bets(
    market_id: int,
    settled: Optional[bool] = Query(None, description="Filter by settlement status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get current user's pool bets for a market.
    
    Args:
        market_id: Pool market ID
        settled: Optional filter by settlement status
        page: Page number (default: 1)
        page_size: Items per page (default: 20, max: 100)
        
    Returns:
        Paginated list of user's pool bets
    """
    # Get user's bets
    bets = PoolMarketService.get_user_pool_bets(
        db=db,
        user_id=current_user.id,
        market_id=market_id,
        settled=settled
    )
    
    # Pagination
    total = len(bets)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    paginated_bets = bets[start_idx:end_idx]
    
    return PoolBetListResponse(
        bets=paginated_bets,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get("/{market_id}/all-bets", response_model=PoolBetListResponse)
def get_all_pool_bets(
    market_id: int,
    settled: Optional[bool] = Query(None, description="Filter by settlement status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db)
):
    """
    Get all pool bets for a market (public view).
    
    Useful for:
    - Viewing market activity
    - Analyzing betting patterns
    - Transparency
    
    Args:
        market_id: Pool market ID
        settled: Optional filter by settlement status
        page: Page number (default: 1)
        page_size: Items per page (default: 20, max: 100)
        
    Returns:
        Paginated list of all pool bets
    """
    # Get all bets for this market
    query = db.query(PoolBet).filter(PoolBet.market_id == market_id)
    
    if settled is not None:
        query = query.filter(PoolBet.settled == settled)
    
    # Count total
    total = query.count()
    
    # Pagination
    bets = query.order_by(PoolBet.created_at.desc()) \
                 .offset((page - 1) * page_size) \
                 .limit(page_size) \
                 .all()
    
    return PoolBetListResponse(
        bets=bets,
        total=total,
        page=page,
        page_size=page_size
    )