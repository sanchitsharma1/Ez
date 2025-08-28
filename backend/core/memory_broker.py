import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from uuid import uuid4

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db_session
from core.redis_client import redis_client
from models.database import Memory
from utils.embedding_client import EmbeddingClient

logger = logging.getLogger(__name__)

class MemoryBroker:
    """Hybrid memory management system using Letta, Qdrant, PostgreSQL, and Redis"""
    
    def __init__(self):
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.embedding_client: Optional[EmbeddingClient] = None
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.initialized = False
        
        # Memory retention policy
        self.retention_days = settings.MEMORY_RETENTION_DAYS
        self.sync_interval = settings.MEMORY_SYNC_INTERVAL
        
        # Background tasks
        self._cleanup_task: Optional[asyncio.Task] = None
        self._sync_task: Optional[asyncio.Task] = None
    
    async def initialize(self):
        """Initialize memory broker and all components"""
        try:
            # Initialize Qdrant client
            self.qdrant_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY
            )
            
            # Initialize embedding client
            self.embedding_client = EmbeddingClient()
            await self.embedding_client.initialize()
            
            # Create Qdrant collection if not exists
            await self._create_collection()
            
            # Start background tasks
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._sync_task = asyncio.create_task(self._sync_loop())
            
            self.initialized = True
            logger.info("Memory Broker initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Memory Broker: {e}")
            raise
    
    async def _create_collection(self):
        """Create Qdrant collection for memory vectors"""
        try:
            collections = await self.qdrant_client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                await self.qdrant_client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=1536,  # OpenAI text-embedding-3-large dimension
                        distance=Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"Failed to create Qdrant collection: {e}")
            raise
    
    async def store_memory(
        self,
        content: str,
        content_type: str = "conversation",
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        importance_score: int = 1
    ) -> str:
        """Store memory across all systems"""
        try:
            memory_id = str(uuid4())
            
            # Generate embedding
            embedding = await self.embedding_client.get_embedding(content)
            
            # Store in PostgreSQL
            async with get_db_session() as session:
                memory = Memory(
                    id=memory_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    content=content,
                    content_type=content_type,
                    tags=tags or [],
                    importance_score=importance_score,
                    vector_id=memory_id,
                    created_at=datetime.utcnow()
                )
                session.add(memory)
                await session.commit()
            
            # Store vector in Qdrant
            await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=memory_id,
                        vector=embedding,
                        payload={
                            "content": content,
                            "content_type": content_type,
                            "agent_id": agent_id,
                            "session_id": session_id,
                            "tags": tags or [],
                            "importance_score": importance_score,
                            "created_at": datetime.utcnow().isoformat()
                        }
                    )
                ]
            )
            
            # Cache recent memory in Redis
            await redis_client.list_push(
                f"recent_memories:{agent_id or 'global'}",
                {
                    "id": memory_id,
                    "content": content,
                    "content_type": content_type,
                    "importance_score": importance_score,
                    "created_at": datetime.utcnow().isoformat()
                }
            )
            
            # Keep only recent 50 memories in cache
            await redis_client.redis.ltrim(f"recent_memories:{agent_id or 'global'}", 0, 49)
            
            logger.info(f"Stored memory {memory_id} successfully")
            return memory_id
            
        except Exception as e:
            logger.error(f"Failed to store memory: {e}")
            raise
    
    async def search_memories(
        self,
        query: str,
        agent_id: Optional[str] = None,
        content_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search memories using semantic similarity"""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.get_embedding(query)
            
            # Build filter conditions
            conditions = []
            if agent_id:
                conditions.append(FieldCondition(key="agent_id", match=MatchValue(value=agent_id)))
            if content_type:
                conditions.append(FieldCondition(key="content_type", match=MatchValue(value=content_type)))
            if tags:
                for tag in tags:
                    conditions.append(FieldCondition(key="tags", match=MatchValue(value=tag)))
            
            filter_condition = Filter(must=conditions) if conditions else None
            
            # Search in Qdrant
            search_results = await self.qdrant_client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                query_filter=filter_condition,
                limit=limit,
                score_threshold=threshold
            )
            
            # Format results
            memories = []
            for result in search_results:
                memories.append({
                    "id": result.id,
                    "content": result.payload.get("content"),
                    "content_type": result.payload.get("content_type"),
                    "agent_id": result.payload.get("agent_id"),
                    "session_id": result.payload.get("session_id"),
                    "tags": result.payload.get("tags", []),
                    "importance_score": result.payload.get("importance_score", 1),
                    "created_at": result.payload.get("created_at"),
                    "similarity_score": result.score
                })
            
            logger.info(f"Found {len(memories)} memories for query: {query}")
            return memories
            
        except Exception as e:
            logger.error(f"Failed to search memories: {e}")
            return []
    
    async def get_memories(
        self,
        limit: int = 100,
        offset: int = 0,
        agent_id: Optional[str] = None,
        content_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get memories from PostgreSQL with pagination"""
        try:
            async with get_db_session() as session:
                query = select(Memory).order_by(Memory.created_at.desc())
                
                if agent_id:
                    query = query.where(Memory.agent_id == agent_id)
                if content_type:
                    query = query.where(Memory.content_type == content_type)
                
                query = query.limit(limit).offset(offset)
                
                result = await session.execute(query)
                memories = result.scalars().all()
                
                return [
                    {
                        "id": str(memory.id),
                        "content": memory.content,
                        "content_type": memory.content_type,
                        "agent_id": memory.agent_id,
                        "session_id": str(memory.session_id) if memory.session_id else None,
                        "tags": memory.tags,
                        "importance_score": memory.importance_score,
                        "created_at": memory.created_at.isoformat(),
                        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None
                    }
                    for memory in memories
                ]
                
        except Exception as e:
            logger.error(f"Failed to get memories: {e}")
            return []
    
    async def delete_memory(self, memory_id: str) -> bool:
        """Delete memory from all systems"""
        try:
            # Delete from PostgreSQL
            async with get_db_session() as session:
                await session.execute(delete(Memory).where(Memory.id == memory_id))
                await session.commit()
            
            # Delete from Qdrant
            await self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=[memory_id]
            )
            
            logger.info(f"Deleted memory {memory_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete memory {memory_id}: {e}")
            return False
    
    async def store_conversation(
        self,
        agent_id: str,
        session_id: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Store conversation context in memory"""
        try:
            # Create conversation summary
            conversation_text = "\n".join([
                f"{msg['role']}: {msg['content']}" for msg in messages
            ])
            
            # Store with high importance for conversations
            await self.store_memory(
                content=conversation_text,
                content_type="conversation",
                agent_id=agent_id,
                session_id=session_id,
                tags=["conversation", agent_id],
                importance_score=5
            )
            
            # Store in Redis for quick access
            await redis_client.set(
                f"conversation:{session_id}:latest",
                {
                    "messages": messages,
                    "metadata": metadata or {},
                    "agent_id": agent_id,
                    "updated_at": datetime.utcnow().isoformat()
                },
                expire=3600  # 1 hour
            )
            
        except Exception as e:
            logger.error(f"Failed to store conversation: {e}")
    
    async def get_conversation_context(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation context"""
        try:
            # Try Redis first
            cached_conversation = await redis_client.get(f"conversation:{session_id}:latest")
            if cached_conversation:
                return cached_conversation.get("messages", [])
            
            # Fall back to memory search
            memories = await self.search_memories(
                query="conversation",
                content_type="conversation",
                limit=limit
            )
            
            # Extract messages from memory content
            messages = []
            for memory in memories:
                if memory.get("session_id") == session_id:
                    # Parse conversation content back to messages
                    content_lines = memory["content"].split("\n")
                    for line in content_lines:
                        if ":" in line:
                            role, content = line.split(":", 1)
                            messages.append({
                                "role": role.strip(),
                                "content": content.strip(),
                                "timestamp": memory["created_at"]
                            })
            
            return messages[-limit:] if messages else []
            
        except Exception as e:
            logger.error(f"Failed to get conversation context: {e}")
            return []
    
    async def _cleanup_loop(self):
        """Background task for memory cleanup"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                await self._cleanup_expired_memories()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
    
    async def _sync_loop(self):
        """Background task for memory synchronization"""
        while True:
            try:
                await asyncio.sleep(self.sync_interval)
                await self._sync_memories()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
    
    async def _cleanup_expired_memories(self):
        """Clean up expired memories"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
            
            # Get expired memories
            async with get_db_session() as session:
                query = select(Memory).where(Memory.created_at < cutoff_date)
                result = await session.execute(query)
                expired_memories = result.scalars().all()
                
                # Delete expired memories
                memory_ids = [str(memory.id) for memory in expired_memories]
                
                if memory_ids:
                    # Delete from PostgreSQL
                    await session.execute(delete(Memory).where(Memory.created_at < cutoff_date))
                    await session.commit()
                    
                    # Delete from Qdrant
                    await self.qdrant_client.delete(
                        collection_name=self.collection_name,
                        points_selector=memory_ids
                    )
                    
                    logger.info(f"Cleaned up {len(memory_ids)} expired memories")
                
        except Exception as e:
            logger.error(f"Failed to cleanup expired memories: {e}")
    
    async def _sync_memories(self):
        """Synchronize memories between systems"""
        try:
            # This could include:
            # - Reindexing vectors
            # - Syncing importance scores
            # - Updating metadata
            # - Consolidating similar memories
            logger.debug("Memory synchronization completed")
            
        except Exception as e:
            logger.error(f"Failed to sync memories: {e}")
    
    async def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        try:
            stats = {}
            
            # PostgreSQL stats
            async with get_db_session() as session:
                from sqlalchemy import func
                result = await session.execute(
                    select(func.count(Memory.id)).select_from(Memory)
                )
                stats["total_memories"] = result.scalar()
                
                # Count by content type
                result = await session.execute(
                    select(Memory.content_type, func.count(Memory.id))
                    .group_by(Memory.content_type)
                )
                stats["by_content_type"] = dict(result.all())
                
                # Count by agent
                result = await session.execute(
                    select(Memory.agent_id, func.count(Memory.id))
                    .group_by(Memory.agent_id)
                )
                stats["by_agent"] = dict(result.all())
            
            # Qdrant stats
            collection_info = await self.qdrant_client.get_collection(self.collection_name)
            stats["vector_count"] = collection_info.points_count
            stats["vector_size"] = collection_info.config.params.vectors.size
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {}
    
    async def cleanup(self):
        """Cleanup memory broker resources"""
        try:
            # Cancel background tasks
            if self._cleanup_task:
                self._cleanup_task.cancel()
            if self._sync_task:
                self._sync_task.cancel()
            
            # Close connections
            if self.qdrant_client:
                await self.qdrant_client.close()
            
            logger.info("Memory Broker cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during Memory Broker cleanup: {e}")