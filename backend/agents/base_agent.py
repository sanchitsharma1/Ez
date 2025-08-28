from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import asyncio
import logging
from datetime import datetime
import openai
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings
from utils.llm_client import LLMClient
from utils.memory_manager import MemoryManager

logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    """Base class for all agents"""
    
    def __init__(self, agent_id: str, name: str, persona: str):
        self.agent_id = agent_id
        self.name = name
        self.persona = persona
        self.llm_client: Optional[LLMClient] = None
        self.memory_manager: Optional[MemoryManager] = None
        self.config: Dict[str, Any] = {}
        self.is_initialized = False
        self.message_count = 0
        self.error_count = 0
        self.last_activity: Optional[datetime] = None
        
        # Agent-specific capabilities
        self.capabilities: List[str] = []
        
        # Voice settings
        self.voice_id: Optional[str] = None
        self.voice_settings: Dict[str, Any] = {}
    
    async def initialize(self):
        """Initialize the agent"""
        try:
            # Initialize LLM client
            self.llm_client = LLMClient()
            await self.llm_client.initialize()
            
            # Initialize memory manager
            self.memory_manager = MemoryManager(agent_id=self.agent_id)
            await self.memory_manager.initialize()
            
            # Load agent-specific configuration
            await self._load_config()
            
            # Perform agent-specific initialization
            await self._initialize_agent()
            
            self.is_initialized = True
            logger.info(f"Agent {self.agent_id} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize agent {self.agent_id}: {e}")
            raise
    
    @abstractmethod
    async def _initialize_agent(self):
        """Agent-specific initialization"""
        pass
    
    async def _load_config(self):
        """Load agent configuration"""
        # Load from database or config file
        # This is a placeholder - implement based on your config storage
        pass
    
    @abstractmethod
    async def process_message(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a message and return response"""
        pass
    
    async def _generate_response(
        self,
        messages: List[Dict[str, Any]],
        mode: str = "online",
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate response using LLM"""
        try:
            # Prepare system prompt with persona and context
            system_prompt = self._build_system_prompt(context)
            
            # Format messages for LLM
            formatted_messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if content and role in ["user", "assistant"]:
                    formatted_messages.append({"role": role, "content": content})
            
            # Generate response
            response = await self.llm_client.generate_response(
                messages=formatted_messages,
                mode=mode,
                agent_id=self.agent_id
            )
            
            self.message_count += 1
            self.last_activity = datetime.utcnow()
            
            return response
            
        except Exception as e:
            self.error_count += 1
            logger.error(f"Error generating response for {self.agent_id}: {e}")
            raise
    
    def _build_system_prompt(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Build system prompt for the agent"""
        base_prompt = f"""You are {self.name}, a specialized AI agent with the following persona:

{self.persona}

Your capabilities include:
{', '.join(self.capabilities)}

Current timestamp: {datetime.utcnow().isoformat()}
"""
        
        if context:
            if context.get("intent"):
                base_prompt += f"\nDetected user intent: {context['intent']}"
            
            if context.get("context"):
                base_prompt += f"\nAdditional context: {context['context']}"
            
            if context.get("mode") == "offline":
                base_prompt += "\n\nNote: You are operating in offline mode using local models."
        
        # Add agent-specific instructions
        agent_instructions = self._get_agent_instructions()
        if agent_instructions:
            base_prompt += f"\n\nSpecific instructions:\n{agent_instructions}"
        
        return base_prompt
    
    @abstractmethod
    def _get_agent_instructions(self) -> str:
        """Get agent-specific instructions for the system prompt"""
        pass
    
    async def handle_error(self, error: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle errors gracefully"""
        error_response = f"I apologize, but I encountered an error while processing your request: {error}. Please try again or contact support if the issue persists."
        
        return {
            "response": error_response,
            "requires_approval": False,
            "metadata": {
                "error": True,
                "error_message": error,
                "agent_id": self.agent_id
            }
        }
    
    async def get_status(self) -> Dict[str, Any]:
        """Get agent status"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "is_initialized": self.is_initialized,
            "message_count": self.message_count,
            "error_count": self.error_count,
            "last_activity": self.last_activity.isoformat() if self.last_activity else None,
            "capabilities": self.capabilities
        }
    
    async def update_config(self, config: Dict[str, Any]):
        """Update agent configuration"""
        self.config.update(config)
        
        # Update persona if provided
        if "persona" in config:
            self.persona = config["persona"]
        
        # Update voice settings if provided
        if "voice_id" in config:
            self.voice_id = config["voice_id"]
        
        if "voice_settings" in config:
            self.voice_settings.update(config["voice_settings"])
    
    async def store_memory(self, content: str, content_type: str = "conversation", tags: Optional[List[str]] = None):
        """Store information in agent memory"""
        if self.memory_manager:
            await self.memory_manager.store_memory(
                content=content,
                content_type=content_type,
                tags=tags or [],
                agent_id=self.agent_id
            )
    
    async def retrieve_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant memories"""
        if self.memory_manager:
            return await self.memory_manager.search_memories(query, limit=limit)
        return []
    
    async def shutdown(self):
        """Shutdown the agent gracefully"""
        try:
            if self.memory_manager:
                await self.memory_manager.cleanup()
            
            if self.llm_client:
                await self.llm_client.cleanup()
            
            logger.info(f"Agent {self.agent_id} shutdown successfully")
            
        except Exception as e:
            logger.error(f"Error shutting down agent {self.agent_id}: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _make_api_call(self, url: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None):
        """Make API call with retry logic"""
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers or {})
            response.raise_for_status()
            return response.json()
    
    def _requires_approval(self, action_type: str) -> bool:
        """Check if an action requires user approval"""
        sensitive_actions = [
            "send_email",
            "schedule_meeting",
            "execute_command",
            "delete_file",
            "modify_system",
            "financial_transaction",
            "external_api_call"
        ]
        return action_type in sensitive_actions
    
    def _assess_risk_level(self, action_type: str, payload: Dict[str, Any]) -> str:
        """Assess risk level of an action"""
        critical_actions = ["execute_command", "delete_file", "modify_system", "financial_transaction"]
        high_risk_actions = ["send_email", "schedule_meeting", "external_api_call"]
        medium_risk_actions = ["create_file", "read_file", "search_data"]
        
        if action_type in critical_actions:
            return "critical"
        elif action_type in high_risk_actions:
            return "high"
        elif action_type in medium_risk_actions:
            return "medium"
        else:
            return "low"