"""
Orders API endpoints.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..database import get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..models.order import Order, OrderStatus
from ..models.market import Market
from ..models.outcome import Outcome
from ..schemas.order import (
    OrderCreate, 
    OrderResponse, 
    OrderListResponse,
    MatchOrderRequest,
    ContractResponse
)
from ..services.escrow import EscrowService, InsufficientFundsError
from ..services.matching import (
    MatchingService,
    MatchingError,
    OrderNotAvailableError
)

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new order (Maker provides liquidity)
    
    Flow:
    1. Verify market and outcome exist
    2. Check user balance
    3. Lock funds (available -> locked)
    4. Create Order with status=OPEN
    5. Record Transaction
    """
    
    # Verify market exists and is open
    market = db.query(Market).filter(Market.id == order_data.market_id).first()
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    
    if market.status != "OPEN":
        raise HTTPException(status_code=400, detail="Market is not open for betting")
    
    # Verify outcome belongs to this market
    outcome = db.query(Outcome).filter(
        and_(
            Outcome.id == order_data.outcome_id,
            Outcome.market_id == order_data.market_id
        )
    ).first()
    
    if not outcome:
        raise HTTPException(status_code=404, detail="Outcome not found in this market")
    
    # Lock funds and create order
    try:
        # Create order (need ID for transaction)
        order = Order(
            user_id=current_user.id,
            market_id=order_data.market_id,
            outcome_id=order_data.outcome_id,
            amount=order_data.amount,
            unfilled_amount=order_data.amount,  # Initially all unfilled
            odds=order_data.odds,
            status=OrderStatus.OPEN
        )
        db.add(order)
        db.flush()  # Get order.id without commit
        
        # Lock funds via EscrowService
        EscrowService.lock_funds(
            db=db,
            user=current_user,
            amount=order_data.amount,
            description=f"Order #{order.id} created: {outcome.name} @ {order_data.odds}",
            order_id=order.id
        )
        
        db.commit()
        db.refresh(order)
        
        return order
    
    except InsufficientFundsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create order: {str(e)}")


@router.get("", response_model=OrderListResponse)
def list_orders(
    market_id: Optional[int] = None,
    outcome_id: Optional[int] = None,
    status: Optional[str] = None,
    my_orders: bool = True,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of orders with optional filters
    
    Filters:
    - market_id: Orders for specific market
    - outcome_id: Orders for specific outcome
    - status: OPEN, PARTIALLY_FILLED, FILLED, CANCELLED
    """
    
    query = db.query(Order)
    
    # Apply filters
    if my_orders:
        query = query.filter(Order.user_id == current_user.id)
    if market_id:
        query = query.filter(Order.market_id == market_id)
    if outcome_id:
        query = query.filter(Order.outcome_id == outcome_id)
    if status:
        query = query.filter(Order.status == status)
    
    total = query.count()
    orders = query.offset(skip).limit(limit).all()
    
    return OrderListResponse(orders=orders, total=total)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get details of a specific order"""
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    return order


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel an order (only own orders, only OPEN/PARTIALLY_FILLED)
    
    Flow:
    1. Verify order belongs to user
    2. Check status (can only cancel OPEN/PARTIALLY_FILLED)
    3. Unlock unfilled_amount
    4. Change status to CANCELLED
    """
    
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    # Verify ownership
    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only cancel your own orders")
    
    # Check status
    if order.status not in [OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel order with status {order.status}"
        )
    
    try:
        # Unlock unfilled amount
        if order.unfilled_amount > 0:
            EscrowService.unlock_funds(
                db=db,
                user=current_user,
                amount=order.unfilled_amount,
                description=f"Order #{order.id} cancelled",
                order_id=order.id
            )
        
        # Update status
        order.status = OrderStatus.CANCELLED
        
        db.commit()
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to cancel order: {str(e)}")


@router.post("/{order_id}/match", response_model=ContractResponse, status_code=status.HTTP_201_CREATED)
def match_order(
    order_id: int,
    match_data: MatchOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Match an order (Taker takes liquidity from Maker)
    
    Flow:
    1. Lock order with SELECT FOR UPDATE
    2. Validate order is available
    3. Calculate taker risk
    4. Lock taker funds
    5. Create contract
    6. Update order unfilled_amount and status
    
    Example:
        Order: Maker stakes $100 @ 1.8 odds on "NaVi"
        Taker: wants to take $50
        Taker risk: 50 * (1.8 - 1) = $40
        Contract: maker_amount=$50, taker_risk=$40, odds=1.8
        Order: unfilled_amount: 100 -> 50, status: OPEN -> PARTIALLY_FILLED
    """
    
    try:
        contract = MatchingService.match_order(
            db=db,
            order_id=order_id,
            taker=current_user,
            amount=match_data.amount
        )
        
        db.commit()
        db.refresh(contract)
        
        return contract
    
    except OrderNotAvailableError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
    except InsufficientFundsError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
    except MatchingError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to match order: {str(e)}")