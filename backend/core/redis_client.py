import redis.asyncio as redis
import json
import logging
from typing import Any, Optional, Union
from datetime import timedelta

from core.config import settings

logger = logging.getLogger(__name__)

class RedisClient:
    """Async Redis client wrapper"""
    
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        
    async def connect(self):
        """Initialize Redis connection"""
        try:
            self.redis = redis.from_url(
                settings.REDIS_URL,
                db=settings.REDIS_DB,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
                decode_responses=True
            )
            # Test connection
            await self.redis.ping()
            logger.info("Connected to Redis successfully")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")
    
    async def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        """Set a key-value pair with optional expiration"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            
            result = await self.redis.set(key, value, ex=expire)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis set error for key {key}: {e}")
            return False
    
    async def get(self, key: str, parse_json: bool = True) -> Any:
        """Get value by key"""
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            if parse_json:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error(f"Redis get error for key {key}: {e}")
            return None
    
    async def delete(self, *keys: str) -> int:
        """Delete one or more keys"""
        try:
            return await self.redis.delete(*keys)
        except Exception as e:
            logger.error(f"Redis delete error for keys {keys}: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        try:
            return bool(await self.redis.exists(key))
        except Exception as e:
            logger.error(f"Redis exists error for key {key}: {e}")
            return False
    
    async def increment(self, key: str, amount: int = 1) -> int:
        """Increment a counter"""
        try:
            return await self.redis.incrby(key, amount)
        except Exception as e:
            logger.error(f"Redis increment error for key {key}: {e}")
            return 0
    
    async def set_hash(self, key: str, mapping: dict, expire: Optional[int] = None) -> bool:
        """Set hash fields"""
        try:
            # Convert values to strings for Redis
            str_mapping = {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                          for k, v in mapping.items()}
            
            result = await self.redis.hset(key, mapping=str_mapping)
            
            if expire:
                await self.redis.expire(key, expire)
            
            return bool(result)
        except Exception as e:
            logger.error(f"Redis hash set error for key {key}: {e}")
            return False
    
    async def get_hash(self, key: str) -> dict:
        """Get all hash fields"""
        try:
            result = await self.redis.hgetall(key)
            if not result:
                return {}
            
            # Parse JSON values
            parsed_result = {}
            for k, v in result.items():
                try:
                    parsed_result[k] = json.loads(v)
                except json.JSONDecodeError:
                    parsed_result[k] = v
            
            return parsed_result
        except Exception as e:
            logger.error(f"Redis hash get error for key {key}: {e}")
            return {}
    
    async def get_hash_field(self, key: str, field: str, parse_json: bool = True) -> Any:
        """Get specific hash field"""
        try:
            value = await self.redis.hget(key, field)
            if value is None:
                return None
            
            if parse_json:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error(f"Redis hash field get error for key {key}, field {field}: {e}")
            return None
    
    async def list_push(self, key: str, *values: Any) -> int:
        """Push values to list"""
        try:
            str_values = [json.dumps(v) if isinstance(v, (dict, list)) else str(v) 
                         for v in values]
            return await self.redis.lpush(key, *str_values)
        except Exception as e:
            logger.error(f"Redis list push error for key {key}: {e}")
            return 0
    
    async def list_pop(self, key: str, parse_json: bool = True) -> Any:
        """Pop value from list"""
        try:
            value = await self.redis.rpop(key)
            if value is None:
                return None
            
            if parse_json:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            logger.error(f"Redis list pop error for key {key}: {e}")
            return None
    
    async def list_range(self, key: str, start: int = 0, end: int = -1, parse_json: bool = True) -> list:
        """Get range of list elements"""
        try:
            values = await self.redis.lrange(key, start, end)
            if not values:
                return []
            
            if parse_json:
                parsed_values = []
                for value in values:
                    try:
                        parsed_values.append(json.loads(value))
                    except json.JSONDecodeError:
                        parsed_values.append(value)
                return parsed_values
            
            return values
        except Exception as e:
            logger.error(f"Redis list range error for key {key}: {e}")
            return []
    
    async def set_add(self, key: str, *members: Any) -> int:
        """Add members to set"""
        try:
            str_members = [json.dumps(m) if isinstance(m, (dict, list)) else str(m) 
                          for m in members]
            return await self.redis.sadd(key, *str_members)
        except Exception as e:
            logger.error(f"Redis set add error for key {key}: {e}")
            return 0
    
    async def set_members(self, key: str, parse_json: bool = True) -> set:
        """Get all set members"""
        try:
            members = await self.redis.smembers(key)
            if not members:
                return set()
            
            if parse_json:
                parsed_members = set()
                for member in members:
                    try:
                        parsed_members.add(json.loads(member))
                    except json.JSONDecodeError:
                        parsed_members.add(member)
                return parsed_members
            
            return members
        except Exception as e:
            logger.error(f"Redis set members error for key {key}: {e}")
            return set()
    
    async def publish(self, channel: str, message: Any) -> int:
        """Publish message to channel"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message)
            return await self.redis.publish(channel, message)
        except Exception as e:
            logger.error(f"Redis publish error for channel {channel}: {e}")
            return 0
    
    async def health_check(self) -> bool:
        """Check Redis connectivity"""
        try:
            response = await self.redis.ping()
            return response == "PONG"
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

# Global Redis client instance
redis_client = RedisClient()

async def init_redis():
    """Initialize Redis connection"""
    await redis_client.connect()

async def close_redis():
    """Close Redis connection"""
    await redis_client.disconnect()

async def get_redis() -> RedisClient:
    """FastAPI dependency for Redis client"""
    return redis_client