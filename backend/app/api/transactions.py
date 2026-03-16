"""
Transactions API endpoints.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..models.transaction import Transaction
from ..schemas.transaction import TransactionListResponse


router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("/my", response_model=TransactionListResponse)
def get_my_transactions(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get current user's transactions ordered by newest first."""
    query = db.query(Transaction).filter(Transaction.user_id == current_user.id)

    total = query.count()
    transactions = (
        query.order_by(Transaction.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return TransactionListResponse(
        transactions=transactions,
        total=total,
        page=page,
        page_size=page_size,
    )
