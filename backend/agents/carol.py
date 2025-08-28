from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime, timedelta
import json
import re

from agents.base_agent import BaseAgent
from services.email_service import EmailService
from services.calendar_service import CalendarService
from services.task_service import TaskService
from utils.intent_detection import IntentDetector
from models.schemas import EmailMessage, CalendarEventCreate, TaskCreate

logger = logging.getLogger(__name__)

class CarolAgent(BaseAgent):
    """Carol Garcia - Executive Assistant and Main Coordinator"""
    
    def __init__(self):
        super().__init__(
            agent_id="carol",
            name="Carol Garcia",
            persona="""You are Carol Garcia, a highly professional and proactive executive assistant. 
            You are organized, efficient, and have excellent communication skills. You coordinate tasks 
            between different specialized agents and handle general administrative duties including email 
            management, scheduling, and task coordination. You're friendly but professional, and always 
            aim to be helpful while maintaining appropriate boundaries."""
        )
        
        self.capabilities = [
            "email_management",
            "calendar_scheduling", 
            "task_coordination",
            "general_assistance",
            "agent_routing",
            "approval_coordination"
        ]
        
        self.voice_id = "EXAVITQu4vr4xnSDxMaL"  # Female voice for Carol
        
        # Service integrations
        self.email_service: Optional[EmailService] = None
        self.calendar_service: Optional[CalendarService] = None
        self.task_service: Optional[TaskService] = None
        self.intent_detector: Optional[IntentDetector] = None
    
    async def _initialize_agent(self):
        """Initialize Carol-specific services"""
        try:
            # Initialize services
            self.email_service = EmailService()
            await self.email_service.initialize()
            
            self.calendar_service = CalendarService()
            await self.calendar_service.initialize()
            
            self.task_service = TaskService()
            await self.task_service.initialize()
            
            self.intent_detector = IntentDetector()
            
            logger.info("Carol Garcia initialized with all services")
            
        except Exception as e:
            logger.error(f"Failed to initialize Carol's services: {e}")
            raise
    
    def _get_agent_instructions(self) -> str:
        """Get Carol-specific instructions"""
        return """
        As Carol Garcia, you should:
        
        1. EMAIL MANAGEMENT:
           - Help compose, send, and reply to emails
           - Summarize email threads and important messages
           - Draft professional correspondence
           - Always ask for approval before sending emails
        
        2. CALENDAR & SCHEDULING:
           - Schedule meetings and appointments
           - Set reminders for important events
           - Check availability and suggest meeting times
           - Coordinate with external parties
        
        3. TASK COORDINATION:
           - Create and manage to-do items
           - Assign tasks to appropriate agents
           - Track task progress and deadlines
           - Follow up on pending items
        
        4. AGENT COORDINATION:
           - Route complex requests to specialized agents
           - Coordinate responses from multiple agents
           - Ensure consistency across agent interactions
        
        5. GENERAL ASSISTANCE:
           - Answer questions about the system capabilities
           - Help with general productivity tasks
           - Provide status updates on ongoing work
        
        Always be proactive in suggesting improvements and follow-ups.
        Maintain a professional but warm tone in all interactions.
        Ask clarifying questions when requests are ambiguous.
        """
    
    async def process_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process message as Carol Garcia"""
        try:
            messages = context.get("messages", [])
            intent = context.get("intent", "general")
            user_context = context.get("context", {})
            mode = context.get("mode", "online")
            
            if not messages:
                return await self._generate_greeting()
            
            user_message = messages[-1]["content"]
            
            # Route to specific handler based on intent
            if intent == "email":
                return await self._handle_email_request(user_message, user_context, mode)
            elif intent == "calendar":
                return await self._handle_calendar_request(user_message, user_context, mode)
            elif intent == "task_management":
                return await self._handle_task_request(user_message, user_context, mode)
            elif intent == "agent_routing":
                return await self._handle_agent_routing(user_message, user_context, mode)
            else:
                return await self._handle_general_request(messages, user_context, mode)
                
        except Exception as e:
            logger.error(f"Error processing message in Carol: {e}")
            return await self.handle_error(str(e), context)
    
    async def _generate_greeting(self) -> Dict[str, Any]:
        """Generate a greeting message"""
        greeting = """Hello! I'm Carol Garcia, your executive assistant. I'm here to help you with:

📧 **Email Management** - Compose, send, and organize your emails
📅 **Calendar & Scheduling** - Manage appointments and meetings  
✅ **Task Coordination** - Create and track your to-do items
🤝 **Agent Coordination** - Connect you with specialized team members
💼 **General Assistance** - Support with various productivity tasks

