from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime, timedelta
import uuid

from middleware.auth import get_current_active_user
from models.database import User
from models.schemas import TaskRequest, TaskResponse, TaskUpdate, TaskStats
from core.database import get_db_session
from models.database import Task, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[TaskStatus] = Query(None),
    priority: Optional[TaskPriority] = Query(None),
    agent_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_active_user)
):
    """Get user tasks with filtering options"""
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            
            # Build query
            query = select(Task).where(Task.user_id == current_user.id)
            
            if status:
                query = query.where(Task.status == status)
            if priority:
                query = query.where(Task.priority == priority)
            if agent_id:
                query = query.where(Task.assigned_agent == agent_id)
            
            # Add ordering and pagination
            query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)
            
            result = await session.execute(query)
            tasks = result.scalars().all()
            
            return [
                TaskResponse(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    priority=task.priority,
                    assigned_agent=task.assigned_agent,
                    due_date=task.due_date,
                    tags=task.tags,
                    metadata=task.metadata or {},
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    completed_at=task.completed_at
                )
                for task in tasks
            ]
            
    except Exception as e:
        logger.error(f"Error retrieving tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve tasks: {str(e)}"
        )

@router.post("/", response_model=TaskResponse)
async def create_task(
    task_data: TaskRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new task"""
    try:
        async with get_db_session() as session:
            # Create new task
            new_task = Task(
                id=uuid.uuid4(),
                title=task_data.title,
                description=task_data.description,
                status=TaskStatus.PENDING,
                priority=task_data.priority or TaskPriority.MEDIUM,
                assigned_agent=task_data.assigned_agent,
                due_date=task_data.due_date,
                tags=task_data.tags or [],
                metadata=task_data.metadata or {},
                user_id=current_user.id,
                created_at=datetime.utcnow()
            )
            
            session.add(new_task)
            await session.commit()
            await session.refresh(new_task)
            
            # Notify assigned agent if specified
            if task_data.assigned_agent:
                try:
                    from main import app
                    orchestrator = app.state.orchestrator
                    
                    if task_data.assigned_agent in orchestrator.agents:
                        agent = orchestrator.agents[task_data.assigned_agent]
                        await agent.store_memory(
                            content=f"New task assigned: {task_data.title} - {task_data.description}",
                            content_type="task_assignment",
                            tags=["task", "assignment"]
                        )
                except Exception as e:
                    logger.warning(f"Failed to notify agent {task_data.assigned_agent}: {e}")
            
            return TaskResponse(
                id=new_task.id,
                title=new_task.title,
                description=new_task.description,
                status=new_task.status,
                priority=new_task.priority,
                assigned_agent=new_task.assigned_agent,
                due_date=new_task.due_date,
                tags=new_task.tags,
                metadata=new_task.metadata or {},
                created_at=new_task.created_at,
                updated_at=new_task.updated_at,
                completed_at=new_task.completed_at
            )
            
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create task: {str(e)}"
        )

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific task by ID"""
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            
            query = select(Task).where(
                Task.id == task_id,
                Task.user_id == current_user.id
            )
            result = await session.execute(query)
            task = result.scalar_one_or_none()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            return TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                status=task.status,
                priority=task.priority,
                assigned_agent=task.assigned_agent,
                due_date=task.due_date,
                tags=task.tags,
                metadata=task.metadata or {},
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve task: {str(e)}"
        )

@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    task_update: TaskUpdate,
    current_user: User = Depends(get_current_active_user)
):
    """Update a task"""
    try:
        async with get_db_session() as session:
            from sqlalchemy import select
            
            # Get existing task
            query = select(Task).where(
                Task.id == task_id,
                Task.user_id == current_user.id
            )
            result = await session.execute(query)
            task = result.scalar_one_or_none()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            # Update task fields
            update_data = task_update.dict(exclude_unset=True)
            for field, value in update_data.items():
                if hasattr(task, field) and value is not None:
                    setattr(task, field, value)
            
            # Set completion timestamp if status changed to completed
            if task_update.status == TaskStatus.COMPLETED and task.status != TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow()
            elif task_update.status != TaskStatus.COMPLETED:
                task.completed_at = None
            
            task.updated_at = datetime.utcnow()
            
            await session.commit()
            await session.refresh(task)
            
            return TaskResponse(
                id=task.id,
                title=task.title,
                description=task.description,
                status=task.status,
                priority=task.priority,
                assigned_agent=task.assigned_agent,
                due_date=task.due_date,
                tags=task.tags,
                metadata=task.metadata or {},
                created_at=task.created_at,
                updated_at=task.updated_at,
                completed_at=task.completed_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update task: {str(e)}"
        )

