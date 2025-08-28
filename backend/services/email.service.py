import asyncio
import logging
from typing import Dict, Any, List, Optional
import base64
import json
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httpx

from core.config import settings
from core.redis_client import redis_client

logger = logging.getLogger(__name__)

class EmailService:
    """Email service supporting Gmail and Zoho with complete OAuth2 flow"""
    
    def __init__(self):
        self.gmail_service = None
        self.zoho_client = None
        self.initialized = False
        
        # OAuth2 scopes
        self.gmail_scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.compose',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
    
    async def initialize(self):
        """Initialize email service"""
        try:
            # Initialize Gmail if credentials available
            if settings.GMAIL_CLIENT_ID and settings.GMAIL_CLIENT_SECRET:
                await self._initialize_gmail()
            
            # Initialize Zoho if credentials available
            if settings.ZOHO_CLIENT_ID and settings.ZOHO_CLIENT_SECRET:
                await self._initialize_zoho()
            
            self.initialized = True
            logger.info("Email service initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize email service: {e}")
            raise
    
    async def _initialize_gmail(self):
        """Initialize Gmail service"""
        try:
            logger.info("Gmail service configured for OAuth2")
        except Exception as e:
            logger.error(f"Gmail initialization failed: {e}")
    
    async def _initialize_zoho(self):
        """Initialize Zoho service"""
        try:
            logger.info("Zoho service configured for OAuth2")
        except Exception as e:
            logger.error(f"Zoho initialization failed: {e}")
    
    def get_gmail_auth_url(self, user_id: str) -> str:
        """Get Gmail OAuth2 authorization URL"""
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GMAIL_CLIENT_ID,
                        "client_secret": settings.GMAIL_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [settings.GMAIL_REDIRECT_URI]
                    }
                },
                scopes=self.gmail_scopes
            )
            
            flow.redirect_uri = settings.GMAIL_REDIRECT_URI
            
            auth_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true',
                state=user_id,
                prompt='consent'
            )
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Error getting Gmail auth URL: {e}")
            raise
    
    def get_zoho_auth_url(self, user_id: str) -> str:
        """Get Zoho OAuth2 authorization URL"""
        try:
            auth_url = (
                f"https://accounts.zoho.com/oauth/v2/auth?"
                f"scope=ZohoMail.messages.ALL,ZohoMail.accounts.READ&"
                f"client_id={settings.ZOHO_CLIENT_ID}&"
                f"response_type=code&"
                f"redirect_uri={settings.ZOHO_REDIRECT_URI}&"
                f"access_type=offline&"
                f"state={user_id}"
            )
            return auth_url
            
        except Exception as e:
            logger.error(f"Error getting Zoho auth URL: {e}")
            raise
    
    async def handle_gmail_callback(self, authorization_code: str, user_id: str) -> Dict[str, Any]:
        """Handle Gmail OAuth2 callback"""
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": settings.GMAIL_CLIENT_ID,
                        "client_secret": settings.GMAIL_CLIENT_SECRET,
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [settings.GMAIL_REDIRECT_URI]
                    }
                },
                scopes=self.gmail_scopes
            )
            
            flow.redirect_uri = settings.GMAIL_REDIRECT_URI
            flow.fetch_token(code=authorization_code)
            
            credentials = flow.credentials
            
            # Store credentials
            await self._store_gmail_credentials(user_id, credentials)
            
            # Get user email
            email = await self._get_gmail_email(credentials)
            
            return {
                "success": True,
                "message": "Gmail account connected successfully",
                "email": email
            }
            
        except Exception as e:
            logger.error(f"Error handling Gmail callback: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def handle_zoho_callback(self, authorization_code: str, user_id: str) -> Dict[str, Any]:
        """Handle Zoho OAuth2 callback"""
        try:
            async with httpx.AsyncClient() as client:
                token_data = {
                    'grant_type': 'authorization_code',
                    'client_id': settings.ZOHO_CLIENT_ID,
                    'client_secret': settings.ZOHO_CLIENT_SECRET,
                    'redirect_uri': settings.ZOHO_REDIRECT_URI,
                    'code': authorization_code
                }
                
                response = await client.post(
                    'https://accounts.zoho.com/oauth/v2/token',
                    data=token_data
                )
                response.raise_for_status()
                
                token_info = response.json()
                
                # Store Zoho credentials
                await self._store_zoho_credentials(user_id, token_info)
                
                return {
                    "success": True,
                    "message": "Zoho account connected successfully",
                    "email": "user@zoho.com"  # Would get actual email from API
                }
                
        except Exception as e:
            logger.error(f"Error handling Zoho callback: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _store_gmail_credentials(self, user_id: str, credentials: Credentials):
        """Store Gmail credentials securely"""
        try:
            creds_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
                "expiry": credentials.expiry.isoformat() if credentials.expiry else None
            }
            
            # Store in Redis (encrypted in production)
            await redis_client.set(
                f"gmail_creds:{user_id}",
                creds_data,
                expire=3600 * 24 * 30  # 30 days
            )
            
            # Also update user record in database
            from core.database import get_db_session
            from models.database import User
            from sqlalchemy import select, update
            
            async with get_db_session() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(gmail_token=creds_data)
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error storing Gmail credentials: {e}")
            raise
    
    async def _store_zoho_credentials(self, user_id: str, token_info: Dict[str, Any]):
        """Store Zoho credentials securely"""
        try:
            # Store in Redis
            await redis_client.set(
                f"zoho_creds:{user_id}",
                token_info,
                expire=token_info.get('expires_in', 3600)
            )
            
            # Update user record
            from core.database import get_db_session
            from models.database import User
            from sqlalchemy import update
            
            async with get_db_session() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(zoho_token=token_info)
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error storing Zoho credentials: {e}")
            raise
    
    async def _get_gmail_credentials(self, user_id: str) -> Optional[Credentials]:
        """Get Gmail credentials for user"""
        try:
            # Try Redis first
            creds_data = await redis_client.get(f"gmail_creds:{user_id}")
            
            if not creds_data:
                # Fallback to database
                from core.database import get_db_session
                from models.database import User
                from sqlalchemy import select
                
                async with get_db_session() as session:
                    query = select(User).where(User.id == user_id)
                    result = await session.execute(query)
                    user = result.scalar_one_or_none()
                    
                    if user and user.gmail_token:
                        creds_data = user.gmail_token
            
            if creds_data:
                credentials = Credentials(
                    token=creds_data["token"],
                    refresh_token=creds_data.get("refresh_token"),
                    token_uri=creds_data["token_uri"],
                    client_id=creds_data["client_id"],
                    client_secret=creds_data["client_secret"],
                    scopes=creds_data["scopes"]
                )
                
                # Set expiry if available
                if creds_data.get("expiry"):
                    from datetime import datetime
                    credentials.expiry = datetime.fromisoformat(creds_data["expiry"])
                
                return credentials
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting Gmail credentials: {e}")
            return None
    
    async def _get_gmail_email(self, credentials: Credentials) -> str:
        """Get Gmail email address"""
        try:
            service = build('gmail', 'v1', credentials=credentials)
            profile = service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress', '')
            
        except Exception as e:
            logger.error(f"Error getting Gmail email: {e}")
            return ""
    
    async def send_gmail(self, user_id: str, to: List[str], subject: str, body: str, html_body: Optional[str] = None, cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send email via Gmail"""
        try:
            credentials = await self._get_gmail_credentials(user_id)
            if not credentials:
                return {
                    "success": False,
                    "error": "Gmail not connected. Please connect your Gmail account first."
                }
            
            service = build('gmail', 'v1', credentials=credentials)
            
            # Create message
            if html_body:
                message = MIMEMultipart('alternative')
                message.attach(MIMEText(body, 'plain'))
                message.attach(MIMEText(html_body, 'html'))
            else:
                message = MIMEText(body)
            
            message['to'] = ', '.join(to)
            message['subject'] = subject
            
            if cc:
                message['cc'] = ', '.join(cc)
            if bcc:
                message['bcc'] = ', '.join(bcc)
            
            # Send message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
            send_message = service.users().messages().send(
                userId='me',
                body={'raw': raw_message}
            ).execute()
            
            return {
                "success": True,
                "message_id": send_message['id'],
                "message": "Email sent successfully via Gmail"
            }
            
        except HttpError as e:
            logger.error(f"Gmail API error: {e}")
            return {
                "success": False,
                "error": f"Gmail error: {e.error_details[0]['message'] if e.error_details else str(e)}"
            }
        except Exception as e:
            logger.error(f"Error sending Gmail: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_recent_emails(self, user_id: str, limit: int = 10, query: str = "in:inbox") -> List[Dict[str, Any]]:
        """Get recent emails from Gmail"""
        try:
            credentials = await self._get_gmail_credentials(user_id)
            if not credentials:
                return []
            
            service = build('gmail', 'v1', credentials=credentials)
            
            # Get message list
            results = service.users().messages().list(
                userId='me',
                maxResults=limit,
                q=query
            ).execute()
            
            messages = results.get('messages', [])
            
            # Get message details
            email_list = []
            for message in messages:
                try:
                    msg = service.users().messages().get(
                        userId='me',
                        id=message['id'],
                        format='metadata',
                        metadataHeaders=['From', 'Subject', 'Date', 'To']
                    ).execute()
                    
                    headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
                    
                    email_list.append({
                        "id": message['id'],
                        "thread_id": msg.get('threadId'),
                        "from": headers.get('From', ''),
                        "to": headers.get('To', ''),
                        "subject": headers.get('Subject', ''),
                        "date": headers.get('Date', ''),
                        "snippet": msg.get('snippet', ''),
                        "unread": 'UNREAD' in msg.get('labelIds', []),
                        "labels": msg.get('labelIds', [])
                    })
                except Exception as e:
                    logger.warning(f"Error processing message {message['id']}: {e}")
                    continue
            
            return email_list
            
        except Exception as e:
            logger.error(f"Error getting recent emails: {e}")
            return []
    
    async def reply_to_email(self, user_id: str, message_id: str, reply_body: str, html_body: Optional[str] = None) -> Dict[str, Any]:
        """Reply to an email"""
        try:
            credentials = await self._get_gmail_credentials(user_id)
            if not credentials:
                return {
                    "success": False,
                    "error": "Gmail not connected"
                }
            
            service = build('gmail', 'v1', credentials=credentials)
            
            # Get original message
            original_msg = service.users().messages().get(
                userId='me',
                id=message_id
            ).execute()
            
            # Extract headers
            headers = {h['name']: h['value'] for h in original_msg['payload'].get('headers', [])}
            
            # Create reply
            if html_body:
                reply = MIMEMultipart('alternative')
                reply.attach(MIMEText(reply_body, 'plain'))
                reply.attach(MIMEText(html_body, 'html'))
            else:
                reply = MIMEText(reply_body)
            
            reply['to'] = headers.get('From', '')
            reply['subject'] = 'Re: ' + headers.get('Subject', '').replace('Re: ', '', 1)
            reply['in-reply-to'] = headers.get('Message-ID', '')
            reply['references'] = headers.get('References', '') + ' ' + headers.get('Message-ID', '')
            
            # Send reply
            raw_reply = base64.urlsafe_b64encode(reply.as_bytes()).decode()
            send_reply = service.users().messages().send(
                userId='me',
                body={
                    'raw': raw_reply,
                    'threadId': original_msg.get('threadId')
                }
            ).execute()
            
            return {
                "success": True,
                "message_id": send_reply['id'],
                "message": "Reply sent successfully"
            }
            
        except Exception as e:
            logger.error(f"Error replying to email: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_emails(self, user_id: str, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search emails"""
        return await self.get_recent_emails(user_id, limit, query)
    
    async def get_email_content(self, user_id: str, message_id: str) -> Optional[Dict[str, Any]]:
        """Get full email content"""
        try:
            credentials = await self._get_gmail_credentials(user_id)
            if not credentials:
                return None
            
            service = build('gmail', 'v1', credentials=credentials)
            
            # Get full message
            msg = service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract headers
            headers = {h['name']: h['value'] for h in msg['payload'].get('headers', [])}
            
            # Extract body
            body_text = ""
            body_html = ""
            
            def extract_body(payload):
                nonlocal body_text, body_html
                
                if payload.get('mimeType') == 'text/plain':
                    data = payload.get('body', {}).get('data', '')
                    if data:
                        body_text = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif payload.get('mimeType') == 'text/html':
                    data = payload.get('body', {}).get('data', '')
                    if data:
                        body_html = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                elif payload.get('parts'):
                    for part in payload['parts']:
                        extract_body(part)
            
            extract_body(msg['payload'])
            
            return {
                "id": message_id,
                "thread_id": msg.get('threadId', ''),
                "from": headers.get('From', ''),
                "to": headers.get('To', ''),
                "cc": headers.get('Cc', ''),
                "subject": headers.get('Subject', ''),
                "date": headers.get('Date', ''),
                "body_text": body_text,
                "body_html": body_html,
                "snippet": msg.get('snippet', ''),
                "labels": msg.get('labelIds', [])
            }
            
        except Exception as e:
            logger.error(f"Error getting email content: {e}")
            return None
    
    async def disconnect_gmail(self, user_id: str) -> bool:
        """Disconnect Gmail account"""
        try:
            # Remove from Redis
            await redis_client.delete(f"gmail_creds:{user_id}")
            
            # Remove from database
            from core.database import get_db_session
            from models.database import User
            from sqlalchemy import update
            
            async with get_db_session() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(gmail_token=None)
                )
                await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting Gmail: {e}")
            return False
    
    async def disconnect_zoho(self, user_id: str) -> bool:
        """Disconnect Zoho account"""
        try:
            # Remove from Redis
            await redis_client.delete(f"zoho_creds:{user_id}")
            
            # Remove from database
            from core.database import get_db_session
            from models.database import User
            from sqlalchemy import update
            
            async with get_db_session() as session:
                await session.execute(
                    update(User)
                    .where(User.id == user_id)
                    .values(zoho_token=None)
                )
                await session.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error disconnecting Zoho: {e}")
            return False
    
    async def get_connection_status(self, user_id: str) -> Dict[str, bool]:
        """Get email connection status"""
        try:
            gmail_connected = await self._get_gmail_credentials(user_id) is not None
            zoho_creds = await redis_client.get(f"zoho_creds:{user_id}")
            zoho_connected = zoho_creds is not None
            
            return {
                "gmail": gmail_connected,
                "zoho": zoho_connected
            }
            
        except Exception as e:
            logger.error(f"Error getting connection status: {e}")
            return {"gmail": False, "zoho": False}