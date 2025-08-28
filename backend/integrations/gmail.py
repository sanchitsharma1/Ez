import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import base64
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import json

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from core.config import settings

logger = logging.getLogger(__name__)

class GmailIntegration:
    """Gmail API integration for email management"""
    
    def __init__(self):
        self.scopes = [
            'https://www.googleapis.com/auth/gmail.readonly',
            'https://www.googleapis.com/auth/gmail.send',
            'https://www.googleapis.com/auth/gmail.modify'
        ]
        self.service = None
        
    async def initialize_oauth_flow(self, redirect_uri: str) -> str:
        """Initialize OAuth2 flow and return authorization URL"""
        try:
            flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": settings.GMAIL_CLIENT_ID,
                        "client_secret": settings.GMAIL_CLIENT_SECRET,
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
            logger.error(f"Error initializing Gmail OAuth flow: {e}")
            raise
    
    async def exchange_code_for_tokens(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access tokens"""
        try:
            flow = Flow.from_client_config(
                client_config={
                    "web": {
                        "client_id": settings.GMAIL_CLIENT_ID,
                        "client_secret": settings.GMAIL_CLIENT_SECRET,
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
    
    async def initialize_service(self, credentials_dict: Dict[str, Any]):
        """Initialize Gmail service with credentials"""
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
                
                return updated_creds
            
            self.service = build('gmail', 'v1', credentials=credentials)
            return credentials_dict
            
        except Exception as e:
            logger.error(f"Error initializing Gmail service: {e}")
            raise
    
    async def get_profile(self) -> Dict[str, Any]:
        """Get Gmail profile information"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            profile = self.service.users().getProfile(userId='me').execute()
            
            return {
                "email_address": profile.get('emailAddress'),
                "messages_total": profile.get('messagesTotal', 0),
                "threads_total": profile.get('threadsTotal', 0),
                "history_id": profile.get('historyId')
            }
            
        except HttpError as e:
            logger.error(f"Gmail API error getting profile: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting Gmail profile: {e}")
            raise
    
    async def list_messages(
        self,
        query: str = "",
        max_results: int = 50,
        page_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """List Gmail messages with optional query"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            request_params = {
                'userId': 'me',
                'maxResults': max_results
            }
            
            if query:
                request_params['q'] = query
            if page_token:
                request_params['pageToken'] = page_token
            
            result = self.service.users().messages().list(**request_params).execute()
            
            messages = result.get('messages', [])
            next_page_token = result.get('nextPageToken')
            
            return {
                "messages": messages,
                "next_page_token": next_page_token,
                "result_size_estimate": result.get('resultSizeEstimate', 0)
            }
            
        except HttpError as e:
            logger.error(f"Gmail API error listing messages: {e}")
            raise
        except Exception as e:
            logger.error(f"Error listing Gmail messages: {e}")
            raise
    
    async def get_message(self, message_id: str) -> Dict[str, Any]:
        """Get a specific Gmail message"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Parse message
            parsed_message = await self._parse_message(message)
            
            return parsed_message
            
        except HttpError as e:
            logger.error(f"Gmail API error getting message {message_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting Gmail message {message_id}: {e}")
            raise
    
    async def send_message(
        self,
        to: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        in_reply_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a Gmail message"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            # Create message
            message = MIMEMultipart('alternative')
            message['To'] = ', '.join(to)
            message['Subject'] = subject
            
            if cc:
                message['Cc'] = ', '.join(cc)
            if bcc:
                message['Bcc'] = ', '.join(bcc)
            if in_reply_to:
                message['In-Reply-To'] = in_reply_to
                message['References'] = in_reply_to
            
            # Add text body
            if body_text:
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                message.attach(text_part)
            
            # Add HTML body
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                message.attach(html_part)
            
            # Add attachments
            if attachments:
                for attachment in attachments:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment['data'])
                    encoders.encode_base64(part)
                    part.add_header(
                        'Content-Disposition',
                        f'attachment; filename= {attachment["filename"]}'
                    )
                    message.attach(part)
            
            # Send message
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            send_message = {'raw': raw_message}
            
            result = self.service.users().messages().send(
                userId='me',
                body=send_message
            ).execute()
            
            return {
                "message_id": result['id'],
                "thread_id": result['threadId'],
                "status": "sent",
                "sent_at": datetime.utcnow().isoformat()
            }
            
        except HttpError as e:
            logger.error(f"Gmail API error sending message: {e}")
            raise
        except Exception as e:
            logger.error(f"Error sending Gmail message: {e}")
            raise
    
    async def modify_message(
        self,
        message_id: str,
        add_labels: Optional[List[str]] = None,
        remove_labels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Modify message labels (read/unread, star, etc.)"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            modify_request = {}
            
            if add_labels:
                modify_request['addLabelIds'] = add_labels
            if remove_labels:
                modify_request['removeLabelIds'] = remove_labels
            
            result = self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body=modify_request
            ).execute()
            
            return {
                "message_id": result['id'],
                "labels": result['labelIds'],
                "modified_at": datetime.utcnow().isoformat()
            }
            
        except HttpError as e:
            logger.error(f"Gmail API error modifying message {message_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error modifying Gmail message {message_id}: {e}")
            raise
    
    async def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark message as read"""
        return await self.modify_message(
            message_id=message_id,
            remove_labels=['UNREAD']
        )
    
    async def mark_as_unread(self, message_id: str) -> Dict[str, Any]:
        """Mark message as unread"""
        return await self.modify_message(
            message_id=message_id,
            add_labels=['UNREAD']
        )
    
    async def star_message(self, message_id: str) -> Dict[str, Any]:
        """Star message"""
        return await self.modify_message(
            message_id=message_id,
            add_labels=['STARRED']
        )
    
    async def get_labels(self) -> List[Dict[str, Any]]:
        """Get all labels"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            result = self.service.users().labels().list(userId='me').execute()
            labels = result.get('labels', [])
            
            return [
                {
                    "id": label['id'],
                    "name": label['name'],
                    "type": label['type'],
                    "messages_total": label.get('messagesTotal', 0),
                    "messages_unread": label.get('messagesUnread', 0)
                }
                for label in labels
            ]
            
        except HttpError as e:
            logger.error(f"Gmail API error getting labels: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting Gmail labels: {e}")
            raise
    
    async def create_draft(
        self,
        to: List[str],
        subject: str,
        body_text: Optional[str] = None,
        body_html: Optional[str] = None,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Create a draft message"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            # Create message
            message = MIMEMultipart('alternative')
            message['To'] = ', '.join(to)
            message['Subject'] = subject
            
            if cc:
                message['Cc'] = ', '.join(cc)
            if bcc:
                message['Bcc'] = ', '.join(bcc)
            
            # Add text body
            if body_text:
                text_part = MIMEText(body_text, 'plain', 'utf-8')
                message.attach(text_part)
            
            # Add HTML body
            if body_html:
                html_part = MIMEText(body_html, 'html', 'utf-8')
                message.attach(html_part)
            
            # Create draft
            raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
            
            draft_message = {
                'message': {'raw': raw_message}
            }
            
            result = self.service.users().drafts().create(
                userId='me',
                body=draft_message
            ).execute()
            
            return {
                "draft_id": result['id'],
                "message_id": result['message']['id'],
                "thread_id": result['message']['threadId'],
                "created_at": datetime.utcnow().isoformat()
            }
            
        except HttpError as e:
            logger.error(f"Gmail API error creating draft: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating Gmail draft: {e}")
            raise
    
    async def _parse_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Gmail message format"""
        try:
            headers = message['payload'].get('headers', [])
            
            # Extract headers
            header_dict = {}
            for header in headers:
                header_dict[header['name'].lower()] = header['value']
            
            # Extract body
            body_text = ""
            body_html = ""
            attachments = []
            
            if 'parts' in message['payload']:
                # Multipart message
                for part in message['payload']['parts']:
                    await self._extract_part(part, body_text, body_html, attachments)
            else:
                # Single part message
                await self._extract_part(message['payload'], body_text, body_html, attachments)
            
            return {
                "message_id": message['id'],
                "thread_id": message['threadId'],
                "subject": header_dict.get('subject', ''),
                "sender": header_dict.get('from', ''),
                "recipients": header_dict.get('to', '').split(', ') if header_dict.get('to') else [],
                "cc": header_dict.get('cc', '').split(', ') if header_dict.get('cc') else [],
                "bcc": header_dict.get('bcc', '').split(', ') if header_dict.get('bcc') else [],
                "date": header_dict.get('date', ''),
                "body_text": body_text.strip(),
                "body_html": body_html.strip(),
                "attachments": attachments,
                "labels": message.get('labelIds', []),
                "snippet": message.get('snippet', ''),
                "size_estimate": message.get('sizeEstimate', 0),
                "history_id": message.get('historyId')
            }
            
        except Exception as e:
            logger.error(f"Error parsing Gmail message: {e}")
            raise
    
    async def _extract_part(self, part: Dict[str, Any], body_text: str, body_html: str, attachments: List):
        """Extract content from message part"""
        try:
            mime_type = part.get('mimeType', '')
            
            if mime_type == 'text/plain':
                data = part.get('body', {}).get('data', '')
                if data:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8')
                    body_text += decoded
                    
            elif mime_type == 'text/html':
                data = part.get('body', {}).get('data', '')
                if data:
                    decoded = base64.urlsafe_b64decode(data).decode('utf-8')
                    body_html += decoded
                    
            elif part.get('filename'):
                # Attachment
                attachments.append({
                    "filename": part['filename'],
                    "mime_type": mime_type,
                    "size": part.get('body', {}).get('size', 0),
                    "attachment_id": part.get('body', {}).get('attachmentId')
                })
                
            # Handle nested parts
            if 'parts' in part:
                for nested_part in part['parts']:
                    await self._extract_part(nested_part, body_text, body_html, attachments)
                    
        except Exception as e:
            logger.error(f"Error extracting message part: {e}")
    
    async def download_attachment(self, message_id: str, attachment_id: str) -> bytes:
        """Download message attachment"""
        try:
            if not self.service:
                raise ValueError("Gmail service not initialized")
            
            attachment = self.service.users().messages().attachments().get(
                userId='me',
                messageId=message_id,
                id=attachment_id
            ).execute()
            
            data = attachment.get('data', '')
            return base64.urlsafe_b64decode(data)
            
        except HttpError as e:
            logger.error(f"Gmail API error downloading attachment: {e}")
            raise
        except Exception as e:
            logger.error(f"Error downloading Gmail attachment: {e}")
            raise