# app/schemas/event.py
"""
Event schemas for API requests and responses.
"""
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional


class EventCreate(BaseModel):
    """Schema for creating a new event (admin-only)"""
    game_type: str  # CS2, Dota2, LoL, etc
    team_a: str
    team_b: str
    tournament: Optional[str] = None
    scheduled_start: Optional[datetime] = None
    external_match_id: Optional[str] = None  # For API integration


class EventUpdate(BaseModel):
    """Schema for updating an event (admin-only)"""
    status: Optional[str] = None  # SCHEDULED, OPEN, LIVE, FINISHED, SETTLED
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    external_match_id: Optional[str] = None


class EventResponse(BaseModel):
    """Schema for event API response"""
    id: int
    game_type: str
    team_a: str
    team_b: str
    tournament: Optional[str] = None
    status: str  # SCHEDULED, OPEN, LIVE, FINISHED, SETTLED
    scheduled_start: Optional[datetime] = None
    actual_start: Optional[datetime] = None
    actual_end: Optional[datetime] = None
    external_match_id: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class EventListResponse(BaseModel):
    """Schema for paginated event list"""
    events: list[EventResponse]
    total: int