# app/api/admin_deps.py
"""
Admin-only dependencies.
"""
from fastapi import Depends, HTTPException, status

from .deps import get_current_user
from ..models.user import User


def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """
    Verify current user is admin.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        User: Admin user
        
    Raises:
        HTTPException: If user is not admin
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user