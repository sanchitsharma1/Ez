from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import uuid

from middleware.auth import get_current_active_user
from models.database import User
from models.schemas import ApprovalRequest, ApprovalResponse, ApprovalUpdate, ApprovalStats

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/pending", response_model=List[ApprovalResponse])
async def get_pending_approvals(
    agent_id: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None, regex="^(low|medium|high|critical)$"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user)
):
    """Get pending approval requests"""
    try:
        from core.database import get_db_session
        from models.database import Approval, ApprovalStatus
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(Approval).where(
                Approval.user_id == current_user.id,
                Approval.status == ApprovalStatus.PENDING
            )
            
            if agent_id:
                query = query.where(Approval.agent_id == agent_id)
            if action_type:
                query = query.where(Approval.action_type == action_type)
            if risk_level:
                query = query.where(Approval.risk_level == risk_level)
            
            query = query.order_by(Approval.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            approvals = result.scalars().all()
            
            return [
                ApprovalResponse(
                    id=approval.id,
                    agent_id=approval.agent_id,
                    action_type=approval.action_type,
                    description=approval.description,
                    payload=approval.payload or {},
                    risk_level=approval.risk_level,
                    status=approval.status,
                    expires_at=approval.expires_at,
                    judy_verdict=approval.judy_verdict,
                    judy_confidence=approval.judy_confidence,
                    judy_reasoning=approval.judy_reasoning,
                    created_at=approval.created_at,
                    responded_at=approval.responded_at,
                    response_reason=approval.response_reason
                )
                for approval in approvals
            ]
            
    except Exception as e:
        logger.error(f"Error retrieving pending approvals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve pending approvals: {str(e)}"
        )

@router.post("/", response_model=ApprovalResponse)
async def create_approval_request(
    request_data: ApprovalRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new approval request"""
    try:
        from core.database import get_db_session
        from models.database import Approval, ApprovalStatus
        
        async with get_db_session() as session:
            # Create new approval request
            new_approval = Approval(
                id=uuid.uuid4(),
                user_id=current_user.id,
                agent_id=request_data.agent_id,
                action_type=request_data.action_type,
                description=request_data.description,
                payload=request_data.payload or {},
                risk_level=request_data.risk_level,
                status=ApprovalStatus.PENDING,
                expires_at=datetime.utcnow() + timedelta(hours=24),  # Default 24-hour expiry
                created_at=datetime.utcnow()
            )
            
            session.add(new_approval)
            await session.commit()
            await session.refresh(new_approval)
            
            # Request Judy's assessment if it's a sensitive action
            if request_data.risk_level in ["high", "critical"]:
                try:
                    judy_assessment = await request_judy_assessment(new_approval)
                    
                    new_approval.judy_verdict = judy_assessment.get("verdict")
                    new_approval.judy_confidence = judy_assessment.get("confidence_score")
                    new_approval.judy_reasoning = judy_assessment.get("reasoning")
                    
                    await session.commit()
                    
                except Exception as e:
                    logger.warning(f"Failed to get Judy assessment for approval {new_approval.id}: {e}")
            
            # Send notification (this would integrate with WebSocket or push notifications)
            await notify_user_about_approval(current_user, new_approval)
            
            return ApprovalResponse(
                id=new_approval.id,
                agent_id=new_approval.agent_id,
                action_type=new_approval.action_type,
                description=new_approval.description,
                payload=new_approval.payload or {},
                risk_level=new_approval.risk_level,
                status=new_approval.status,
                expires_at=new_approval.expires_at,
                judy_verdict=new_approval.judy_verdict,
                judy_confidence=new_approval.judy_confidence,
                judy_reasoning=new_approval.judy_reasoning,
                created_at=new_approval.created_at,
                responded_at=new_approval.responded_at,
                response_reason=new_approval.response_reason
            )
            
    except Exception as e:
        logger.error(f"Error creating approval request: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create approval request: {str(e)}"
        )

@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific approval request"""
    try:
        from core.database import get_db_session
        from models.database import Approval
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(Approval).where(
                Approval.id == approval_id,
                Approval.user_id == current_user.id
            )
            result = await session.execute(query)
            approval = result.scalar_one_or_none()
            
            if not approval:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Approval request not found"
                )
            
            return ApprovalResponse(
                id=approval.id,
                agent_id=approval.agent_id,
                action_type=approval.action_type,
                description=approval.description,
                payload=approval.payload or {},
                risk_level=approval.risk_level,
                status=approval.status,
                expires_at=approval.expires_at,
                judy_verdict=approval.judy_verdict,
                judy_confidence=approval.judy_confidence,
                judy_reasoning=approval.judy_reasoning,
                created_at=approval.created_at,
                responded_at=approval.responded_at,
                response_reason=approval.response_reason
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving approval {approval_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve approval: {str(e)}"
        )

@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    approval_id: uuid.UUID,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Approve a pending request"""
    try:
        return await respond_to_approval(
            approval_id=approval_id,
            approved=True,
            reason=reason,
            current_user=current_user
        )
        
    except Exception as e:
        logger.error(f"Error approving request {approval_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve request: {str(e)}"
        )

@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    approval_id: uuid.UUID,
    reason: Optional[str] = None,
    current_user: User = Depends(get_current_active_user)
):
    """Reject a pending request"""
    try:
        return await respond_to_approval(
            approval_id=approval_id,
            approved=False,
            reason=reason,
            current_user=current_user
        )
        
    except Exception as e:
        logger.error(f"Error rejecting request {approval_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject request: {str(e)}"
        )

@router.put("/{approval_id}", response_model=ApprovalResponse)
async def update_approval(
    approval_id: uuid.UUID,
    update_data: ApprovalUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """Update an approval request (admin only for some fields)"""
    try:
        from core.database import get_db_session
        from models.database import Approval
        from sqlalchemy import select
        
        async with get_db_session() as session:
            query = select(Approval).where(
                Approval.id == approval_id,
                Approval.user_id == current_user.id
            )
            result = await session.execute(query)
            approval = result.scalar_one_or_none()
            
            if not approval:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Approval request not found"
                )
            
            # Update allowed fields
            if update_data.description is not None:
                approval.description = update_data.description
            
            if update_data.expires_at is not None:
                approval.expires_at = update_data.expires_at
            
            if update_data.payload is not None:
                approval.payload = update_data.payload
            
            await session.commit()
            await session.refresh(approval)
            
            return ApprovalResponse(
                id=approval.id,
                agent_id=approval.agent_id,
                action_type=approval.action_type,
                description=approval.description,
                payload=approval.payload or {},
                risk_level=approval.risk_level,
                status=approval.status,
                expires_at=approval.expires_at,
                judy_verdict=approval.judy_verdict,
                judy_confidence=approval.judy_confidence,
                judy_reasoning=approval.judy_reasoning,
                created_at=approval.created_at,
                responded_at=approval.responded_at,
                response_reason=approval.response_reason
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating approval {approval_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update approval: {str(e)}"
        )

@router.get("/history/all", response_model=List[ApprovalResponse])
async def get_approval_history(
    status: Optional[str] = Query(None, regex="^(pending|approved|rejected|expired)$"),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user)
):
    """Get approval history"""
    try:
        from core.database import get_db_session
        from models.database import Approval, ApprovalStatus
        from sqlalchemy import select
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        async with get_db_session() as session:
            query = select(Approval).where(
                Approval.user_id == current_user.id,
                Approval.created_at >= since_date
            )
            
            if status:
                query = query.where(Approval.status == ApprovalStatus[status.upper()])
            
            query = query.order_by(Approval.created_at.desc()).limit(limit)
            
            result = await session.execute(query)
            approvals = result.scalars().all()
            
            return [
                ApprovalResponse(
                    id=approval.id,
                    agent_id=approval.agent_id,
                    action_type=approval.action_type,
                    description=approval.description,
                    payload=approval.payload or {},
                    risk_level=approval.risk_level,
                    status=approval.status,
                    expires_at=approval.expires_at,
                    judy_verdict=approval.judy_verdict,
                    judy_confidence=approval.judy_confidence,
                    judy_reasoning=approval.judy_reasoning,
                    created_at=approval.created_at,
                    responded_at=approval.responded_at,
                    response_reason=approval.response_reason
                )
                for approval in approvals
            ]
            
    except Exception as e:
        logger.error(f"Error retrieving approval history: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve approval history: {str(e)}"
        )

@router.get("/stats/summary", response_model=ApprovalStats)
async def get_approval_stats(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_active_user)
):
    """Get approval statistics"""
    try:
        from core.database import get_db_session
        from models.database import Approval, ApprovalStatus
        from sqlalchemy import select, func
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        async with get_db_session() as session:
            # Total approvals
            total_query = select(func.count(Approval.id)).where(
                Approval.user_id == current_user.id,
                Approval.created_at >= since_date
            )
            total_result = await session.execute(total_query)
            total_approvals = total_result.scalar()
            
            # Pending approvals
            pending_query = select(func.count(Approval.id)).where(
                Approval.user_id == current_user.id,
                Approval.status == ApprovalStatus.PENDING
            )
            pending_result = await session.execute(pending_query)
            pending_approvals = pending_result.scalar()
            
            # Approvals by status
            status_query = select(Approval.status, func.count(Approval.id)).where(
                Approval.user_id == current_user.id,
                Approval.created_at >= since_date
            ).group_by(Approval.status)
            status_result = await session.execute(status_query)
            approvals_by_status = {status.value: count for status, count in status_result}
            
            # Approvals by agent
            agent_query = select(Approval.agent_id, func.count(Approval.id)).where(
                Approval.user_id == current_user.id,
                Approval.created_at >= since_date
            ).group_by(Approval.agent_id)
            agent_result = await session.execute(agent_query)
            approvals_by_agent = {agent_id: count for agent_id, count in agent_result}
            
            # Approvals by risk level
            risk_query = select(Approval.risk_level, func.count(Approval.id)).where(
                Approval.user_id == current_user.id,
                Approval.created_at >= since_date
            ).group_by(Approval.risk_level)
            risk_result = await session.execute(risk_query)
            approvals_by_risk = {risk_level: count for risk_level, count in risk_result}
            
            # Average response time (in hours)
            response_time_query = select(func.avg(
                func.extract('epoch', Approval.responded_at - Approval.created_at) / 3600
            )).where(
                Approval.user_id == current_user.id,
                Approval.responded_at.is_not(None),
                Approval.created_at >= since_date
            )
            response_time_result = await session.execute(response_time_query)
            avg_response_time = response_time_result.scalar() or 0
            
            return ApprovalStats(
                total_approvals=total_approvals,
                pending_approvals=pending_approvals,
                approvals_by_status=approvals_by_status,
                approvals_by_agent=approvals_by_agent,
                approvals_by_risk=approvals_by_risk,
                average_response_time_hours=round(avg_response_time, 2),
                period_days=days
            )
            
    except Exception as e:
        logger.error(f"Error getting approval stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get approval stats: {str(e)}"
        )

@router.post("/batch/expire")
async def expire_old_approvals(
    hours: int = Query(24, ge=1, le=168),  # Default 24 hours
    current_user: User = Depends(get_current_active_user)
):
    """Expire old pending approvals"""
    try:
        from core.database import get_db_session
        from models.database import Approval, ApprovalStatus
        from sqlalchemy import select, update
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        async with get_db_session() as session:
            # Update expired approvals
            update_query = update(Approval).where(
                Approval.user_id == current_user.id,
                Approval.status == ApprovalStatus.PENDING,
                Approval.created_at < cutoff_time
            ).values(
                status=ApprovalStatus.EXPIRED,
                responded_at=datetime.utcnow(),
                response_reason="Auto-expired due to timeout"
            )
            
            result = await session.execute(update_query)
            expired_count = result.rowcount
            
            await session.commit()
            
            return {
                "message": f"Expired {expired_count} old approval requests",
                "expired_count": expired_count,
                "cutoff_hours": hours,
                "expired_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error expiring old approvals: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to expire old approvals: {str(e)}"
        )

# Helper functions

async def respond_to_approval(
    approval_id: uuid.UUID,
    approved: bool,
    reason: Optional[str],
    current_user: User
) -> ApprovalResponse:
    """Common function to approve or reject requests"""
    from core.database import get_db_session
    from models.database import Approval, ApprovalStatus
    from sqlalchemy import select
    
    async with get_db_session() as session:
        query = select(Approval).where(
            Approval.id == approval_id,
            Approval.user_id == current_user.id
        )
        result = await session.execute(query)
        approval = result.scalar_one_or_none()
        
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Approval request not found"
            )
        
        if approval.status != ApprovalStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot modify approval with status: {approval.status.value}"
            )
        
        # Check if approval has expired
        if approval.expires_at and approval.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Approval request has expired"
            )
        
        # Update approval status
        approval.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        approval.responded_at = datetime.utcnow()
        approval.response_reason = reason
        
        await session.commit()
        
        # Execute the approved action or notify about rejection
        if approved:
            try:
                await execute_approved_action(approval)
            except Exception as e:
                logger.error(f"Failed to execute approved action for {approval_id}: {e}")
                # Don't fail the approval, just log the execution error
        
        # Notify relevant agent about the decision
        await notify_agent_about_approval_decision(approval, approved)
        
        await session.refresh(approval)
        
        return ApprovalResponse(
            id=approval.id,
            agent_id=approval.agent_id,
            action_type=approval.action_type,
            description=approval.description,
            payload=approval.payload or {},
            risk_level=approval.risk_level,
            status=approval.status,
            expires_at=approval.expires_at,
            judy_verdict=approval.judy_verdict,
            judy_confidence=approval.judy_confidence,
            judy_reasoning=approval.judy_reasoning,
            created_at=approval.created_at,
            responded_at=approval.responded_at,
            response_reason=approval.response_reason
        )

async def request_judy_assessment(approval) -> Dict[str, Any]:
    """Request Judy's assessment of an approval request"""
    try:
        from main import app
        
        orchestrator = app.state.orchestrator
        judy_agent = orchestrator.agents.get("judy")
        
        if not judy_agent:
            return {"verdict": "unavailable", "confidence_score": 0.5, "reasoning": "Judy agent not available"}
        
        # Prepare assessment context
        assessment_context = {
            "action_type": approval.action_type,
            "description": approval.description,
            "payload": approval.payload,
            "risk_level": approval.risk_level,
            "agent_id": approval.agent_id
        }
        
        # Get Judy's assessment
        result = await judy_agent.assess_approval_request(assessment_context)
        
        return {
            "verdict": result.get("verdict", "unknown"),
            "confidence_score": result.get("confidence_score", 0.5),
            "reasoning": result.get("reasoning", "No reasoning provided")
        }
        
    except Exception as e:
        logger.error(f"Error getting Judy assessment: {e}")
        return {"verdict": "error", "confidence_score": 0.0, "reasoning": f"Assessment failed: {str(e)}"}

async def notify_user_about_approval(user: User, approval):
    """Notify user about new approval request"""
    try:
        # This would integrate with WebSocket or push notification system
        from utils.websocket_manager import WebSocketManager
        
        websocket_manager = WebSocketManager()
        
        notification = {
            "type": "approval_request",
            "approval_id": str(approval.id),
            "agent_id": approval.agent_id,
            "action_type": approval.action_type,
            "description": approval.description,
            "risk_level": approval.risk_level,
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None
        }
        
        await websocket_manager.send_to_user(str(user.id), notification)
        
    except Exception as e:
        logger.error(f"Failed to notify user about approval: {e}")

async def notify_agent_about_approval_decision(approval, approved: bool):
    """Notify agent about approval decision"""
    try:
        from main import app
        
        orchestrator = app.state.orchestrator
        agent = orchestrator.agents.get(approval.agent_id)
        
        if agent:
            decision = "approved" if approved else "rejected"
            await agent.store_memory(
                content=f"Approval request {decision}: {approval.description}",
                content_type="approval_decision",
                tags=["approval", decision, approval.action_type]
            )
            
    except Exception as e:
        logger.error(f"Failed to notify agent about approval decision: {e}")

async def execute_approved_action(approval):
    """Execute the approved action"""
    try:
        from main import app
        
        orchestrator = app.state.orchestrator
        agent = orchestrator.agents.get(approval.agent_id)
        
        if agent and hasattr(agent, 'execute_approved_action'):
            await agent.execute_approved_action(
                action_type=approval.action_type,
                payload=approval.payload
            )
            
    except Exception as e:
        logger.error(f"Failed to execute approved action: {e}")
        raise