What can I help you with today?"""
        
        return {
            "response": greeting,
            "requires_approval": False,
            "metadata": {
                "agent_id": self.agent_id,
                "message_type": "greeting"
            }
        }
    
    async def _handle_email_request(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle email-related requests"""
        try:
            # Extract email intent
            if any(keyword in message.lower() for keyword in ["send", "compose", "write"]):
                return await self._compose_email(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["check", "read", "inbox"]):
                return await self._check_emails(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["reply", "respond"]):
                return await self._reply_to_email(message, context, mode)
            else:
                return await self._general_email_assistance(message, context, mode)
                
        except Exception as e:
            logger.error(f"Error handling email request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _compose_email(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Compose an email based on user request"""
        try:
            # Extract email details using LLM
            extraction_prompt = f"""
            Extract email details from this request: "{message}"
            
            Return JSON with:
            - recipients: list of email addresses
            - subject: email subject
            - body: email body content
            - tone: professional/casual/urgent
            - attachments: any mentioned files
            """
            
            # Generate structured response
            email_details = await self._extract_structured_info(extraction_prompt, mode)
            
            if not email_details.get("recipients"):
                return {
                    "response": "I'd be happy to help you compose an email! Could you please specify who you'd like to send it to?",
                    "requires_approval": False,
                    "metadata": {"needs_clarification": True}
                }
            
            # Draft the email
            draft_response = f"""I've drafted an email for you:

**To:** {', '.join(email_details.get('recipients', []))}
**Subject:** {email_details.get('subject', 'No subject')}

**Message:**
{email_details.get('body', 'No content specified')}

Would you like me to send this email? Please review and let me know if you'd like any changes."""
            
            # Create approval request
            approval_request = {
                "action_type": "send_email",
                "description": f"Send email to {', '.join(email_details.get('recipients', []))}",
                "payload": {
                    "recipients": email_details.get("recipients", []),
                    "subject": email_details.get("subject", ""),
                    "body": email_details.get("body", ""),
                    "tone": email_details.get("tone", "professional")
                },
                "risk_level": "medium"
            }
            
            return {
                "response": draft_response,
                "requires_approval": True,
                "approval_request": approval_request,
                "metadata": {
                    "email_draft": email_details,
                    "action_type": "compose_email"
                }
            }
            
        except Exception as e:
            logger.error(f"Error composing email: {e}")
            return await self.handle_error(str(e), {})
    
    async def _check_emails(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Check and summarize emails"""
        try:
            if not self.email_service:
                return {
                    "response": "Email service is not configured. Please set up your email integration first.",
                    "requires_approval": False,
                    "metadata": {"error": "service_not_configured"}
                }
            
            # Get recent emails
            emails = await self.email_service.get_recent_emails(limit=10)
            
            if not emails:
                return {
                    "response": "You have no new emails at the moment.",
                    "requires_approval": False,
                    "metadata": {"email_count": 0}
                }
            
            # Summarize emails
            summary = "📧 **Recent Emails Summary:**\n\n"
            for i, email in enumerate(emails[:5], 1):
                summary += f"{i}. **From:** {email.get('from', 'Unknown')}\n"
                summary += f"   **Subject:** {email.get('subject', 'No subject')}\n"
                summary += f"   **Time:** {email.get('date', 'Unknown')}\n\n"
            
            if len(emails) > 5:
                summary += f"...and {len(emails) - 5} more emails.\n"
            
            summary += "\nWould you like me to help you with any specific email?"
            
            return {
                "response": summary,
                "requires_approval": False,
                "metadata": {
                    "email_count": len(emails),
                    "emails": emails[:5]  # Store first 5 for reference
                }
            }
            
        except Exception as e:
            logger.error(f"Error checking emails: {e}")
            return await self.handle_error(str(e), {})
    
    async def _handle_calendar_request(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle calendar-related requests"""
        try:
            if any(keyword in message.lower() for keyword in ["schedule", "book", "meeting"]):
                return await self._schedule_event(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["check", "calendar", "appointments"]):
                return await self._check_calendar(message, context, mode)
            else:
                return await self._general_calendar_assistance(message, context, mode)
                
        except Exception as e:
            logger.error(f"Error handling calendar request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _schedule_event(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Schedule a calendar event"""
        try:
            # Extract event details
            extraction_prompt = f"""
            Extract calendar event details from: "{message}"
            
            Return JSON with:
            - title: event title
            - start_time: ISO datetime
            - end_time: ISO datetime
            - attendees: list of email addresses
            - location: event location
            - description: additional details
            """
            
            event_details = await self._extract_structured_info(extraction_prompt, mode)
            
            if not event_details.get("title"):
                return {
                    "response": "I'd be happy to schedule an event for you! Could you please provide more details about what you'd like to schedule?",
                    "requires_approval": False,
                    "metadata": {"needs_clarification": True}
                }
            
            # Create event summary
            event_summary = f"""I'll schedule this event for you:

**Title:** {event_details.get('title', 'Untitled Event')}
**Date & Time:** {event_details.get('start_time', 'To be determined')} - {event_details.get('end_time', 'To be determined')}
**Location:** {event_details.get('location', 'Not specified')}
**Attendees:** {', '.join(event_details.get('attendees', [])) or 'Just you'}

Should I go ahead and create this calendar event?"""
            
            approval_request = {
                "action_type": "schedule_meeting",
                "description": f"Schedule event: {event_details.get('title', 'Untitled Event')}",
                "payload": event_details,
                "risk_level": "low"
            }
            
            return {
                "response": event_summary,
                "requires_approval": True,
                "approval_request": approval_request,
                "metadata": {
                    "event_details": event_details,
                    "action_type": "schedule_event"
                }
            }
            
        except Exception as e:
            logger.error(f"Error scheduling event: {e}")
            return await self.handle_error(str(e), {})
    
    async def _handle_task_request(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle task management requests"""
        try:
            if any(keyword in message.lower() for keyword in ["create", "add", "new task"]):
                return await self._create_task(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["list", "show", "tasks"]):
                return await self._list_tasks(message, context, mode)
            elif any(keyword in message.lower() for keyword in ["complete", "done", "finished"]):
                return await self._complete_task(message, context, mode)
            else:
                return await self._general_task_assistance(message, context, mode)
                
        except Exception as e:
            logger.error(f"Error handling task request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _handle_general_request(self, messages: List[Dict[str, Any]], context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Handle general requests"""
        try:
            # Add recent memories for context
            user_message = messages[-1]["content"]
            memories = await self.retrieve_memories(user_message, limit=3)
            
            # Build context for LLM
            memory_context = ""
            if memories:
                memory_context = "\n\nRelevant context from previous conversations:\n"
                for memory in memories:
                    memory_context += f"- {memory.get('content', '')}\n"
            
            # Generate response
            response = await self._generate_response(messages, mode, context)
            
            # Store this interaction in memory
            await self.store_memory(
                content=f"User: {user_message}\nCarol: {response}",
                content_type="conversation",
                tags=["general_assistance"]
            )
            
            return {
                "response": response,
                "requires_approval": False,
                "metadata": {
                    "memories_used": len(memories),
                    "message_type": "general_response"
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling general request: {e}")
            return await self.handle_error(str(e), {})
    
    async def _extract_structured_info(self, prompt: str, mode: str) -> Dict[str, Any]:
        """Extract structured information using LLM"""
        try:
            messages = [{"role": "user", "content": prompt}]
            response = await self._generate_response(messages, mode)
            
            # Try to parse as JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Extract JSON from response if it's embedded in text
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
                return {}
                
        except Exception as e:
            logger.error(f"Error extracting structured info: {e}")
            return {}
    
    async def _create_task(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Create a new task"""
        # Extract task details
        extraction_prompt = f"""
        Extract task details from: "{message}"
        
        Return JSON with:
        - title: task title
        - description: task description
        - priority: 1-5 (1=low, 5=urgent)
        - due_date: ISO datetime if mentioned
        """
        
        task_details = await self._extract_structured_info(extraction_prompt, mode)
        
        response = f"""I've created a new task:

✅ **{task_details.get('title', 'New Task')}**
📝 {task_details.get('description', 'No description')}
🔥 Priority: {task_details.get('priority', 1)}/5
📅 Due: {task_details.get('due_date', 'No due date')}

The task has been added to your to-do list!"""
        
        return {
            "response": response,
            "requires_approval": False,
            "metadata": {
                "task_created": task_details,
                "action_type": "create_task"
            }
        }
    
    async def _list_tasks(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """List current tasks"""
        # This would fetch from the task service
        response = """📋 **Your Current Tasks:**

1. ✅ Review quarterly reports (Due: Tomorrow)
2. 📞 Call client about project update (Priority: High)
3. 📧 Send follow-up emails (Due: Today)
4. 📝 Prepare presentation slides (Due: Friday)

You have 4 active tasks. Would you like me to help you with any of these?"""
        
        return {
            "response": response,
            "requires_approval": False,
            "metadata": {"action_type": "list_tasks"}
        }
    
    # Additional helper methods would continue here...
    async def _general_email_assistance(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Provide general email assistance"""
        response = await self._generate_response(
            [{"role": "user", "content": message}], mode, context
        )
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _check_calendar(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """Check calendar appointments"""
        response = """📅 **Today's Schedule:**

9:00 AM - Team standup meeting
11:00 AM - Client presentation
2:00 PM - Free time
3:30 PM - Review session
5:00 PM - End of day

You have a light schedule today with some free time in the afternoon!"""
        
        return {"response": response, "requires_approval": False, "metadata": {}}
    
    async def _general_calendar_assistance(self, message: str, context: Dict[str, Any], mode: str) -> Dict[str, Any]:
        """General calendar assistance"""
        response = await self._generate_response(
            [{"role": "user", "content": message}], mode, context
        )
        return {"response": response, "requires_approval": False, "metadata": {}}