from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

from middleware.auth import get_current_active_user
from models.database import User
from models.schemas import AgentConfig, AgentStatus, AgentResponse
from agents.orchestrator import AgentOrchestrator

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=Dict[str, Any])
async def list_agents(
    current_user: User = Depends(get_current_active_user)
):
    """List all available agents with their configurations"""
    try:
        from main import app
        orchestrator: AgentOrchestrator = app.state.orchestrator
        
        agent_configs = orchestrator.get_agent_configs()
        agent_status = await orchestrator.get_agent_status()
        
        # Combine configs with status
        agents_info = {}
        for agent_id, config in agent_configs.items():
            agents_info[agent_id] = {
                **config,
                "status": agent_status.get(agent_id, {"is_initialized": False})
            }
        
        return {
            "agents": agents_info,
            "total_count": len(agents_info),
            "online_count": len([a for a in agent_status.values() if a.get("is_initialized")])
        }
        
    except Exception as e:
        logger.error(f"Error listing agents: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agents: {str(e)}"
        )

@router.get("/{agent_id}", response_model=Dict[str, Any])
async def get_agent(
    agent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get specific agent configuration and status"""
    try:
        from main import app
        orchestrator: AgentOrchestrator = app.state.orchestrator
        
        agent_configs = orchestrator.get_agent_configs()
        if agent_id not in agent_configs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        agent_status = await orchestrator.get_agent_status()
        
        return {
            **agent_configs[agent_id],
            "status": agent_status.get(agent_id, {"is_initialized": False})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve agent: {str(e)}"
        )

@router.put("/{agent_id}", response_model=Dict[str, Any])
async def update_agent_config(
    agent_id: str,
    config: AgentConfig,
    current_user: User = Depends(get_current_active_user)
):
    """Update agent configuration"""
    try:
        from main import app
        orchestrator: AgentOrchestrator = app.state.orchestrator
        
        success = await orchestrator.update_agent_config(agent_id, config)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        return {
            "message": f"Agent {agent_id} configuration updated successfully",
            "agent_id": agent_id,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update agent: {str(e)}"
        )

@router.get("/{agent_id}/status", response_model=AgentStatus)
async def get_agent_status(
    agent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get detailed agent status"""
    try:
        from main import app
        orchestrator: AgentOrchestrator = app.state.orchestrator
        
        if agent_id not in orchestrator.agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        agent = orchestrator.agents[agent_id]
        status = await agent.get_status()
        
        return AgentStatus(**status)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting status for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent status: {str(e)}"
        )

@router.post("/{agent_id}/chat", response_model=AgentResponse)
async def chat_with_agent(
    agent_id: str,
    message: str,
    session_id: Optional[str] = None,
    mode: str = "online",
    current_user: User = Depends(get_current_active_user)
):
    """Chat directly with a specific agent"""
    try:
        from main import app
        orchestrator: AgentOrchestrator = app.state.orchestrator
        
        if agent_id not in orchestrator.agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        response = await orchestrator.process_message(
            message=message,
            agent_id=agent_id,
            session_id=session_id,
            mode=mode,
            user_id=str(current_user.id)
        )
        
        return AgentResponse(
            message=response["message"],
            agent_id=response["agent_id"],
            session_id=response["session_id"],
            timestamp=datetime.utcnow(),
            metadata=response.get("metadata", {}),
            requires_approval=response.get("requires_approval", False)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error chatting with agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to chat with agent: {str(e)}"
        )

@router.post("/{agent_id}/reset")
async def reset_agent(
    agent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Reset agent state and memory"""
    try:
        from main import app
        orchestrator: AgentOrchestrator = app.state.orchestrator
        
        if agent_id not in orchestrator.agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        agent = orchestrator.agents[agent_id]
        
        # Reset agent state
        agent.message_count = 0
        agent.error_count = 0
        agent.last_activity = None
        
        # Clear agent memory
        if agent.memory_manager:
            # Clear conversation history for this agent
            pass  # Implement based on memory manager capabilities
        
        return {
            "message": f"Agent {agent_id} reset successfully",
            "agent_id": agent_id,
            "reset_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset agent: {str(e)}"
        )

@router.get("/{agent_id}/metrics")
async def get_agent_metrics(
    agent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get agent performance metrics"""
    try:
        from main import app
        orchestrator: AgentOrchestrator = app.state.orchestrator
        
        if agent_id not in orchestrator.agents:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        agent = orchestrator.agents[agent_id]
        status = await agent.get_status()
        
        return {
            "agent_id": agent_id,
            "message_count": status.get("message_count", 0),
            "error_count": status.get("error_count", 0),
            "error_rate": status.get("error_count", 0) / max(status.get("message_count", 1), 1),
            "last_activity": status.get("last_activity"),
            "uptime": datetime.utcnow().isoformat() if status.get("is_initialized") else None,
            "capabilities": status.get("capabilities", [])
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metrics for agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get agent metrics: {str(e)}"
        )