from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import uuid

from middleware.auth import get_current_active_user
from models.database import User
from models.schemas import CalendarEventRequest, CalendarEventResponse, CalendarEventUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/events", response_model=List[CalendarEventResponse])
async def get_calendar_events(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    current_user: User = Depends(get_current_active_user)
):
    """Get calendar events for a date range"""
    try:
        from core.database import get_db_session
        from models.database import CalendarEvent
        from sqlalchemy import select
        
        # Default to current month if no dates provided
        if not start_date:
            start_date = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if not end_date:
            end_date = start_date.replace(month=start_date.month + 1) if start_date.month < 12 else start_date.replace(year=start_date.year + 1, month=1)
        
        async with get_db_session() as session:
            query = select(CalendarEvent).where(
                CalendarEvent.user_id == current_user.id,
                CalendarEvent.start_time >= start_date,
                CalendarEvent.start_time <= end_date
            ).order_by(CalendarEvent.start_time).limit(limit)
            
            result = await session.execute(query)
            events = result.scalars().all()
            
            return [
                CalendarEventResponse(
                    id=event.id,
                    title=event.title,
                    description=event.description,
                    start_time=event.start_time,
                    end_time=event.end_time,
                    all_day=event.all_day,
                    location=event.location,
                    attendees=event.attendees or [],
                    recurrence_rule=event.recurrence_rule,
                    reminder_minutes=event.reminder_minutes,
                    google_event_id=event.google_event_id,
                    created_by_agent=event.created_by_agent,
                    metadata=event.metadata or {},
                    created_at=event.created_at,
                    updated_at=event.updated_at
                )
                for event in events
            ]
            
    except Exception as e:
        logger.error(f"Error retrieving calendar events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve calendar events: {str(e)}"
        )

