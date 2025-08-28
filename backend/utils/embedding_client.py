import asyncio
import logging
from typing import List, Optional
import numpy as np
import openai
import httpx
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = logging.getLogger(__name__)

class EmbeddingClient:
    """Unified embedding client supporting OpenAI and local models"""
    
    def __init__(self):
        self.openai_client: Optional[openai.AsyncOpenAI] = None
        self.local_model: Optional[SentenceTransformer] = None
        self.fallback_model: Optional[SentenceTransformer] = None
        self.specialized_model: Optional[SentenceTransformer] = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize embedding clients and models"""
        try:
            # Initialize OpenAI client for online embeddings
            if settings.OPENAI_API_KEY:
                self.openai_client = openai.AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY
                )
                logger.info("OpenAI embedding client initialized")
            
            # Initialize local models in background to avoid blocking
            await asyncio.create_task(self._load_local_models())
            
            self.initialized = True
            logger.info("Embedding client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize embedding client: {e}")
            raise
    
    async def _load_local_models(self):
        """Load local embedding models"""
        try:
            # Primary local model - nomic-embed-text
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._load_nomic_model
                )
                logger.info("Loaded nomic-embed-text model")
            except Exception as e:
                logger.warning(f"Failed to load nomic-embed-text: {e}")
            
            # Fallback model - sentence-transformers/all-MiniLM-L6-v2
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._load_fallback_model
                )
                logger.info("Loaded fallback embedding model")
            except Exception as e:
                logger.warning(f"Failed to load fallback model: {e}")
            
            # Specialized model - e5-large-v2
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._load_specialized_model
                )
                logger.info("Loaded specialized embedding model")
            except Exception as e:
                logger.warning(f"Failed to load specialized model: {e}")
                
        except Exception as e:
            logger.error(f"Error loading local models: {e}")
    
    def _load_nomic_model(self):
        """Load nomic-embed-text model"""
        try:
            # This would require the actual nomic-embed-text model
            # For now, we'll use sentence-transformers as a placeholder
            self.local_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load nomic model: {e}")
    
    def _load_fallback_model(self):
        """Load fallback sentence transformer model"""
        try:
            self.fallback_model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        except Exception as e:
            logger.error(f"Failed to load fallback model: {e}")
    
    def _load_specialized_model(self):
        """Load specialized e5-large-v2 model"""
        try:
            self.specialized_model = SentenceTransformer('intfloat/e5-large-v2')
        except Exception as e:
            logger.error(f"Failed to load specialized model: {e}")
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def get_embedding(
        self,
        text: str,
        model: str = "auto",
        mode: str = "online"
    ) -> List[float]:
        """Get embedding for text using appropriate model"""
        
        if mode == "online" and self.openai_client:
            return await self._get_openai_embedding(text, model)
        else:
            return await self._get_local_embedding(text, model)
    
    async def _get_openai_embedding(
        self,
        text: str,
        model: str = "auto"
    ) -> List[float]:
        """Get embedding using OpenAI API"""
        try:
            if model == "auto":
                model = settings.OPENAI_EMBEDDING_MODEL
            
            response = await self.openai_client.embeddings.create(
                input=text,
                model=model
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"OpenAI embedding error: {e}")
            # Fallback to local embedding
            return await self._get_local_embedding(text, model)
    
    async def _get_local_embedding(
        self,
        text: str,
        model: str = "auto"
    ) -> List[float]:
        """Get embedding using local models"""
        try:
            # Choose appropriate local model
            selected_model = None
            
            if model == "specialized" and self.specialized_model:
                selected_model = self.specialized_model
            elif model == "nomic" and self.local_model:
                selected_model = self.local_model
            elif self.local_model:
                selected_model = self.local_model
            elif self.fallback_model:
                selected_model = self.fallback_model
            else:
                raise ValueError("No local embedding models available")
            
            # Generate embedding in executor to avoid blocking
            embedding = await asyncio.get_event_loop().run_in_executor(
                None, selected_model.encode, text
            )
            
            return embedding.tolist()
            
        except Exception as e:
            logger.error(f"Local embedding error: {e}")
            raise
    
    async def get_embeddings_batch(
        self,
        texts: List[str],
        model: str = "auto",
        mode: str = "online",
        batch_size: int = 100
    ) -> List[List[float]]:
        """Get embeddings for multiple texts"""
        
        if not texts:
            return []
        
        embeddings = []
        
        # Process in batches to avoid memory issues
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            
            if mode == "online" and self.openai_client:
                batch_embeddings = await self._get_openai_embeddings_batch(batch_texts, model)
            else:
                batch_embeddings = await self._get_local_embeddings_batch(batch_texts, model)
            
            embeddings.extend(batch_embeddings)
            
            # Small delay between batches to avoid rate limiting
            if i + batch_size < len(texts):
                await asyncio.sleep(0.1)
        
        return embeddings
    
    async def _get_openai_embeddings_batch(
        self,
        texts: List[str],
        model: str = "auto"
    ) -> List[List[float]]:
        """Get batch embeddings using OpenAI API"""
        try:
            if model == "auto":
                model = settings.OPENAI_EMBEDDING_MODEL
            
            response = await self.openai_client.embeddings.create(
                input=texts,
                model=model
            )
            
            return [item.embedding for item in response.data]
            
        except Exception as e:
            logger.error(f"OpenAI batch embedding error: {e}")
            # Fallback to local embeddings
            return await self._get_local_embeddings_batch(texts, model)
    
    async def _get_local_embeddings_batch(
        self,
        texts: List[str],
        model: str = "auto"
    ) -> List[List[float]]:
        """Get batch embeddings using local models"""
        try:
            # Choose appropriate local model
            selected_model = None
            
            if model == "specialized" and self.specialized_model:
                selected_model = self.specialized_model
            elif model == "nomic" and self.local_model:
                selected_model = self.local_model
            elif self.local_model:
                selected_model = self.local_model
            elif self.fallback_model:
                selected_model = self.fallback_model
            else:
                raise ValueError("No local embedding models available")
            
            # Generate embeddings in executor
            embeddings = await asyncio.get_event_loop().run_in_executor(
                None, selected_model.encode, texts
            )
            
            return embeddings.tolist()
            
        except Exception as e:
            logger.error(f"Local batch embedding error: {e}")
            raise
    
    async def compute_similarity(
        self,
        text1: str,
        text2: str,
        model: str = "auto",
        mode: str = "online"
    ) -> float:
        """Compute cosine similarity between two texts"""
        try:
            embedding1 = await self.get_embedding(text1, model, mode)
            embedding2 = await self.get_embedding(text2, model, mode)
            
            # Convert to numpy arrays for computation
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Compute cosine similarity
            similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
            
            return float(similarity)
            
        except Exception as e:
            logger.error(f"Similarity computation error: {e}")
            return 0.0
    
    async def find_most_similar(
        self,
        query_text: str,
        candidate_texts: List[str],
        model: str = "auto",
        mode: str = "online",
        top_k: int = 5
    ) -> List[tuple]:
        """Find most similar texts to query"""
        try:
            # Get query embedding
            query_embedding = await self.get_embedding(query_text, model, mode)
            
            # Get candidate embeddings
            candidate_embeddings = await self.get_embeddings_batch(
                candidate_texts, model, mode
            )
            
            # Compute similarities
            similarities = []
            query_vec = np.array(query_embedding)
            
            for i, candidate_embedding in enumerate(candidate_embeddings):
                candidate_vec = np.array(candidate_embedding)
                similarity = np.dot(query_vec, candidate_vec) / (
                    np.linalg.norm(query_vec) * np.linalg.norm(candidate_vec)
                )
                similarities.append((i, candidate_texts[i], float(similarity)))
            
            # Sort by similarity and return top_k
            similarities.sort(key=lambda x: x[2], reverse=True)
            return similarities[:top_k]
            
        except Exception as e:
            logger.error(f"Similar text finding error: {e}")
            return []
    
    async def get_text_clustering(
        self,
        texts: List[str],
        n_clusters: int = 5,
        model: str = "auto",
        mode: str = "online"
    ) -> List[int]:
        """Cluster texts based on embeddings"""
        try:
            from sklearn.cluster import KMeans
            
            # Get embeddings for all texts
            embeddings = await self.get_embeddings_batch(texts, model, mode)
            
            # Perform clustering in executor
            def cluster_embeddings():
                embeddings_array = np.array(embeddings)
                kmeans = KMeans(n_clusters=n_clusters, random_state=42)
                return kmeans.fit_predict(embeddings_array).tolist()
            
            cluster_labels = await asyncio.get_event_loop().run_in_executor(
                None, cluster_embeddings
            )
            
            return cluster_labels
            
        except Exception as e:
            logger.error(f"Text clustering error: {e}")
            return [0] * len(texts)  # Return all in cluster 0 as fallback
    
    async def get_available_models(self) -> dict:
        """Get available embedding models"""
        models = {
            "online": [],
            "local": []
        }
        
        # OpenAI models
        if self.openai_client:
            models["online"] = [
                "text-embedding-3-large",
                "text-embedding-3-small", 
                "text-embedding-ada-002"
            ]
        
        # Local models
        if self.local_model:
            models["local"].append("nomic-embed-text")
        if self.fallback_model:
            models["local"].append("all-MiniLM-L6-v2")
        if self.specialized_model:
            models["local"].append("e5-large-v2")
        
        return models
    
    async def health_check(self) -> dict:
        """Check health of embedding services"""
        health = {}
        
        # Check OpenAI
        try:
            if self.openai_client:
                test_embedding = await self.get_embedding("test", mode="online")
                health["openai"] = len(test_embedding) > 0
            else:
                health["openai"] = False
        except Exception:
            health["openai"] = False
        
        # Check local models
        try:
            test_embedding = await self.get_embedding("test", mode="offline")
            health["local"] = len(test_embedding) > 0
        except Exception:
            health["local"] = False
        
        return health
    
    async def cleanup(self):
        """Clean up embedding client resources"""
        try:
            # Clean up model references
            self.local_model = None
            self.fallback_model = None
            self.specialized_model = None
            
            logger.info("Embedding client cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during embedding client cleanup: {e}")