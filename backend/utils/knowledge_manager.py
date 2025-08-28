import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import uuid4
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db_session
from models.database import KnowledgeBase
from utils.embedding_client import EmbeddingClient
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import PointStruct

logger = logging.getLogger(__name__)

class KnowledgeManager:
    """Manages knowledge base storage, retrieval, and search"""
    
    def __init__(self):
        self.embedding_client: Optional[EmbeddingClient] = None
        self.qdrant_client: Optional[AsyncQdrantClient] = None
        self.collection_name = "knowledge_base"
        self.initialized = False
    
    async def initialize(self):
        """Initialize knowledge manager"""
        try:
            # Initialize embedding client
            self.embedding_client = EmbeddingClient()
            await self.embedding_client.initialize()
            
            # Initialize Qdrant client
            from core.config import settings
            self.qdrant_client = AsyncQdrantClient(
                url=settings.QDRANT_URL,
                api_key=settings.QDRANT_API_KEY
            )
            
            # Create collection if it doesn't exist
            await self._ensure_collection_exists()
            
            self.initialized = True
            logger.info("Knowledge manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize knowledge manager: {e}")
            raise
    
    async def _ensure_collection_exists(self):
        """Ensure the knowledge base collection exists in Qdrant"""
        try:
            from qdrant_client.models import Distance, VectorParams
            
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
        except Exception as e:
            logger.error(f"Error ensuring collection exists: {e}")
            raise
    
    async def store_knowledge(
        self,
        title: str,
        content: str,
        content_type: str = "document",
        source_file: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store knowledge entry in both PostgreSQL and Qdrant"""
        try:
            knowledge_id = str(uuid4())
            
            # Generate embedding
            embedding = await self.embedding_client.get_embedding(content)
            
            # Store in PostgreSQL
            async with get_db_session() as session:
                knowledge_entry = KnowledgeBase(
                    id=knowledge_id,
                    title=title,
                    content=content,
                    content_type=content_type,
                    source_file=source_file,
                    tags=tags or [],
                    vector_id=knowledge_id,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(knowledge_entry)
                await session.commit()
            
            # Store vector in Qdrant
            await self.qdrant_client.upsert(
                collection_name=self.collection_name,
                points=[
                    PointStruct(
                        id=knowledge_id,
                        vector=embedding,
                        payload={
                            "title": title,
                            "content": content[:1000],  # Truncate for payload
                            "content_type": content_type,
                            "source_file": source_file,
                            "tags": tags or [],
                            "created_at": datetime.utcnow().isoformat(),
                            **(metadata or {})
                        }
                    )
                ]
            )
            
            logger.info(f"Stored knowledge entry: {title}")
            return knowledge_id
            
        except Exception as e:
            logger.error(f"Error storing knowledge: {e}")
            raise
    
    async def search_knowledge(
        self,
        query: str,
        limit: int = 10,
        content_types: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search knowledge base using semantic similarity"""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_client.get_embedding(query)
            
            # Build filter conditions
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            conditions = []
            
            if content_types:
                for content_type in content_types:
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
            
            # Get full content from PostgreSQL
            knowledge_entries = []
            for result in search_results:
                async with get_db_session() as session:
                    query_stmt = select(KnowledgeBase).where(KnowledgeBase.id == result.id)
                    db_result = await session.execute(query_stmt)
                    knowledge = db_result.scalar_one_or_none()
                    
                    if knowledge:
                        knowledge_entries.append({
                            "id": str(knowledge.id),
                            "title": knowledge.title,
                            "content": knowledge.content,
                            "content_type": knowledge.content_type,
                            "source_file": knowledge.source_file,
                            "tags": knowledge.tags,
                            "similarity_score": result.score,
                            "created_at": knowledge.created_at.isoformat() if knowledge.created_at else None,
                            "updated_at": knowledge.updated_at.isoformat() if knowledge.updated_at else None
                        })
            
            logger.info(f"Found {len(knowledge_entries)} knowledge entries for query: {query}")
            return knowledge_entries
            
        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            return []
    
    async def get_knowledge_by_id(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """Get specific knowledge entry by ID"""
        try:
            async with get_db_session() as session:
                query = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_id)
                result = await session.execute(query)
                knowledge = result.scalar_one_or_none()
                
                if knowledge:
                    return {
                        "id": str(knowledge.id),
                        "title": knowledge.title,
                        "content": knowledge.content,
                        "content_type": knowledge.content_type,
                        "source_file": knowledge.source_file,
                        "tags": knowledge.tags,
                        "created_at": knowledge.created_at.isoformat() if knowledge.created_at else None,
                        "updated_at": knowledge.updated_at.isoformat() if knowledge.updated_at else None
                    }
                
                return None
                
        except Exception as e:
            logger.error(f"Error getting knowledge by ID {knowledge_id}: {e}")
            return None
    
    async def update_knowledge(
        self,
        knowledge_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> bool:
        """Update existing knowledge entry"""
        try:
            async with get_db_session() as session:
                query = select(KnowledgeBase).where(KnowledgeBase.id == knowledge_id)
                result = await session.execute(query)
                knowledge = result.scalar_one_or_none()
                
                if not knowledge:
                    return False
                
                # Update fields
                if title is not None:
                    knowledge.title = title
                if content is not None:
                    knowledge.content = content
                if tags is not None:
                    knowledge.tags = tags
                
                knowledge.updated_at = datetime.utcnow()
                await session.commit()
                
                # Update vector if content changed
                if content is not None:
                    embedding = await self.embedding_client.get_embedding(content)
                    await self.qdrant_client.upsert(
                        collection_name=self.collection_name,
                        points=[
                            PointStruct(
                                id=knowledge_id,
                                vector=embedding,
                                payload={
                                    "title": knowledge.title,
                                    "content": content[:1000],
                                    "content_type": knowledge.content_type,
                                    "source_file": knowledge.source_file,
                                    "tags": knowledge.tags,
                                    "updated_at": datetime.utcnow().isoformat()
                                }
                            )
                        ]
                    )
                
                logger.info(f"Updated knowledge entry: {knowledge_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error updating knowledge {knowledge_id}: {e}")
            return False
    
    async def delete_knowledge(self, knowledge_id: str) -> bool:
        """Delete knowledge entry"""
        try:
            # Delete from PostgreSQL
            async with get_db_session() as session:
                await session.execute(delete(KnowledgeBase).where(KnowledgeBase.id == knowledge_id))
                await session.commit()
            
            # Delete from Qdrant
            await self.qdrant_client.delete(
                collection_name=self.collection_name,
                points_selector=[knowledge_id]
            )
            
            logger.info(f"Deleted knowledge entry: {knowledge_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting knowledge {knowledge_id}: {e}")
            return False
    
    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        try:
            stats = {"total_entries": 0, "by_content_type": {}, "by_tags": {}}
            
            async with get_db_session() as session:
                from sqlalchemy import func
                
                # Total entries
                total_query = select(func.count(KnowledgeBase.id))
                result = await session.execute(total_query)
                stats["total_entries"] = result.scalar()
                
                # By content type
                type_query = select(KnowledgeBase.content_type, func.count(KnowledgeBase.id)).group_by(KnowledgeBase.content_type)
                result = await session.execute(type_query)
                stats["by_content_type"] = dict(result.all())
                
                # Recent entries
                from sqlalchemy import desc
                recent_query = select(KnowledgeBase).order_by(desc(KnowledgeBase.created_at)).limit(5)
                result = await session.execute(recent_query)
                recent_entries = result.scalars().all()
                
                stats["recent_entries"] = [
                    {
                        "id": str(entry.id),
                        "title": entry.title,
                        "content_type": entry.content_type,
                        "created_at": entry.created_at.isoformat() if entry.created_at else None
                    }
                    for entry in recent_entries
                ]
            
            # Qdrant stats
            try:
                collection_info = await self.qdrant_client.get_collection(self.collection_name)
                stats["vector_count"] = collection_info.points_count
            except Exception:
                stats["vector_count"] = 0
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting knowledge stats: {e}")
            return {"total_entries": 0, "by_content_type": {}, "by_tags": {}}
    
    async def list_knowledge(
        self,
        limit: int = 20,
        offset: int = 0,
        content_type: Optional[str] = None,
        order_by: str = "created_at"
    ) -> List[Dict[str, Any]]:
        """List knowledge entries with pagination"""
        try:
            async with get_db_session() as session:
                query = select(KnowledgeBase)
                
                if content_type:
                    query = query.where(KnowledgeBase.content_type == content_type)
                
                if order_by == "created_at":
                    from sqlalchemy import desc
                    query = query.order_by(desc(KnowledgeBase.created_at))
                elif order_by == "title":
                    query = query.order_by(KnowledgeBase.title)
                elif order_by == "updated_at":
                    from sqlalchemy import desc
                    query = query.order_by(desc(KnowledgeBase.updated_at))
                
                query = query.limit(limit).offset(offset)
                
                result = await session.execute(query)
                knowledge_entries = result.scalars().all()
                
                return [
                    {
                        "id": str(entry.id),
                        "title": entry.title,
                        "content": entry.content[:200] + "..." if len(entry.content) > 200 else entry.content,
                        "content_type": entry.content_type,
                        "source_file": entry.source_file,
                        "tags": entry.tags,
                        "created_at": entry.created_at.isoformat() if entry.created_at else None,
                        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None
                    }
                    for entry in knowledge_entries
                ]
                
        except Exception as e:
            logger.error(f"Error listing knowledge entries: {e}")
            return []
    
    async def cleanup(self):
        """Cleanup knowledge manager resources"""
        try:
            if self.qdrant_client:
                await self.qdrant_client.close()
            
            logger.info("Knowledge manager cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during knowledge manager cleanup: {e}")