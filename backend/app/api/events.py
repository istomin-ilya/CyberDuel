# app/api/events.py
"""
Event API endpoints.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..api.deps import get_current_user
from ..models.user import User
from ..models.event import Event, EventStatus
from ..schemas.event import EventCreate, EventUpdate, EventResponse, EventListResponse

router = APIRouter(prefix="/api/events", tags=["events"])


@router.post("", response_model=EventResponse, status_code=status.HTTP_201_CREATED)
def create_event(
    event_data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new event (admin-only)
    
    Admin creates events for upcoming matches.
    Initial status is SCHEDULED.
    """
    # TODO: Add admin check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    event = Event(
        game_type=event_data.game_type,
        team_a=event_data.team_a,
        team_b=event_data.team_b,
        tournament=event_data.tournament,
        scheduled_start=event_data.scheduled_start,
        external_match_id=event_data.external_match_id,
        status=EventStatus.SCHEDULED
    )
    
    db.add(event)
    db.commit()
    db.refresh(event)
    
    return event


@router.get("", response_model=EventListResponse)
def list_events(
    status: Optional[str] = None,
    game_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """
    Get list of events (public)
    
    Filters:
    - status: SCHEDULED, OPEN, LIVE, FINISHED, SETTLED
    - game_type: CS2, Dota2, LoL, etc
    """
    
    query = db.query(Event)
    
    # Apply filters
    if status:
        query = query.filter(Event.status == status)
    if game_type:
        query = query.filter(Event.game_type == game_type)
    
    # Order by scheduled_start (upcoming first)
    query = query.order_by(Event.scheduled_start.desc())
    
    total = query.count()
    events = query.offset(skip).limit(limit).all()
    
    return EventListResponse(events=events, total=total)


@router.get("/{event_id}", response_model=EventResponse)
def get_event(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get details of a specific event (public)"""
    
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    return event


@router.patch("/{event_id}", response_model=EventResponse)
def update_event(
    event_id: int,
    event_data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update event (admin-only)
    
    Used to progress event through lifecycle:
    SCHEDULED → OPEN → LIVE → FINISHED → SETTLED
    """
    # TODO: Add admin check
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin access required")
    
    event = db.query(Event).filter(Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Update fields
    if event_data.status is not None:
        # Validate status transition
        valid_statuses = ["SCHEDULED", "OPEN", "LIVE", "FINISHED", "SETTLED"]
        if event_data.status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Invalid status: {event_data.status}")
        event.status = event_data.status
    
    if event_data.actual_start is not None:
        event.actual_start = event_data.actual_start
    
    if event_data.actual_end is not None:
        event.actual_end = event_data.actual_end
    
    if event_data.external_match_id is not None:
        event.external_match_id = event_data.external_match_id
    
    db.commit()
    db.refresh(event)
    
    return event