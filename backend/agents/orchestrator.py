from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from typing import Dict, Any, Optional, AsyncGenerator, List
import asyncio
import json
from datetime import datetime
import logging

from agents.carol import CarolAgent
from agents.alex import AlexAgent
from agents.sofia import SofiaAgent
from agents.morgan import MorganAgent
from agents.judy import JudyAgent
from core.memory_broker import MemoryBroker
from models.schemas import ChatRequest, StreamChunk, AgentConfig
from utils.intent_detection import IntentDetector

logger = logging.getLogger(__name__)

class ConversationState:
    """State management for conversation flow"""
    
    def __init__(self):
        self.messages: List[Dict[str, Any]] = []
        self.current_agent: Optional[str] = None
        self.intent: Optional[str] = None
        self.context: Dict[str, Any] = {}
        self.requires_approval: bool = False
        self.approval_request: Optional[Dict[str, Any]] = None
        self.user_id: Optional[str] = None
        self.session_id: Optional[str] = None
        self.mode: str = "online"
        self.metadata: Dict[str, Any] = {}

class AgentOrchestrator:
    """Main orchestrator for managing multiple agents using LangGraph"""
    
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.intent_detector = IntentDetector()
        self.memory_broker: Optional[MemoryBroker] = None
        self.graph = None
        self.checkpointer = MemorySaver()
        
        # Agent configurations
        self.agent_configs = {
            "carol": {
                "name": "Carol Garcia",
                "nickname": "Carol",
                "description": "Executive assistant and main coordinator",
                "persona": "Professional, organized, and proactive executive assistant",
                "voice_id": "EXAVITQu4vr4xnSDxMaL",
                "capabilities": [
                    {"name": "email_management", "description": "Send and manage emails", "enabled": True},
                    {"name": "task_coordination", "description": "Coordinate tasks between agents", "enabled": True},
                    {"name": "general_assistance", "description": "General personal assistance", "enabled": True}
                ]
            },
            "alex": {
                "name": "Alex",
                "nickname": "Alex",
                "description": "System monitoring and operations specialist",
                "persona": "Technical, security-conscious, and methodical system administrator",
                "voice_id": "ErXwobaYiN019PkySvjV",
                "capabilities": [
                    {"name": "system_monitoring", "description": "Monitor system health and performance", "enabled": True},
                    {"name": "command_execution", "description": "Execute approved system commands", "enabled": True},
                    {"name": "security_analysis", "description": "Analyze security threats and vulnerabilities", "enabled": True}
                ]
            },
            "sofia": {
                "name": "Sofia",
                "nickname": "Sofia",
                "description": "Knowledge management and content creation specialist",
                "persona": "Intellectual, thorough, and articulate knowledge worker",
                "voice_id": "21m00Tcm4TlvDq8ikWAM",
                "capabilities": [
                    {"name": "document_processing", "description": "Process and summarize documents", "enabled": True},
                    {"name": "knowledge_base", "description": "Maintain and query knowledge base", "enabled": True},
                    {"name": "content_creation", "description": "Generate essays and reports", "enabled": True}
                ]
            },
            "morgan": {
                "name": "Morgan",
                "nickname": "Morgan",
                "description": "Financial analysis and market intelligence specialist",
                "persona": "Analytical, data-driven, and financially astute advisor",
                "voice_id": "VR6AewLTigWG4xSOukaG",
                "capabilities": [
                    {"name": "market_analysis", "description": "Analyze financial markets and trends", "enabled": True},
                    {"name": "stock_research", "description": "Research stocks and investments", "enabled": True},
                    {"name": "financial_reporting", "description": "Generate financial reports and insights", "enabled": True}
                ]
            },
            "judy": {
                "name": "Judy",
                "nickname": "Judy",
                "description": "Decision validation and consensus specialist",
                "persona": "Impartial, thorough, and discerning judge",
                "voice_id": "AZnzlk1XvdvUeBnXmlld",
                "capabilities": [
                    {"name": "response_validation", "description": "Validate responses from multiple LLMs", "enabled": True},
                    {"name": "consensus_building", "description": "Build consensus from multiple sources", "enabled": True},
                    {"name": "risk_assessment", "description": "Assess risk levels for sensitive actions", "enabled": True}
                ]
            }
        }
    
    async def initialize(self):
        """Initialize the orchestrator and all agents"""
        logger.info("Initializing Agent Orchestrator...")
        
        # Initialize agents
        self.agents["carol"] = CarolAgent()
        self.agents["alex"] = AlexAgent()
        self.agents["sofia"] = SofiaAgent()
        self.agents["morgan"] = MorganAgent()
        self.agents["judy"] = JudyAgent()
        
        # Initialize all agents
        for agent_id, agent in self.agents.items():
            await agent.initialize()
            logger.info(f"Initialized agent: {agent_id}")
        
        # Build the conversation graph
        self._build_graph()
        
        logger.info("Agent Orchestrator initialized successfully")
    
    def _build_graph(self):
        """Build the LangGraph conversation flow"""
        workflow = StateGraph(ConversationState)
        
        # Add nodes for each step in the conversation flow
        workflow.add_node("detect_intent", self._detect_intent)
        workflow.add_node("route_to_agent", self._route_to_agent)
        workflow.add_node("process_with_agent", self._process_with_agent)
        workflow.add_node("request_approval", self._request_approval)
        workflow.add_node("validate_with_judy", self._validate_with_judy)
        workflow.add_node("finalize_response", self._finalize_response)
        
        # Define the conversation flow
        workflow.set_entry_point("detect_intent")
        
        workflow.add_edge("detect_intent", "route_to_agent")
        workflow.add_edge("route_to_agent", "process_with_agent")
        
        # Conditional edges for approval flow
        workflow.add_conditional_edges(
            "process_with_agent",
            self._should_request_approval,
            {
                "approval_required": "request_approval",
                "validation_required": "validate_with_judy",
                "finalize": "finalize_response"
            }
        )
        
        workflow.add_edge("request_approval", "validate_with_judy")
        workflow.add_edge("validate_with_judy", "finalize_response")
        workflow.add_edge("finalize_response", END)
        
        # Compile the graph
        self.graph = workflow.compile(checkpointer=self.checkpointer)
    
    async def _detect_intent(self, state: ConversationState) -> ConversationState:
        """Detect user intent from the message"""
        if not state.messages:
            return state
            
        user_message = state.messages[-1]["content"]
        intent_result = await self.intent_detector.detect_intent(user_message)
        
        state.intent = intent_result["intent"]
        state.context.update(intent_result.get("entities", {}))
        
        logger.info(f"Detected intent: {state.intent}")
        return state
    
    async def _route_to_agent(self, state: ConversationState) -> ConversationState:
        """Route the conversation to the appropriate agent"""
        # If agent is already specified, use it
        if state.current_agent:
            return state
        
        # Route based on intent
        agent_routing = {
            "email": "carol",
            "calendar": "carol",
            "task_management": "carol",
            "system_monitoring": "alex",
            "system_command": "alex",
            "document_processing": "sofia",
            "knowledge_query": "sofia",
            "content_generation": "sofia",
            "financial_analysis": "morgan",
            "market_data": "morgan",
            "investment_advice": "morgan",
            "validation_request": "judy",
            "consensus_building": "judy",
            "general": "carol"
        }
        
        state.current_agent = agent_routing.get(state.intent, "carol")
        logger.info(f"Routing to agent: {state.current_agent}")
        
        return state
    
    async def _process_with_agent(self, state: ConversationState) -> ConversationState:
        """Process the message with the selected agent"""
        try:
            agent = self.agents.get(state.current_agent)
            if not agent:
                logger.error(f"Agent {state.current_agent} not found")
                state.context["error"] = f"Agent {state.current_agent} not available"
                return state
            
            # Process message with agent
            result = await agent.process_message({
                "messages": state.messages,
                "intent": state.intent,
                "context": state.context,
                "mode": state.mode,
                "user_id": state.user_id,
                "session_id": state.session_id
            })
            
            # Update state with result
            state.context.update(result.get("metadata", {}))
            state.requires_approval = result.get("requires_approval", False)
            
            if state.requires_approval:
                state.approval_request = result.get("approval_request")
            
            # Store the agent response
            state.context["agent_response"] = result.get("response", "")
            
            return state
            
        except Exception as e:
            logger.error(f"Error processing with agent {state.current_agent}: {e}")
            state.context["error"] = str(e)
            return state
    
    def _should_request_approval(self, state: ConversationState) -> str:
        """Determine if approval is required"""
        if state.context.get("error"):
            return "finalize"
        
        if state.requires_approval:
            return "approval_required"
        
        # Check if validation is needed (sensitive queries)
        sensitive_intents = ["validation_request", "consensus_building"]
        if state.intent in sensitive_intents:
            return "validation_required"
        
        return "finalize"
    
    async def _request_approval(self, state: ConversationState) -> ConversationState:
        """Request user approval for sensitive actions"""
        try:
            if not state.approval_request:
                logger.warning("Approval requested but no approval request found")
                return state
            
            # Store approval request for UI
            state.context["pending_approval"] = {
                "approval_id": f"approval_{datetime.utcnow().timestamp()}",
                "request": state.approval_request,
                "created_at": datetime.utcnow().isoformat()
            }
            
            logger.info(f"Approval requested for action: {state.approval_request.get('action_type')}")
            
        except Exception as e:
            logger.error(f"Error requesting approval: {e}")
            state.context["error"] = f"Approval request failed: {str(e)}"
        
        return state
    
    async def _validate_with_judy(self, state: ConversationState) -> ConversationState:
        """Validate response with Judy agent"""
        try:
            judy = self.agents.get("judy")
            if not judy:
                logger.warning("Judy agent not available for validation")
                return state
            
            # Prepare validation context
            validation_context = {
                "original_query": state.messages[-1]["content"] if state.messages else "",
                "agent_response": state.context.get("agent_response", ""),
                "responding_agent": state.current_agent,
                "intent": state.intent
            }
            
            # Get Judy's validation
            validation_result = await judy.validate_response(validation_context)
            
            # Update context with validation
            state.context["validation"] = validation_result
            
            logger.info(f"Validation completed with confidence: {validation_result.get('confidence_score', 0)}")
            
        except Exception as e:
            logger.error(f"Error in validation: {e}")
            state.context["validation_error"] = str(e)
        
        return state
    
    async def _finalize_response(self, state: ConversationState) -> ConversationState:
        """Finalize the response"""
        try:
            # If there's an error, create error response
            if state.context.get("error"):
                state.context["final_response"] = f"I encountered an error: {state.context['error']}"
            else:
                state.context["final_response"] = state.context.get("agent_response", "I'm sorry, I couldn't process your request.")
            
            # Add validation info if available
            validation = state.context.get("validation")
            if validation and validation.get("confidence_score", 1.0) < 0.7:
                state.context["final_response"] += f"\n\n*Note: This response has been validated with {validation['confidence_score']:.0%} confidence.*"
            
            # Store conversation in memory
            if self.memory_broker:
                await self.memory_broker.store_conversation(
                    agent_id=state.current_agent,
                    session_id=state.session_id,
                    messages=state.messages,
                    metadata=state.context
                )
            
        except Exception as e:
            logger.error(f"Error finalizing response: {e}")
            state.context["final_response"] = "I encountered an error while processing your request."
        
        return state
    
    async def process_message(
        self,
        message: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        mode: str = "online",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a message through the orchestration graph"""
        try:
            # Create initial state
            state = ConversationState()
            state.messages = [{"role": "user", "content": message, "timestamp": datetime.utcnow().isoformat()}]
            state.current_agent = agent_id
            state.session_id = session_id or f"session_{datetime.utcnow().timestamp()}"
            state.mode = mode
            state.user_id = user_id
            
            # Process through graph
            if self.graph:
                final_state = await self.graph.ainvoke(state, config={"thread_id": state.session_id})
                
                return {
                    "message": final_state.context.get("final_response", "No response generated"),
                    "agent_id": final_state.current_agent,
                    "session_id": final_state.session_id,
                    "metadata": final_state.context,
                    "requires_approval": final_state.requires_approval
                }
            else:
                # Fallback if graph not initialized
                return await self._fallback_processing(message, agent_id, mode)
                
        except Exception as e:
            logger.error(f"Error in process_message: {e}")
            return {
                "message": f"I encountered an error processing your request: {str(e)}",
                "agent_id": agent_id or "carol",
                "session_id": session_id or f"session_{datetime.utcnow().timestamp()}",
                "metadata": {"error": True},
                "requires_approval": False
            }
    
    async def process_stream(
        self,
        message: str,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        mode: str = "online",
        user_id: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Process message with streaming response"""
        try:
            # Start processing
            yield {
                "type": "start",
                "content": "",
                "agent_id": agent_id or "carol",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Process message
            result = await self.process_message(message, agent_id, session_id, mode, user_id)
            
            # Stream the response in chunks
            response_text = result["message"]
            chunk_size = 10  # Words per chunk
            words = response_text.split()
            
            for i in range(0, len(words), chunk_size):
                chunk = " ".join(words[i:i + chunk_size])
                yield {
                    "type": "chunk",
                    "content": chunk + (" " if i + chunk_size < len(words) else ""),
                    "agent_id": result["agent_id"],
                    "session_id": result["session_id"],
                    "timestamp": datetime.utcnow().isoformat()
                }
                
                # Small delay for streaming effect
                await asyncio.sleep(0.1)
            
            # End marker
            yield {
                "type": "end",
                "content": "",
                "agent_id": result["agent_id"],
                "session_id": result["session_id"],
                "timestamp": datetime.utcnow().isoformat(),
                "metadata": result.get("metadata", {})
            }
            
        except Exception as e:
            logger.error(f"Error in process_stream: {e}")
            yield {
                "type": "error",
                "content": f"Stream processing error: {str(e)}",
                "agent_id": agent_id or "carol",
                "session_id": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    async def _fallback_processing(self, message: str, agent_id: Optional[str], mode: str) -> Dict[str, Any]:
        """Fallback processing if graph fails"""
        try:
            # Default to Carol if no agent specified
            target_agent_id = agent_id or "carol"
            agent = self.agents.get(target_agent_id)
            
            if not agent:
                target_agent_id = "carol"
                agent = self.agents.get("carol")
            
            if not agent:
                raise Exception("No agents available")
            
            # Process with agent directly
            result = await agent.process_message({
                "messages": [{"role": "user", "content": message}],
                "context": {},
                "mode": mode
            })
            
            return {
                "message": result.get("response", "No response generated"),
                "agent_id": target_agent_id,
                "session_id": f"fallback_{datetime.utcnow().timestamp()}",
                "metadata": result.get("metadata", {}),
                "requires_approval": result.get("requires_approval", False)
            }
            
        except Exception as e:
            logger.error(f"Error in fallback processing: {e}")
            return {
                "message": "I'm currently experiencing technical difficulties. Please try again later.",
                "agent_id": "carol",
                "session_id": f"error_{datetime.utcnow().timestamp()}",
                "metadata": {"fallback_error": str(e)},
                "requires_approval": False
            }
    
    def get_agent_configs(self) -> Dict[str, Any]:
        """Get all agent configurations"""
        return self.agent_configs
    
    async def update_agent_config(self, agent_id: str, config: AgentConfig) -> bool:
        """Update agent configuration"""
        try:
            if agent_id in self.agent_configs:
                self.agent_configs[agent_id].update(config.dict(exclude_unset=True))
                
                # Update the actual agent if it exists
                if agent_id in self.agents:
                    await self.agents[agent_id].update_config(config.dict(exclude_unset=True))
                
                logger.info(f"Updated config for agent: {agent_id}")
                return True
            else:
                logger.warning(f"Agent {agent_id} not found for config update")
                return False
                
        except Exception as e:
            logger.error(f"Error updating agent config: {e}")
            return False
    
    async def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents"""
        status = {}
        
        for agent_id, agent in self.agents.items():
            try:
                agent_status = await agent.get_status()
                status[agent_id] = agent_status
            except Exception as e:
                status[agent_id] = {
                    "agent_id": agent_id,
                    "error": str(e),
                    "is_initialized": False
                }
        
        return status
    
    async def cleanup(self):
        """Clean up orchestrator resources"""
        try:
            # Cleanup all agents
            for agent_id, agent in self.agents.items():
                try:
                    await agent.shutdown()
                    logger.info(f"Agent {agent_id} shut down successfully")
                except Exception as e:
                    logger.error(f"Error shutting down agent {agent_id}: {e}")
            
            # Cleanup memory broker
            if self.memory_broker:
                await self.memory_broker.cleanup()
            
            logger.info("Agent Orchestrator cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during orchestrator cleanup: {e}")