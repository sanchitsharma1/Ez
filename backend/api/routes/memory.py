from fastapi import APIRouter, HTTPException, Depends, status, Query
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

from middleware.auth import get_current_active_user
from models.database import User
from models.schemas import MemoryEntry, MemoryQuery, MemoryResponse, MemoryStats

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/", response_model=List[MemoryResponse])
async def get_memories(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    agent_id: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    tags: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Retrieve stored memories with filtering options"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        # Parse tags if provided
        tag_list = tags.split(",") if tags else None
        
        memories = await memory_broker.get_memories(
            limit=limit,
            offset=offset,
            agent_id=agent_id,
            content_type=content_type,
            tags=tag_list,
            user_id=str(current_user.id)
        )
        
        return [
            MemoryResponse(
                id=memory.get("id"),
                content=memory.get("content", ""),
                content_type=memory.get("content_type", "conversation"),
                agent_id=memory.get("agent_id"),
                user_id=memory.get("user_id"),
                session_id=memory.get("session_id"),
                tags=memory.get("tags", []),
                metadata=memory.get("metadata", {}),
                created_at=memory.get("created_at"),
                updated_at=memory.get("updated_at")
            )
            for memory in memories
        ]
        
    except Exception as e:
        logger.error(f"Error retrieving memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memories: {str(e)}"
        )

@router.post("/", response_model=MemoryResponse)
async def create_memory(
    memory: MemoryEntry,
    current_user: User = Depends(get_current_active_user)
):
    """Create a new memory entry"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        # Create memory entry
        created_memory = await memory_broker.store_memory(
            content=memory.content,
            content_type=memory.content_type,
            agent_id=memory.agent_id,
            session_id=memory.session_id,
            tags=memory.tags,
            metadata=memory.metadata or {},
            user_id=str(current_user.id)
        )
        
        return MemoryResponse(
            id=created_memory.get("id"),
            content=created_memory.get("content", ""),
            content_type=created_memory.get("content_type", "conversation"),
            agent_id=created_memory.get("agent_id"),
            user_id=created_memory.get("user_id"),
            session_id=created_memory.get("session_id"),
            tags=created_memory.get("tags", []),
            metadata=created_memory.get("metadata", {}),
            created_at=created_memory.get("created_at"),
            updated_at=created_memory.get("updated_at")
        )
        
    except Exception as e:
        logger.error(f"Error creating memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create memory: {str(e)}"
        )

@router.get("/{memory_id}", response_model=MemoryResponse)
async def get_memory(
    memory_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Get a specific memory by ID"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        memory = await memory_broker.get_memory_by_id(
            memory_id=memory_id,
            user_id=str(current_user.id)
        )
        
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )
        
        return MemoryResponse(
            id=memory.get("id"),
            content=memory.get("content", ""),
            content_type=memory.get("content_type", "conversation"),
            agent_id=memory.get("agent_id"),
            user_id=memory.get("user_id"),
            session_id=memory.get("session_id"),
            tags=memory.get("tags", []),
            metadata=memory.get("metadata", {}),
            created_at=memory.get("created_at"),
            updated_at=memory.get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving memory {memory_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve memory: {str(e)}"
        )

@router.put("/{memory_id}", response_model=MemoryResponse)
async def update_memory(
    memory_id: str,
    memory_update: MemoryEntry,
    current_user: User = Depends(get_current_active_user)
):
    """Update a memory entry"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        updated_memory = await memory_broker.update_memory(
            memory_id=memory_id,
            content=memory_update.content,
            content_type=memory_update.content_type,
            tags=memory_update.tags,
            metadata=memory_update.metadata or {},
            user_id=str(current_user.id)
        )
        
        if not updated_memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found or not authorized to update"
            )
        
        return MemoryResponse(
            id=updated_memory.get("id"),
            content=updated_memory.get("content", ""),
            content_type=updated_memory.get("content_type", "conversation"),
            agent_id=updated_memory.get("agent_id"),
            user_id=updated_memory.get("user_id"),
            session_id=updated_memory.get("session_id"),
            tags=updated_memory.get("tags", []),
            metadata=updated_memory.get("metadata", {}),
            created_at=updated_memory.get("created_at"),
            updated_at=updated_memory.get("updated_at")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating memory {memory_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update memory: {str(e)}"
        )

@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """Delete a memory entry"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        success = await memory_broker.delete_memory(
            memory_id=memory_id,
            user_id=str(current_user.id)
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found or not authorized to delete"
            )
        
        return {
            "message": "Memory deleted successfully",
            "memory_id": memory_id,
            "deleted_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete memory: {str(e)}"
        )

@router.post("/search", response_model=List[MemoryResponse])
async def search_memories(
    query: MemoryQuery,
    current_user: User = Depends(get_current_active_user)
):
    """Search memories using semantic similarity"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        memories = await memory_broker.search_memories(
            query=query.query,
            limit=query.limit or 50,
            agent_id=query.agent_id,
            content_type=query.content_type,
            tags=query.tags,
            user_id=str(current_user.id),
            similarity_threshold=query.similarity_threshold
        )
        
        return [
            MemoryResponse(
                id=memory.get("id"),
                content=memory.get("content", ""),
                content_type=memory.get("content_type", "conversation"),
                agent_id=memory.get("agent_id"),
                user_id=memory.get("user_id"),
                session_id=memory.get("session_id"),
                tags=memory.get("tags", []),
                metadata=memory.get("metadata", {}),
                created_at=memory.get("created_at"),
                updated_at=memory.get("updated_at"),
                similarity_score=memory.get("similarity_score")
            )
            for memory in memories
        ]
        
    except Exception as e:
        logger.error(f"Error searching memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search memories: {str(e)}"
        )

