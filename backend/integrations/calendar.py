import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.config import settings

logger = logging.getLogger(__name__)

class GoogleCalendarIntegration:
    """Google Calendar API integration"""
    
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]
        self.service = None
        
    async def initialize_oauth_flow(self, redirect_uri: str) -> str:
        """Initialize OAuth2 flow and return authorization URL"""
        try:
            flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": settings.GCAL_CLIENT_ID,
                        "client_secret": settings.GCAL_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            
            flow.redirect_uri = redirect_uri
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            
            return authorization_url
            
        except Exception as e:
            logger.error(f"Error initializing Google Calendar OAuth flow: {e}")
            raise
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        try:
            flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": settings.GCAL_CLIENT_ID,
                        "client_secret": settings.GCAL_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            
            flow.redirect_uri = redirect_uri
            flow.fetch_token(code=code)
            
            credentials = flow.credentials
            
            return {
                "access_token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None
            }
            
        except Exception as e:
            logger.error(f"Error exchanging code for tokens: {e}")
            raise
    
    async def initialize_service(self, credentials_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Initialize Google Calendar service with credentials"""
        try:
            credentials = Credentials.from_authorized_user_info(credentials_dict)
            
            # Refresh credentials if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                
                # Return updated credentials
                updated_creds = {
                    "access_token": credentials.token,
                    "refresh_token": credentials.refresh_token,
                    "token_uri": credentials.token_uri,
                    "client_id": credentials.client_id,
                    "client_secret": credentials.client_secret,
                    "scopes": credentials.scopes,
                    "expiry": credentials.expiry.isoformat() if credentials.expiry else None
                }
                
                self.service = build('calendar', 'v3', credentials=credentials)
                return updated_creds
            
            self.service = build('calendar', 'v3', credentials=credentials)
            return credentials_dict
            
        except Exception as e:
            logger.error(f"Error initializing Google Calendar service: {e}")
            raise
    
    async def list_calendars(self) -> List[Dict[str, Any]]:
        """List all calendars"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            calendars_result = self.service.calendarList().list().execute()
            calendars = calendars_result.get('items', [])
            
            return [
                {
                    "id": calendar['id'],
                    "summary": calendar.get('summary', ''),
                    "description": calendar.get('description', ''),
                    "location": calendar.get('location', ''),
                    "time_zone": calendar.get('timeZone', ''),
                    "access_role": calendar.get('accessRole', ''),
                    "primary": calendar.get('primary', False),
                    "selected": calendar.get('selected', False),
                    "background_color": calendar.get('backgroundColor', ''),
                    "foreground_color": calendar.get('foregroundColor', '')
                }
                for calendar in calendars
            ]
            
        except HttpError as e:
            logger.error(f"Google Calendar API error listing calendars: {e}")
            raise
        except Exception as e:
            logger.error(f"Error listing Google calendars: {e}")
            raise
    
    async def get_events(
        self,
        calendar_id: str = 'primary',
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 250,
        single_events: bool = True,
        order_by: str = 'startTime'
    ) -> List[Dict[str, Any]]:
        """Get events from a calendar"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            # Default to current time if no time_min specified
            if not time_min:
                time_min = datetime.utcnow()
            
            # Format times for API
            time_min_str = time_min.isoformat() + 'Z'
            time_max_str = time_max.isoformat() + 'Z' if time_max else None
            
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=single_events,
                orderBy=order_by
            ).execute()
            
            events = events_result.get('items', [])
            
            return [await self._format_event(event) for event in events]
            
        except HttpError as e:
            logger.error(f"Google Calendar API error getting events: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting Google Calendar events: {e}")
            raise
    
    async def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        calendar_id: str = 'primary',
        all_day: bool = False,
        recurrence: Optional[List[str]] = None,
        reminders: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Create a new calendar event"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            # Format start and end times
            if all_day:
                start_formatted = {
                    'date': start_time.strftime('%Y-%m-%d')
                }
                end_formatted = {
                    'date': end_time.strftime('%Y-%m-%d')
                }
            else:
                start_formatted = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(start_time.tzinfo) if start_time.tzinfo else 'UTC'
                }
                end_formatted = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(end_time.tzinfo) if end_time.tzinfo else 'UTC'
                }
            
            # Build event object
            event = {
                'summary': title,
                'start': start_formatted,
                'end': end_formatted
            }
            
            if description:
                event['description'] = description
            
            if location:
                event['location'] = location
            
            if attendees:
                event['attendees'] = [{'email': email} for email in attendees]
            
            if recurrence:
                event['recurrence'] = recurrence
            
            # Set reminders
            if reminders:
                event['reminders'] = {
                    'useDefault': False,
                    'overrides': reminders
                }
            else:
                event['reminders'] = {
                    'useDefault': True
                }
            
            # Create the event
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            return await self._format_event(created_event)
            
        except HttpError as e:
            logger.error(f"Google Calendar API error creating event: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating Google Calendar event: {e}")
            raise
    
    async def update_event(
        self,
        event_id: str,
        calendar_id: str = 'primary',
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Update an existing calendar event"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            # Get existing event
            existing_event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update fields
            if title is not None:
                existing_event['summary'] = title
            
            if description is not None:
                existing_event['description'] = description
            
            if location is not None:
                existing_event['location'] = location
            
            if attendees is not None:
                existing_event['attendees'] = [{'email': email} for email in attendees]
            
            if start_time is not None:
                existing_event['start'] = {
                    'dateTime': start_time.isoformat(),
                    'timeZone': str(start_time.tzinfo) if start_time.tzinfo else 'UTC'
                }
            
            if end_time is not None:
                existing_event['end'] = {
                    'dateTime': end_time.isoformat(),
                    'timeZone': str(end_time.tzinfo) if end_time.tzinfo else 'UTC'
                }
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=existing_event
            ).execute()
            
            return await self._format_event(updated_event)
            
        except HttpError as e:
            logger.error(f"Google Calendar API error updating event: {e}")
            raise
        except Exception as e:
            logger.error(f"Error updating Google Calendar event: {e}")
            raise
    
    async def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """Delete a calendar event"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return True
            
        except HttpError as e:
            if e.resp.status == 404:
                logger.warning(f"Event {event_id} not found for deletion")
                return False
            logger.error(f"Google Calendar API error deleting event: {e}")
            raise
        except Exception as e:
            logger.error(f"Error deleting Google Calendar event: {e}")
            raise
    
    async def get_event(self, event_id: str, calendar_id: str = 'primary') -> Dict[str, Any]:
        """Get a specific event"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            return await self._format_event(event)
            
        except HttpError as e:
            logger.error(f"Google Calendar API error getting event: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting Google Calendar event: {e}")
            raise
    
    async def search_events(
        self,
        query: str,
        calendar_id: str = 'primary',
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Search for events"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            # Default to current time if no time_min specified
            if not time_min:
                time_min = datetime.utcnow()
            
            # Format times for API
            time_min_str = time_min.isoformat() + 'Z'
            time_max_str = time_max.isoformat() + 'Z' if time_max else None
            
            events_result = self.service.events().list(
                calendarId=calendar_id,
                q=query,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            return [await self._format_event(event) for event in events]
            
        except HttpError as e:
            logger.error(f"Google Calendar API error searching events: {e}")
            raise
        except Exception as e:
            logger.error(f"Error searching Google Calendar events: {e}")
            raise
    
    async def get_free_busy(
        self,
        calendar_ids: List[str],
        time_min: datetime,
        time_max: datetime
    ) -> Dict[str, Any]:
        """Get free/busy information for calendars"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            body = {
                'timeMin': time_min.isoformat() + 'Z',
                'timeMax': time_max.isoformat() + 'Z',
                'items': [{'id': calendar_id} for calendar_id in calendar_ids]
            }
            
            freebusy_result = self.service.freebusy().query(body=body).execute()
            
            return freebusy_result
            
        except HttpError as e:
            logger.error(f"Google Calendar API error getting free/busy: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting Google Calendar free/busy: {e}")
            raise
    
    async def create_quick_event(self, text: str, calendar_id: str = 'primary') -> Dict[str, Any]:
        """Create an event using quick add (natural language)"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            event = self.service.events().quickAdd(
                calendarId=calendar_id,
                text=text
            ).execute()
            
            return await self._format_event(event)
            
        except HttpError as e:
            logger.error(f"Google Calendar API error creating quick event: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating Google Calendar quick event: {e}")
            raise
    
    async def _format_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Format Google Calendar event for consistent output"""
        try:
            # Parse start and end times
            start = event.get('start', {})
            end = event.get('end', {})
            
            # Handle all-day events vs timed events
            all_day = 'date' in start
            
            if all_day:
                start_time = datetime.fromisoformat(start['date']).replace(tzinfo=timezone.utc)
                end_time = datetime.fromisoformat(end['date']).replace(tzinfo=timezone.utc)
            else:
                start_time = datetime.fromisoformat(start['dateTime'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end['dateTime'].replace('Z', '+00:00'))
            
            # Extract attendees
            attendees = []
            for attendee in event.get('attendees', []):
                attendees.append({
                    'email': attendee.get('email', ''),
                    'display_name': attendee.get('displayName', ''),
                    'response_status': attendee.get('responseStatus', 'needsAction'),
                    'organizer': attendee.get('organizer', False)
                })
            
            # Extract reminders
            reminders = []
            reminder_data = event.get('reminders', {})
            if not reminder_data.get('useDefault', True):
                for override in reminder_data.get('overrides', []):
                    reminders.append({
                        'method': override.get('method', 'email'),
                        'minutes': override.get('minutes', 10)
                    })
            
            return {
                'id': event.get('id'),
                'title': event.get('summary', ''),
                'description': event.get('description', ''),
                'location': event.get('location', ''),
                'start_time': start_time,
                'end_time': end_time,
                'all_day': all_day,
                'attendees': attendees,
                'reminders': reminders,
                'html_link': event.get('htmlLink', ''),
                'status': event.get('status', 'confirmed'),
                'visibility': event.get('visibility', 'default'),
                'recurrence': event.get('recurrence', []),
                'created': datetime.fromisoformat(event['created'].replace('Z', '+00:00')) if 'created' in event else None,
                'updated': datetime.fromisoformat(event['updated'].replace('Z', '+00:00')) if 'updated' in event else None,
                'creator_email': event.get('creator', {}).get('email', ''),
                'organizer_email': event.get('organizer', {}).get('email', ''),
                'google_event_id': event.get('id'),
                'calendar_id': event.get('organizer', {}).get('email', 'primary')
            }
            
        except Exception as e:
            logger.error(f"Error formatting Google Calendar event: {e}")
            # Return minimal event data if formatting fails
            return {
                'id': event.get('id'),
                'title': event.get('summary', 'Untitled Event'),
                'start_time': datetime.utcnow(),
                'end_time': datetime.utcnow(),
                'all_day': False,
                'google_event_id': event.get('id')
            }
    
    async def create_calendar(
        self,
        summary: str,
        description: Optional[str] = None,
        location: Optional[str] = None,
        time_zone: str = 'UTC'
    ) -> Dict[str, Any]:
        """Create a new calendar"""
        try:
            if not self.service:
                raise ValueError("Google Calendar service not initialized")
            
            calendar_data = {
                'summary': summary,
                'timeZone': time_zone
            }
            
            if description:
                calendar_data['description'] = description
            
            if location:
                calendar_data['location'] = location
            
            created_calendar = self.service.calendars().insert(body=calendar_data).execute()
            
            return {
                'id': created_calendar['id'],
                'summary': created_calendar['summary'],
                'description': created_calendar.get('description', ''),
                'location': created_calendar.get('location', ''),
                'time_zone': created_calendar['timeZone'],
                'etag': created_calendar['etag']
            }
            
        except HttpError as e:
            logger.error(f"Google Calendar API error creating calendar: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating Google Calendar: {e}")
            raise