import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import httpx
from urllib.parse import urljoin

from core.config import settings

logger = logging.getLogger(__name__)

class WhatsAppIntegration:
    """WhatsApp Business Cloud API integration"""
    
    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.webhook_verify_token = settings.WHATSAPP_WEBHOOK_TOKEN
        
    async def send_text_message(
        self,
        to: str,
        message: str,
        preview_url: bool = True
    ) -> Dict[str, Any]:
        """Send a text message via WhatsApp"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "text",
                "text": {
                    "body": message,
                    "preview_url": preview_url
                }
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    "message_id": result["messages"][0]["id"],
                    "to": to,
                    "status": "sent",
                    "sent_at": datetime.utcnow().isoformat()
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error sending message: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {e}")
            raise
    
    async def send_template_message(
        self,
        to: str,
        template_name: str,
        language_code: str = "en",
        parameters: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Send a template message via WhatsApp"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            template_payload = {
                "name": template_name,
                "language": {
                    "code": language_code
                }
            }
            
            if parameters:
                template_payload["components"] = [
                    {
                        "type": "body",
                        "parameters": [
                            {"type": "text", "text": param} for param in parameters
                        ]
                    }
                ]
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "template",
                "template": template_payload
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    "message_id": result["messages"][0]["id"],
                    "to": to,
                    "template": template_name,
                    "status": "sent",
                    "sent_at": datetime.utcnow().isoformat()
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error sending template: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending WhatsApp template: {e}")
            raise
    
    async def send_interactive_message(
        self,
        to: str,
        header_text: str,
        body_text: str,
        footer_text: Optional[str] = None,
        buttons: Optional[List[Dict[str, str]]] = None,
        list_sections: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Send an interactive message (buttons or list)"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            interactive_payload = {
                "type": "button" if buttons else "list",
                "header": {
                    "type": "text",
                    "text": header_text
                },
                "body": {
                    "text": body_text
                }
            }
            
            if footer_text:
                interactive_payload["footer"] = {"text": footer_text}
            
            if buttons:
                interactive_payload["action"] = {
                    "buttons": [
                        {
                            "type": "reply",
                            "reply": {
                                "id": button["id"],
                                "title": button["title"]
                            }
                        }
                        for button in buttons[:3]  # Max 3 buttons
                    ]
                }
            elif list_sections:
                interactive_payload["action"] = {
                    "button": "Select Option",
                    "sections": list_sections
                }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": "interactive",
                "interactive": interactive_payload
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    "message_id": result["messages"][0]["id"],
                    "to": to,
                    "type": "interactive",
                    "status": "sent",
                    "sent_at": datetime.utcnow().isoformat()
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error sending interactive message: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending WhatsApp interactive message: {e}")
            raise
    
    async def send_media_message(
        self,
        to: str,
        media_type: str,
        media_url: str,
        caption: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a media message (image, document, audio, video)"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            media_payload = {
                "link": media_url
            }
            
            if caption:
                media_payload["caption"] = caption
            if filename and media_type == "document":
                media_payload["filename"] = filename
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to,
                "type": media_type,
                media_type: media_payload
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                
                return {
                    "message_id": result["messages"][0]["id"],
                    "to": to,
                    "media_type": media_type,
                    "status": "sent",
                    "sent_at": datetime.utcnow().isoformat()
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error sending media: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error sending WhatsApp media: {e}")
            raise
    
    async def mark_message_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark a received message as read"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "status": "read",
                "message_id": message_id
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                
                return {
                    "message_id": message_id,
                    "status": "read",
                    "marked_at": datetime.utcnow().isoformat()
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error marking message as read: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error marking WhatsApp message as read: {e}")
            raise
    
    async def get_media_url(self, media_id: str) -> str:
        """Get media URL from media ID"""
        try:
            url = f"{self.base_url}/{media_id}"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                result = response.json()
                return result["url"]
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error getting media URL: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error getting WhatsApp media URL: {e}")
            raise
    
    async def download_media(self, media_url: str) -> bytes:
        """Download media content"""
        try:
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(media_url, headers=headers)
                response.raise_for_status()
                
                return response.content
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error downloading media: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error downloading WhatsApp media: {e}")
            raise
    
    def verify_webhook(self, mode: str, token: str, challenge: str) -> Optional[str]:
        """Verify webhook subscription"""
        try:
            if mode == "subscribe" and token == self.webhook_verify_token:
                return challenge
            return None
            
        except Exception as e:
            logger.error(f"Error verifying WhatsApp webhook: {e}")
            return None
    
    async def process_webhook_message(self, webhook_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Process incoming webhook message"""
        try:
            messages = []
            
            entry = webhook_data.get("entry", [])
            for entry_item in entry:
                changes = entry_item.get("changes", [])
                
                for change in changes:
                    if change.get("field") == "messages":
                        value = change.get("value", {})
                        
                        # Process messages
                        for message in value.get("messages", []):
                            processed_message = await self._process_message(message, value)
                            if processed_message:
                                messages.append(processed_message)
                        
                        # Process status updates
                        for status in value.get("statuses", []):
                            processed_status = await self._process_status(status)
                            if processed_status:
                                messages.append(processed_status)
            
            return messages
            
        except Exception as e:
            logger.error(f"Error processing WhatsApp webhook: {e}")
            raise
    
    async def _process_message(self, message: Dict[str, Any], value: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process individual incoming message"""
        try:
            message_id = message.get("id")
            from_number = message.get("from")
            timestamp = message.get("timestamp")
            message_type = message.get("type")
            
            # Get contact info
            contacts = value.get("contacts", [])
            contact_name = ""
            for contact in contacts:
                if contact.get("wa_id") == from_number:
                    contact_name = contact.get("profile", {}).get("name", "")
                    break
            
            processed_message = {
                "message_id": message_id,
                "from": from_number,
                "contact_name": contact_name,
                "timestamp": datetime.fromtimestamp(int(timestamp)).isoformat(),
                "type": message_type,
                "webhook_type": "message"
            }
            
            # Extract content based on message type
            if message_type == "text":
                processed_message["text"] = message.get("text", {}).get("body", "")
                
            elif message_type == "button":
                processed_message["button_text"] = message.get("button", {}).get("text", "")
                processed_message["button_payload"] = message.get("button", {}).get("payload", "")
                
            elif message_type == "interactive":
                interactive = message.get("interactive", {})
                if interactive.get("type") == "button_reply":
                    processed_message["button_reply"] = interactive.get("button_reply", {})
                elif interactive.get("type") == "list_reply":
                    processed_message["list_reply"] = interactive.get("list_reply", {})
                    
            elif message_type in ["image", "audio", "video", "document"]:
                media = message.get(message_type, {})
                processed_message["media_id"] = media.get("id")
                processed_message["mime_type"] = media.get("mime_type")
                processed_message["sha256"] = media.get("sha256")
                
                if message_type == "document":
                    processed_message["filename"] = media.get("filename")
                elif "caption" in media:
                    processed_message["caption"] = media.get("caption")
            
            # Mark message as read
            try:
                await self.mark_message_as_read(message_id)
            except Exception as e:
                logger.warning(f"Failed to mark message as read: {e}")
            
            return processed_message
            
        except Exception as e:
            logger.error(f"Error processing individual message: {e}")
            return None
    
    async def _process_status(self, status: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process message status update"""
        try:
            return {
                "message_id": status.get("id"),
                "recipient_id": status.get("recipient_id"),
                "status": status.get("status"),
                "timestamp": datetime.fromtimestamp(int(status.get("timestamp", 0))).isoformat(),
                "webhook_type": "status"
            }
            
        except Exception as e:
            logger.error(f"Error processing status update: {e}")
            return None
    
    async def create_task_from_message(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a task from WhatsApp message"""
        try:
            # Extract task information from message
            text = message.get("text", "").strip()
            
            if not text:
                return None
            
            # Simple task detection patterns
            task_patterns = [
                "remind me to",
                "add task",
                "todo:",
                "task:",
                "schedule",
                "appointment"
            ]
            
            is_task = any(pattern in text.lower() for pattern in task_patterns)
            
            if not is_task:
                return None
            
            # Create task data
            task_data = {
                "title": text[:100],  # Truncate title
                "description": f"Task created from WhatsApp message from {message.get('contact_name', message.get('from'))}",
                "source": "whatsapp",
                "source_message_id": message.get("message_id"),
                "created_from_contact": message.get("from"),
                "created_at": message.get("timestamp")
            }
            
            return task_data
            
        except Exception as e:
            logger.error(f"Error creating task from WhatsApp message: {e}")
            return None
    
    async def send_task_confirmation(self, to: str, task_title: str) -> Dict[str, Any]:
        """Send task creation confirmation"""
        try:
            message = f"✅ Task created: {task_title}\n\nI'll help you manage this task through our assistant system."
            
            return await self.send_text_message(to, message)
            
        except Exception as e:
            logger.error(f"Error sending task confirmation: {e}")
            raise
    
    async def send_reminder(self, to: str, reminder_text: str) -> Dict[str, Any]:
        """Send a reminder message"""
        try:
            message = f"⏰ Reminder: {reminder_text}"
            
            return await self.send_text_message(to, message)
            
        except Exception as e:
            logger.error(f"Error sending reminder: {e}")
            raise
    
    async def get_business_profile(self) -> Dict[str, Any]:
        """Get WhatsApp Business profile information"""
        try:
            url = f"{self.base_url}/{self.phone_number_id}/whatsapp_business_profile"
            
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            params = {
                "fields": "about,address,description,email,profile_picture_url,websites,vertical"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                
                return response.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error getting business profile: {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error getting WhatsApp business profile: {e}")
            raise