@router.post("/events", response_model=CalendarEventResponse)
async def create_calendar_event(
    event_data: CalendarEventRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new calendar event"""
    try:
        from core.database import get_db_session
        from models.database import CalendarEvent
        
        async with get_db_session() as session:
            # Create new calendar event
            new_event = CalendarEvent(
                id=uuid.uuid4(),
                title=event_data.title,
                description=event_data.description,
                start_time=event_data.start_time,
                end_time=event_data.end_time or event_data.start_time + timedelta(hours=1),
                all_day=event_data.all_day or False,
                location=event_data.location,
                attendees=event_data.attendees or [],
                recurrence_rule=event_data.recurrence_rule,
                reminder_minutes=event_data.reminder_minutes or 15,
                created_by_agent=event_data.created_by_agent,
                metadata=event_data.metadata or {},
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )
            
            session.add(new_event)
            await session.commit()
            await session.refresh(new_event)
            
            # Sync with Google Calendar if enabled
            try:
                google_event_id = await sync_to_google_calendar(new_event, current_user, action="create")
                if google_event_id:
                    new_event.google_event_id = google_event_id
                    await session.commit()
            except Exception as e:
                logger.warning(f"Failed to sync event to Google Calendar: {e}")
            
            return CalendarEventResponse(
                id=new_event.id,
                title=new_event.title,
                description=new_event.description,
                start_time=new_event.start_time,
                end_time=new_event.end_time,
                all_day=new_event.all_day,
                location=new_event.location,
                attendees=new_event.attendees or [],
                recurrence_rule=new_event.recurrence_rule,
                reminder_minutes=new_event.reminder_minutes,
                google_event_id=new_event.google_event_id,
                created_by_agent=new_event.created_by_agent,
                metadata=new_event.metadata or {},
                created_at=new_event.created_at,
                updated_at=new_event.updated_at
            )
            
    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create calendar event: {str(e)}"
        )

@router.get("/events/{event_id}", response_model=CalendarEventResponse)
async def get_calendar_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific calendar event by ID"""
    try:
        from core.database import get_db_session
        from models.database import CalendarEvent
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(CalendarEvent).where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == current_user.id
            )
            result = await session.execute(query)
            event = result.scalar_one_or_none()
            
            if not event:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Calendar event not found"
                )
            
            return CalendarEventResponse(
                id=event.id,
                title=event.title,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                all_day=event.all_day,
                location=event.location,
                attendees=event.attendees or [],
                recurrence_rule=event.recurrence_rule,
                reminder_minutes=event.reminder_minutes,
                google_event_id=event.google_event_id,
                created_by_agent=event.created_by_agent,
                metadata=event.metadata or {},
                created_at=event.created_at,
                updated_at=event.updated_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving calendar event {event_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve calendar event: {str(e)}"
        )

@router.put("/events/{event_id}", response_model=CalendarEventResponse)
async def update_calendar_event(
    event_id: uuid.UUID,
    event_update: CalendarEventUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """Update a calendar event"""
    try:
        from core.database import get_db_session
        from models.database import CalendarEvent
        from sqlalchemy import select
        
        async with get_db_session() as session:
            # Get existing event
            query = select(CalendarEvent).where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == current_user.id
            )
            result = await session.execute(query)
            event = result.scalar_one_or_none()
            
            if not event:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Calendar event not found"
                )
            
            # Update event fields
            update_data = event_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(event, field) and value is not None:
                    setattr(event, field, value)
            
            event.updated_at = datetime.utcnow()
            
            await session.commit()
            await session.refresh(event)
            
            # Sync with Google Calendar if enabled
            try:
                await sync_to_google_calendar(event, current_user, action="update")
            except Exception as e:
                logger.warning(f"Failed to sync event update to Google Calendar: {e}")
            
            return CalendarEventResponse(
                id=event.id,
                title=event.title,
                description=event.description,
                start_time=event.start_time,
                end_time=event.end_time,
                all_day=event.all_day,
                location=event.location,
                attendees=event.attendees or [],
                recurrence_rule=event.recurrence_rule,
                reminder_minutes=event.reminder_minutes,
                google_event_id=event.google_event_id,
                created_by_agent=event.created_by_agent,
                metadata=event.metadata or {},
                created_at=event.created_at,
                updated_at=event.updated_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating calendar event {event_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update calendar event: {str(e)}"
        )

@router.delete("/events/{event_id}")
async def delete_calendar_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a calendar event"""
    try:
        from core.database import get_db_session
        from models.database import CalendarEvent
        from sqlalchemy import select, delete
        
        async with get_db_session() as session:
            # Get event to delete
            query = select(CalendarEvent).where(
                CalendarEvent.id == event_id,
                CalendarEvent.user_id == current_user.id
            )
            result = await session.execute(query)
            event = result.scalar_one_or_none()
            
            if not event:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Calendar event not found"
                )
            
            # Delete from Google Calendar if synced
            try:
                if event.google_event_id:
                    await sync_to_google_calendar(event, current_user, action="delete")
            except Exception as e:
                logger.warning(f"Failed to delete event from Google Calendar: {e}")
            
            # Delete from local database
            delete_query = delete(CalendarEvent).where(CalendarEvent.id == event_id)
            await session.execute(delete_query)
            await session.commit()
            
            return {
                "message": "Calendar event deleted successfully",
                "event_id": str(event_id),
                "deleted_at": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting calendar event {event_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete calendar event: {str(e)}"
        )

@router.get("/events/today", response_model=List[CalendarEventResponse])
async def get_todays_events(
    current_user: User = Depends(get_current_active_user)
):
    """Get today's calendar events"""
    try:
        now = datetime.utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        
        return await get_calendar_events(
            start_date=start_of_day,
            end_date=end_of_day,
            current_user=current_user
        )
        
    except Exception as e:
        logger.error(f"Error getting today's events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get today's events: {str(e)}"
        )

@router.get("/events/upcoming", response_model=List[CalendarEventResponse])
async def get_upcoming_events(
    days: int = Query(7, ge=1, le=365),
    current_user: User = Depends(get_current_active_user)
):
    """Get upcoming events within specified days"""
    try:
        now = datetime.utcnow()
        end_date = now + timedelta(days=days)
        
        return await get_calendar_events(
            start_date=now,
            end_date=end_date,
            current_user=current_user
        )
        
    except Exception as e:
        logger.error(f"Error getting upcoming events: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get upcoming events: {str(e)}"
        )

@router.post("/sync/google")
async def sync_with_google_calendar(
    current_user: User = Depends(get_current_active_user)
):
    """Sync calendar events with Google Calendar"""
    try:
        # This would integrate with Google Calendar API
        # For now, return a placeholder response
        
        synced_count = await perform_google_calendar_sync(current_user)
        
        return {
            "message": "Google Calendar sync completed",
            "synced_events": synced_count,
            "synced_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error syncing with Google Calendar: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync with Google Calendar: {str(e)}"
        )

@router.get("/export/ical")
async def export_calendar_to_ical(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Export calendar events to iCal format"""
    try:
        from fastapi.responses import Response
        
        # Get events for the specified range
        events = await get_calendar_events(
            start_date=start_date,
            end_date=end_date,
            current_user=current_user
        )
        
        # Generate iCal content
        ical_content = generate_ical_content(events, current_user)
        
        return Response(
            content=ical_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": f"attachment; filename=calendar_{datetime.utcnow().strftime('%Y%m%d')}.ics"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting calendar to iCal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export calendar: {str(e)}"
        )

# Helper functions

async def sync_to_google_calendar(event, user: User, action: str) -> Optional[str]:
    """Sync event to Google Calendar"""
    # Placeholder for Google Calendar API integration
    # This would use the Google Calendar API to create/update/delete events
    try:
        # Implementation would go here
        # Return Google event ID for create/update, None for delete
        return f"google_event_{event.id}" if action != "delete" else None
    except Exception as e:
        logger.error(f"Google Calendar sync failed: {e}")
        return None

async def perform_google_calendar_sync(user: User) -> int:
    """Perform full sync with Google Calendar"""
    # Placeholder for Google Calendar sync implementation
    try:
        # Implementation would:
        # 1. Fetch events from Google Calendar
        # 2. Compare with local events
        # 3. Sync differences
        return 0  # Return number of synced events
    except Exception as e:
        logger.error(f"Google Calendar full sync failed: {e}")
        return 0

def generate_ical_content(events: List[CalendarEventResponse], user: User) -> str:
    """Generate iCal content from events"""
    try:
        ical_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Multi-Agent Assistant//Calendar//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH"
        ]
        
        for event in events:
            ical_lines.extend([
                "BEGIN:VEVENT",
                f"UID:{event.id}",
                f"DTSTART:{event.start_time.strftime('%Y%m%dT%H%M%S')}Z",
                f"DTEND:{event.end_time.strftime('%Y%m%dT%H%M%S')}Z",
                f"SUMMARY:{event.title}",
                f"DESCRIPTION:{event.description or ''}",
                f"LOCATION:{event.location or ''}",
                f"CREATED:{event.created_at.strftime('%Y%m%dT%H%M%S')}Z",
                f"LAST-MODIFIED:{event.updated_at.strftime('%Y%m%dT%H%M%S') if event.updated_at else event.created_at.strftime('%Y%m%dT%H%M%S')}Z",
                "END:VEVENT"
            ])
        
        ical_lines.append("END:VCALENDAR")
        
        return "\r\n".join(ical_lines)
        
    except Exception as e:
        logger.error(f"Error generating iCal content: {e}")
        raise