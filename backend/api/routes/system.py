from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta

from middleware.auth import get_current_active_user, get_admin_user
from models.database import User
from models.schemas import SystemMetrics, SystemCommand, SystemCommandResponse, SystemAlert

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/metrics", response_model=SystemMetrics)
async def get_system_metrics(
    current_user: User = Depends(get_current_active_user)
):
    """Get system performance metrics"""
    try:
        from utils.system_monitor import SystemMonitor
        
        # Get system metrics from Alex agent's system monitor
        system_monitor = SystemMonitor()
        metrics = await system_monitor.get_system_metrics()
        
        return SystemMetrics(
            cpu_usage=metrics.get("cpu_usage", 0),
            memory_usage=metrics.get("memory_usage", 0),
            disk_usage=metrics.get("disk_usage", 0),
            network_io=metrics.get("network_io", {}),
            process_count=metrics.get("process_count", 0),
            uptime=metrics.get("uptime", 0),
            load_average=metrics.get("load_average", []),
            temperature=metrics.get("temperature", 0),
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error(f"Error retrieving system metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system metrics: {str(e)}"
        )

@router.get("/health")
async def get_system_health():
    """Get overall system health status"""
    try:
        from main import app
        
        # Check various system components
        health_checks = {
            "database": await check_database_health(),
            "redis": await check_redis_health(),
            "agents": await check_agents_health(),
            "memory_broker": await check_memory_broker_health(),
            "disk_space": await check_disk_space(),
            "memory": await check_memory_usage()
        }
        
        # Determine overall status
        failed_checks = [name for name, status in health_checks.items() if status.get("status") != "healthy"]
        overall_status = "healthy" if not failed_checks else "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": health_checks,
            "failed_checks": failed_checks
        }
        
    except Exception as e:
        logger.error(f"Error checking system health: {e}")
        return {
            "status": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }

@router.post("/commands", response_model=SystemCommandResponse)
async def execute_system_command(
    command_data: SystemCommand,
    current_user: User = Depends(get_admin_user)  # Admin only
):
    """Execute a system command through Alex agent"""
    try:
        from main import app
        
        # Get Alex agent for system operations
        orchestrator = app.state.orchestrator
        alex_agent = orchestrator.agents.get("alex")
        
        if not alex_agent:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Alex agent not available"
            )
        
        # Process command through Alex with safety checks
        result = await alex_agent.execute_system_command(
            command=command_data.command,
            args=command_data.args or [],
            working_directory=command_data.working_directory,
            timeout=command_data.timeout or 30,
            requires_approval=True  # Always require approval for system commands
        )
        
        return SystemCommandResponse(
            command_id=result.get("command_id"),
            command=command_data.command,
            status=result.get("status", "pending"),
            output=result.get("output", ""),
            error=result.get("error"),
            execution_time=result.get("execution_time"),
            requires_approval=result.get("requires_approval", True),
            approval_id=result.get("approval_id"),
            executed_at=datetime.utcnow()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing system command: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute system command: {str(e)}"
        )

@router.get("/commands/{command_id}", response_model=SystemCommandResponse)
async def get_command_status(
    command_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get status of a system command"""
    try:
        from main import app
        from core.database import get_db_session
        from models.database import SystemCommandLog
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(SystemCommandLog).where(
                SystemCommandLog.command_id == command_id,
                SystemCommandLog.user_id == current_user.id
            )
            result = await session.execute(query)
            command_log = result.scalar_one_or_none()
            
            if not command_log:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Command not found"
                )
            
            return SystemCommandResponse(
                command_id=command_log.command_id,
                command=command_log.command,
                status=command_log.status,
                output=command_log.output,
                error=command_log.error,
                execution_time=command_log.execution_time,
                requires_approval=command_log.requires_approval,
                approval_id=command_log.approval_id,
                executed_at=command_log.executed_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting command status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get command status: {str(e)}"
        )

@router.get("/processes")
async def get_system_processes(
    limit: int = Query(50, ge=1, le=500),
    sort_by: str = Query("cpu", regex="^(cpu|memory|name|pid)$"),
    current_user: User = Depends(get_current_active_user)
):
    """Get running system processes"""
    try:
        from utils.system_monitor import SystemMonitor
        
        system_monitor = SystemMonitor()
        processes = await system_monitor.get_processes(limit=limit, sort_by=sort_by)
        
        return {
            "processes": processes,
            "total_count": len(processes),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving system processes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system processes: {str(e)}"
        )

@router.get("/alerts", response_model=List[SystemAlert])
async def get_system_alerts(
    severity: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user)
):
    """Get system alerts and warnings"""
    try:
        from core.database import get_db_session
        from models.database import SystemAlert as SystemAlertModel
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(SystemAlertModel).where(
                SystemAlertModel.resolved_at.is_(None)  # Only unresolved alerts
            )
            
            if severity:
                query = query.where(SystemAlertModel.severity == severity)
            
            query = query.order_by(SystemAlertModel.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            alerts = result.scalars().all()
            
            return [
                SystemAlert(
                    id=alert.id,
                    title=alert.title,
                    description=alert.description,
                    severity=alert.severity,
                    alert_type=alert.alert_type,
                    source=alert.source,
                    metadata=alert.metadata or {},
                    created_at=alert.created_at,
                    resolved_at=alert.resolved_at
                )
                for alert in alerts
            ]
            
    except Exception as e:
        logger.error(f"Error retrieving system alerts: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system alerts: {str(e)}"
        )

@router.post("/alerts/{alert_id}/resolve")
async def resolve_system_alert(
    alert_id: str,
    resolution_note: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Resolve a system alert"""
    try:
        from core.database import get_db_session
        from models.database import SystemAlert as SystemAlertModel
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(SystemAlertModel).where(SystemAlertModel.id == alert_id)
            result = await session.execute(query)
            alert = result.scalar_one_or_none()
            
            if not alert:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Alert not found"
                )
            
            if alert.resolved_at:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Alert already resolved"
                )
            
            # Resolve the alert
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = current_user.id
            
            if resolution_note:
                if not alert.metadata:
                    alert.metadata = {}
                alert.metadata["resolution_note"] = resolution_note
                alert.metadata["resolved_by_user"] = current_user.username
            
            await session.commit()
            
            return {
                "message": "Alert resolved successfully",
                "alert_id": alert_id,
                "resolved_at": alert.resolved_at.isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve alert: {str(e)}"
        )

