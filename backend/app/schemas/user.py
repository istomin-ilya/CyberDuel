"""
User schemas for request/response validation.
"""
from pydantic import BaseModel, EmailStr, Field
from decimal import Decimal
from datetime import datetime


class UserBase(BaseModel):
    """Base user schema."""
    email: EmailStr


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=8, max_length=100)


class UserLogin(UserBase):
    """Schema for user login."""
    password: str


class UserResponse(UserBase):
    """Schema for user in responses."""
    id: int
    balance_available: Decimal
    balance_locked: Decimal
    created_at: datetime
    
    class Config:
        from_attributes = True  # Allows creating from ORM models


class TokenResponse(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str