@router.delete("/{task_id}")
async def delete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a task"""
    try:
        async with get_db_session() as session:
            from sqlalchemy import select, delete
            
            # Check if task exists and belongs to user
            query = select(Task).where(
                Task.id == task_id,
                Task.user_id == current_user.id
            )
            result = await session.execute(query)
            task = result.scalar_one_or_none()
            
            if not task:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Task not found"
                )
            
            # Delete the task
            delete_query = delete(Task).where(Task.id == task_id)
            await session.execute(delete_query)
            await session.commit()
            
            return {
                "message": "Task deleted successfully",
                "task_id": str(task_id),
                "deleted_at": datetime.utcnow().isoformat()
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete task: {str(e)}"
        )

@router.post("/{task_id}/complete")
async def complete_task(
    task_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user)
):
    """Mark a task as completed"""
    try:
        task_update = TaskUpdate(status=TaskStatus.COMPLETED)
        return await update_task(task_id, task_update, current_user)
        
    except Exception as e:
        logger.error(f"Error completing task {task_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete task: {str(e)}"
        )

@router.post("/{task_id}/assign/{agent_id}")
async def assign_task_to_agent(
    task_id: uuid.UUID,
    agent_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Assign a task to a specific agent"""
    try:
        # Verify agent exists
        from main import app
        orchestrator = app.state.orchestrator
        
        if agent_id not in orchestrator.agents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Agent {agent_id} not found"
            )
        
        task_update = TaskUpdate(assigned_agent=agent_id)
        updated_task = await update_task(task_id, task_update, current_user)
        
        # Notify the agent
        try:
            agent = orchestrator.agents[agent_id]
            await agent.store_memory(
                content=f"Task assigned: {updated_task.title} - {updated_task.description}",
                content_type="task_assignment",
                tags=["task", "assignment"]
            )
        except Exception as e:
            logger.warning(f"Failed to notify agent {agent_id}: {e}")
        
        return updated_task
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error assigning task {task_id} to agent {agent_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to assign task: {str(e)}"
        )

@router.get("/stats/summary", response_model=TaskStats)
async def get_task_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get task statistics for the user"""
    try:
        async with get_db_session() as session:
            from sqlalchemy import select, func
            
            # Total tasks
            total_query = select(func.count(Task.id)).where(Task.user_id == current_user.id)
            total_result = await session.execute(total_query)
            total_tasks = total_result.scalar()
            
            # Tasks by status
            status_query = select(Task.status, func.count(Task.id)).where(
                Task.user_id == current_user.id
            ).group_by(Task.status)
            status_result = await session.execute(status_query)
            tasks_by_status = {status: count for status, count in status_result}
            
            # Tasks by priority
            priority_query = select(Task.priority, func.count(Task.id)).where(
                Task.user_id == current_user.id
            ).group_by(Task.priority)
            priority_result = await session.execute(priority_query)
            tasks_by_priority = {priority.value: count for priority, count in priority_result}
            
            # Overdue tasks
            now = datetime.utcnow()
            overdue_query = select(func.count(Task.id)).where(
                Task.user_id == current_user.id,
                Task.due_date < now,
                Task.status != TaskStatus.COMPLETED
            )
            overdue_result = await session.execute(overdue_query)
            overdue_tasks = overdue_result.scalar()
            
            # Due today
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            today_end = today_start + timedelta(days=1)
            
            due_today_query = select(func.count(Task.id)).where(
                Task.user_id == current_user.id,
                Task.due_date >= today_start,
                Task.due_date < today_end,
                Task.status != TaskStatus.COMPLETED
            )
            due_today_result = await session.execute(due_today_query)
            due_today = due_today_result.scalar()
            
            return TaskStats(
                total_tasks=total_tasks,
                tasks_by_status=tasks_by_status,
                tasks_by_priority=tasks_by_priority,
                overdue_tasks=overdue_tasks,
                due_today=due_today,
                completion_rate=round(
                    tasks_by_status.get(TaskStatus.COMPLETED, 0) / max(total_tasks, 1) * 100, 2
                )
            )
            
    except Exception as e:
        logger.error(f"Error getting task stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get task stats: {str(e)}"
        )

@router.get("/due/today", response_model=List[TaskResponse])
async def get_tasks_due_today(
    current_user: User = Depends(get_current_active_user)
):
    """Get tasks due today"""
    try:
        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        async with get_db_session() as session:
            from sqlalchemy import select
            
            query = select(Task).where(
                Task.user_id == current_user.id,
                Task.due_date >= today_start,
                Task.due_date < today_end,
                Task.status != TaskStatus.COMPLETED
            ).order_by(Task.priority.desc(), Task.due_date)
            
            result = await session.execute(query)
            tasks = result.scalars().all()
            
            return [
                TaskResponse(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    priority=task.priority,
                    assigned_agent=task.assigned_agent,
                    due_date=task.due_date,
                    tags=task.tags,
                    metadata=task.metadata or {},
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    completed_at=task.completed_at
                )
                for task in tasks
            ]
            
    except Exception as e:
        logger.error(f"Error getting tasks due today: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get tasks due today: {str(e)}"
        )

@router.get("/overdue", response_model=List[TaskResponse])
async def get_overdue_tasks(
    current_user: User = Depends(get_current_active_user)
):
    """Get overdue tasks"""
    try:
        now = datetime.utcnow()
        
        async with get_db_session() as session:
            from sqlalchemy import select
            
            query = select(Task).where(
                Task.user_id == current_user.id,
                Task.due_date < now,
                Task.status != TaskStatus.COMPLETED
            ).order_by(Task.due_date)
            
            result = await session.execute(query)
            tasks = result.scalars().all()
            
            return [
                TaskResponse(
                    id=task.id,
                    title=task.title,
                    description=task.description,
                    status=task.status,
                    priority=task.priority,
                    assigned_agent=task.assigned_agent,
                    due_date=task.due_date,
                    tags=task.tags,
                    metadata=task.metadata or {},
                    created_at=task.created_at,
                    updated_at=task.updated_at,
                    completed_at=task.completed_at
                )
                for task in tasks
            ]
            
    except Exception as e:
        logger.error(f"Error getting overdue tasks: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get overdue tasks: {str(e)}"
        )