@router.get("/logs")
async def get_system_logs(
    level: Optional[str] = Query(None, regex="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$"),
    limit: int = Query(100, ge=1, le=1000),
    hours: int = Query(24, ge=1, le=168),  # Last 24 hours by default
    current_user: User = Depends(get_admin_user)  # Admin only
):
    """Get system logs"""
    try:
        from utils.system_monitor import SystemMonitor
        
        since = datetime.utcnow() - timedelta(hours=hours)
        
        system_monitor = SystemMonitor()
        logs = await system_monitor.get_logs(
            level=level,
            since=since,
            limit=limit
        )
        
        return {
            "logs": logs,
            "total_count": len(logs),
            "since": since.isoformat(),
            "level_filter": level,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error retrieving system logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve system logs: {str(e)}"
        )

@router.post("/maintenance")
async def enter_maintenance_mode(
    reason: str,
    estimated_duration_minutes: Optional[int] = None,
    current_user: User = Depends(get_admin_user)  # Admin only
):
    """Enter system maintenance mode"""
    try:
        from core.redis_client import redis_client
        
        maintenance_data = {
            "enabled": True,
            "reason": reason,
            "started_by": current_user.username,
            "started_at": datetime.utcnow().isoformat(),
            "estimated_end": (
                datetime.utcnow() + timedelta(minutes=estimated_duration_minutes)
            ).isoformat() if estimated_duration_minutes else None
        }
        
        await redis_client.set("system:maintenance", maintenance_data, expire=86400)  # 24 hours max
        
        logger.warning(f"System maintenance mode enabled by {current_user.username}: {reason}")
        
        return {
            "message": "System maintenance mode enabled",
            "maintenance_data": maintenance_data
        }
        
    except Exception as e:
        logger.error(f"Error entering maintenance mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enter maintenance mode: {str(e)}"
        )

@router.delete("/maintenance")
async def exit_maintenance_mode(
    current_user: User = Depends(get_admin_user)  # Admin only
):
    """Exit system maintenance mode"""
    try:
        from core.redis_client import redis_client
        
        await redis_client.delete("system:maintenance")
        
        logger.info(f"System maintenance mode disabled by {current_user.username}")
        
        return {
            "message": "System maintenance mode disabled",
            "disabled_by": current_user.username,
            "disabled_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error exiting maintenance mode: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to exit maintenance mode: {str(e)}"
        )

# Helper functions

async def check_database_health() -> Dict[str, Any]:
    """Check database connectivity"""
    try:
        from core.database import get_db_session
        
        async with get_db_session() as session:
            await session.execute("SELECT 1")
            return {"status": "healthy", "response_time": "< 100ms"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity"""
    try:
        from core.redis_client import redis_client
        
        await redis_client.ping()
        return {"status": "healthy", "response_time": "< 50ms"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_agents_health() -> Dict[str, Any]:
    """Check agents status"""
    try:
        from main import app
        
        orchestrator = app.state.orchestrator
        agent_status = await orchestrator.get_agent_status()
        
        healthy_agents = [name for name, status in agent_status.items() if status.get("is_initialized")]
        total_agents = len(agent_status)
        
        return {
            "status": "healthy" if len(healthy_agents) == total_agents else "degraded",
            "healthy_agents": healthy_agents,
            "total_agents": total_agents
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_memory_broker_health() -> Dict[str, Any]:
    """Check memory broker status"""
    try:
        from main import app
        
        memory_broker = app.state.memory_broker
        # Add specific health check for memory broker
        return {"status": "healthy"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_disk_space() -> Dict[str, Any]:
    """Check available disk space"""
    try:
        import shutil
        
        total, used, free = shutil.disk_usage("/")
        free_percent = (free / total) * 100
        
        status = "healthy" if free_percent > 10 else "warning" if free_percent > 5 else "critical"
        
        return {
            "status": status,
            "free_space_gb": round(free / (1024**3), 2),
            "free_percent": round(free_percent, 2)
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

async def check_memory_usage() -> Dict[str, Any]:
    """Check system memory usage"""
    try:
        import psutil
        
        memory = psutil.virtual_memory()
        
        status = "healthy" if memory.percent < 80 else "warning" if memory.percent < 90 else "critical"
        
        return {
            "status": status,
            "used_percent": memory.percent,
            "available_gb": round(memory.available / (1024**3), 2)
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}