@router.get("/stats/summary", response_model=MemoryStats)
async def get_memory_stats(
    current_user: User = Depends(get_current_active_user)
):
    """Get memory statistics for the user"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        stats = await memory_broker.get_memory_stats(user_id=str(current_user.id))
        
        return MemoryStats(
            total_memories=stats.get("total_memories", 0),
            memories_by_agent=stats.get("memories_by_agent", {}),
            memories_by_type=stats.get("memories_by_type", {}),
            total_size_mb=stats.get("total_size_mb", 0),
            oldest_memory=stats.get("oldest_memory"),
            newest_memory=stats.get("newest_memory"),
            top_tags=stats.get("top_tags", [])
        )
        
    except Exception as e:
        logger.error(f"Error getting memory stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get memory stats: {str(e)}"
        )

@router.post("/cleanup")
async def cleanup_memories(
    older_than_days: int = Query(30, ge=1),
    content_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Clean up old memories based on retention policy"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        
        cleaned_count = await memory_broker.cleanup_memories(
            older_than_days=older_than_days,
            content_type=content_type,
            user_id=str(current_user.id)
        )
        
        return {
            "message": f"Cleaned up {cleaned_count} memories",
            "cleaned_count": cleaned_count,
            "older_than_days": older_than_days,
            "content_type": content_type,
            "cleaned_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup memories: {str(e)}"
        )

@router.post("/export")
async def export_memories(
    format: str = Query("json", regex="^(json|csv)$"),
    agent_id: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user)
):
    """Export user memories in specified format"""
    try:
        from main import app
        memory_broker = app.state.memory_broker
        from fastapi.responses import StreamingResponse
        import json
        import csv
        from io import StringIO
        
        memories = await memory_broker.get_memories(
            limit=10000,  # Large limit for export
            agent_id=agent_id,
            content_type=content_type,
            user_id=str(current_user.id)
        )
        
        if format == "json":
            def generate():
                yield json.dumps({
                    "export_date": datetime.utcnow().isoformat(),
                    "user_id": str(current_user.id),
                    "total_memories": len(memories),
                    "memories": memories
                }, indent=2)
            
            return StreamingResponse(
                generate(),
                media_type="application/json",
                headers={"Content-Disposition": f"attachment; filename=memories_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"}
            )
        
        else:  # CSV format
            def generate():
                output = StringIO()
                writer = csv.writer(output)
                
                # Write header
                writer.writerow(["id", "content", "content_type", "agent_id", "session_id", "tags", "created_at"])
                
                for memory in memories:
                    writer.writerow([
                        memory.get("id", ""),
                        memory.get("content", ""),
                        memory.get("content_type", ""),
                        memory.get("agent_id", ""),
                        memory.get("session_id", ""),
                        ",".join(memory.get("tags", [])),
                        memory.get("created_at", "")
                    ])
                
                output.seek(0)
                return output.getvalue()
            
            return StreamingResponse(
                iter([generate()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=memories_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"}
            )
        
    except Exception as e:
        logger.error(f"Error exporting memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export memories: {str(e)}"
        )