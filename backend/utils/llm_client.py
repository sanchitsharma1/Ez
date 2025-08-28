import asyncio
import logging
from typing import List, Dict, Any, Optional, AsyncGenerator
import openai
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from core.config import settings

logger = logging.getLogger(__name__)

class LLMClient:
    """Unified LLM client supporting OpenAI, Perplexity, and Ollama"""
    
    def __init__(self):
        self.openai_client: Optional[openai.AsyncOpenAI] = None
        self.perplexity_client: Optional[httpx.AsyncClient] = None
        self.ollama_client: Optional[httpx.AsyncClient] = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize LLM clients"""
        try:
            # Initialize OpenAI client
            if settings.OPENAI_API_KEY:
                self.openai_client = openai.AsyncOpenAI(
                    api_key=settings.OPENAI_API_KEY
                )
                logger.info("OpenAI client initialized")
            
            # Initialize Perplexity client
            if settings.PERPLEXITY_API_KEY:
                self.perplexity_client = httpx.AsyncClient(
                    base_url="https://api.perplexity.ai",
                    headers={
                        "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    timeout=60.0
                )
                logger.info("Perplexity client initialized")
            
            # Initialize Ollama client
            self.ollama_client = httpx.AsyncClient(
                base_url=settings.OLLAMA_URL,
                timeout=120.0
            )
            logger.info("Ollama client initialized")
            
            self.initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize LLM clients: {e}")
            raise
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        mode: str = "online",
        agent_id: str = "carol",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        stream: bool = False
    ) -> str:
        """Generate response using appropriate LLM based on mode"""
        
        if mode == "online":
            return await self._generate_online_response(
                messages, agent_id, model, temperature, max_tokens, stream
            )
        else:
            return await self._generate_offline_response(
                messages, agent_id, model, temperature, max_tokens, stream
            )
    
    async def _generate_online_response(
        self,
        messages: List[Dict[str, str]],
        agent_id: str,
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        stream: bool
    ) -> str:
        """Generate response using online models (OpenAI/Perplexity)"""
        try:
            if not self.openai_client:
                raise ValueError("OpenAI client not initialized")
            
            # Use OpenAI by default, Perplexity for research queries
            if self._needs_research(messages):
                return await self._generate_perplexity_response(
                    messages, temperature, max_tokens
                )
            else:
                return await self._generate_openai_response(
                    messages, model or settings.OPENAI_DEFAULT_MODEL, 
                    temperature, max_tokens, stream
                )
                
        except Exception as e:
            logger.error(f"Online LLM generation failed: {e}")
            # Fallback to offline if available
            return await self._generate_offline_response(
                messages, agent_id, model, temperature, max_tokens, stream
            )
    
    async def _generate_openai_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool
    ) -> str:
        """Generate response using OpenAI"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream
            )
            
            if stream:
                # Handle streaming response
                content_parts = []
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        content_parts.append(chunk.choices[0].delta.content)
                return "".join(content_parts)
            else:
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise
    
    async def _generate_perplexity_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int
    ) -> str:
        """Generate response using Perplexity for research queries"""
        try:
            if not self.perplexity_client:
                raise ValueError("Perplexity client not initialized")
            
            payload = {
                "model": "llama-3.1-sonar-small-128k-online",
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "return_citations": True,
                "search_domain_filter": ["perplexity.ai"],
                "return_images": False,
                "return_related_questions": False
            }
            
            response = await self.perplexity_client.post("/chat/completions", json=payload)
            response.raise_for_status()
            
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            
            # Add citation info if available
            if result.get("citations"):
                content += "\n\nSources: " + ", ".join(result["citations"])
            
            return content
            
        except Exception as e:
            logger.error(f"Perplexity API error: {e}")
            raise
    
    async def _generate_offline_response(
        self,
        messages: List[Dict[str, str]],
        agent_id: str,
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        stream: bool
    ) -> str:
        """Generate response using Ollama local models"""
        try:
            if not self.ollama_client:
                raise ValueError("Ollama client not initialized")
            
            # Select appropriate model
            model_name = model or self._get_agent_model(agent_id)
            
            # Convert messages to Ollama format
            prompt = self._messages_to_prompt(messages)
            
            payload = {
                "model": model_name,
                "prompt": prompt,
                "stream": stream,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            response = await self.ollama_client.post("/api/generate", json=payload)
            response.raise_for_status()
            
            if stream:
                # Handle streaming response
                content_parts = []
                async for line in response.aiter_lines():
                    if line:
                        chunk = line.strip()
                        if chunk:
                            import json
                            data = json.loads(chunk)
                            if "response" in data:
                                content_parts.append(data["response"])
                return "".join(content_parts)
            else:
                result = response.json()
                return result.get("response", "")
                
        except Exception as e:
            logger.error(f"Ollama API error: {e}")
            raise
    
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        mode: str = "online",
        agent_id: str = "carol",
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        
        try:
            if mode == "online" and self.openai_client:
                async for chunk in self._stream_openai_response(
                    messages, model or settings.OPENAI_DEFAULT_MODEL, 
                    temperature, max_tokens
                ):
                    yield chunk
            else:
                async for chunk in self._stream_ollama_response(
                    messages, self._get_agent_model(agent_id), 
                    temperature, max_tokens
                ):
                    yield chunk
                    
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield f"Error: {str(e)}"
    
    async def _stream_openai_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """Stream OpenAI response"""
        try:
            response = await self.openai_client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            yield f"Error: {str(e)}"
    
    async def _stream_ollama_response(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int
    ) -> AsyncGenerator[str, None]:
        """Stream Ollama response"""
        try:
            prompt = self._messages_to_prompt(messages)
            
            payload = {
                "model": model,
                "prompt": prompt,
                "stream": True,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            async with self.ollama_client.stream("POST", "/api/generate", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line:
                        import json
                        try:
                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue
                            
        except Exception as e:
            logger.error(f"Ollama streaming error: {e}")
            yield f"Error: {str(e)}"
    
    def _needs_research(self, messages: List[Dict[str, str]]) -> bool:
        """Determine if query needs research capabilities"""
        research_keywords = [
            "latest", "recent", "current", "news", "today", "yesterday",
            "what's happening", "update on", "search for", "find information",
            "research", "investigate", "analyze current", "market trends"
        ]
        
        last_message = messages[-1]["content"].lower() if messages else ""
        return any(keyword in last_message for keyword in research_keywords)
    
    def _get_agent_model(self, agent_id: str) -> str:
        """Get appropriate model for each agent"""
        agent_models = {
            "carol": "llama3:8b",
            "alex": "codellama:7b",
            "sofia": "llama3:8b", 
            "morgan": "llama3:8b",
            "judy": "llama3:70b"  # Larger model for consensus building
        }
        return agent_models.get(agent_id, settings.DEFAULT_LOCAL_MODEL)
    
    def _messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert OpenAI format messages to Ollama prompt"""
        prompt_parts = []
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"Human: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        prompt_parts.append("Assistant:")
        return "\n\n".join(prompt_parts)
    
    async def get_available_models(self, mode: str = "online") -> List[str]:
        """Get list of available models"""
        try:
            if mode == "online" and self.openai_client:
                models = await self.openai_client.models.list()
                return [model.id for model in models.data if "gpt" in model.id]
            else:
                # Get Ollama models
                response = await self.ollama_client.get("/api/tags")
                response.raise_for_status()
                result = response.json()
                return [model["name"] for model in result.get("models", [])]
                
        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []
    
    async def health_check(self) -> Dict[str, bool]:
        """Check health of all LLM services"""
        health = {}
        
        # Check OpenAI
        try:
            if self.openai_client:
                models = await self.openai_client.models.list()
                health["openai"] = len(models.data) > 0
            else:
                health["openai"] = False
        except Exception:
            health["openai"] = False
        
        # Check Perplexity
        try:
            if self.perplexity_client:
                response = await self.perplexity_client.get("/")
                health["perplexity"] = response.status_code < 500
            else:
                health["perplexity"] = False
        except Exception:
            health["perplexity"] = False
        
        # Check Ollama
        try:
            if self.ollama_client:
                response = await self.ollama_client.get("/api/tags")
                health["ollama"] = response.status_code == 200
            else:
                health["ollama"] = False
        except Exception:
            health["ollama"] = False
        
        return health
    
    async def cleanup(self):
        """Clean up LLM client resources"""
        try:
            if self.perplexity_client:
                await self.perplexity_client.aclose()
            
            if self.ollama_client:
                await self.ollama_client.aclose()
            
            logger.info("LLM client cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during LLM client cleanup: {e}")