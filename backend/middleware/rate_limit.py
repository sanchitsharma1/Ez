import logging
import time
from typing import Optional, Dict, Any
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import asyncio

from core.redis_client import redis_client

logger = logging.getLogger(__name__)

class RateLimitMiddleware:
    """Rate limiting middleware using Redis for distributed rate limiting"""
    
    def __init__(
        self,
        calls: int = 100,
        period: int = 60,
        per_ip: bool = True,
        per_user: bool = True,
        skip_successful_requests: bool = False
    ):
        self.calls = calls
        self.period = period
        self.per_ip = per_ip
        self.per_user = per_user
        self.skip_successful_requests = skip_successful_requests
        
        # Different limits for different endpoints
        self.endpoint_limits = {
            "/api/chat": {"calls": 30, "period": 60},
            "/api/voice/transcribe": {"calls": 20, "period": 60},
            "/api/voice/synthesize": {"calls": 15, "period": 60},
            "/api/email/send": {"calls": 10, "period": 60},
            "/api/system/commands": {"calls": 5, "period": 300},  # 5 per 5 minutes
            "/health": {"calls": 1000, "period": 60},  # More lenient for health checks
        }
    
    async def __call__(self, request: Request, call_next):
        """Process rate limiting for the request"""
        try:
            # Skip rate limiting for certain paths
            if self._should_skip_rate_limit(request):
                response = await call_next(request)
                return response
            
            # Get rate limit configuration for this endpoint
            endpoint_config = self._get_endpoint_config(request)
            
            # Check rate limits
            rate_limit_result = await self._check_rate_limits(request, endpoint_config)
            
            if rate_limit_result["exceeded"]:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": rate_limit_result["message"],
                        "retry_after": rate_limit_result["retry_after"],
                        "limit": rate_limit_result["limit"],
                        "remaining": rate_limit_result["remaining"],
                        "reset_time": rate_limit_result["reset_time"]
                    },
                    headers={
                        "Retry-After": str(rate_limit_result["retry_after"]),
                        "X-RateLimit-Limit": str(rate_limit_result["limit"]),
                        "X-RateLimit-Remaining": str(rate_limit_result["remaining"]),
                        "X-RateLimit-Reset": str(rate_limit_result["reset_time"])
                    }
                )
            
            # Process the request
            start_time = time.time()
            response = await call_next(request)
            end_time = time.time()
            
            # Update rate limit counters (after successful request if configured)
            if not self.skip_successful_requests or response.status_code >= 400:
                await self._update_rate_limits(request, endpoint_config, end_time - start_time)
            
            # Add rate limit headers to response
            response.headers.update({
                "X-RateLimit-Limit": str(rate_limit_result["limit"]),
                "X-RateLimit-Remaining": str(max(0, rate_limit_result["remaining"] - 1)),
                "X-RateLimit-Reset": str(rate_limit_result["reset_time"])
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Error in rate limit middleware: {e}")
            # Continue processing if rate limiting fails
            response = await call_next(request)
            return response
    
    def _should_skip_rate_limit(self, request: Request) -> bool:
        """Check if rate limiting should be skipped for this request"""
        # Skip for health checks and static files
        skip_paths = [
            "/health",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico"
        ]
        
        return any(request.url.path.startswith(path) for path in skip_paths)
    
    def _get_endpoint_config(self, request: Request) -> Dict[str, int]:
        """Get rate limit configuration for the endpoint"""
        path = request.url.path
        
        # Check for exact matches first
        if path in self.endpoint_limits:
            return self.endpoint_limits[path]
        
        # Check for pattern matches
        for pattern, config in self.endpoint_limits.items():
            if path.startswith(pattern):
                return config
        
        # Return default configuration
        return {"calls": self.calls, "period": self.period}
    
    async def _check_rate_limits(self, request: Request, config: Dict[str, int]) -> Dict[str, Any]:
        """Check if request exceeds rate limits"""
        try:
            current_time = int(time.time())
            window_start = current_time - (current_time % config["period"])
            
            # Generate rate limit keys
            keys = await self._get_rate_limit_keys(request)
            
            exceeded = False
            remaining = config["calls"]
            
            for key in keys:
                # Get current count
                count_key = f"rate_limit:{key}:{window_start}"
                current_count = await redis_client.get(count_key) or 0
                
                if isinstance(current_count, (str, bytes)):
                    current_count = int(current_count)
                
                if current_count >= config["calls"]:
                    exceeded = True
                    remaining = 0
                    break
                
                remaining = min(remaining, config["calls"] - current_count)
            
            return {
                "exceeded": exceeded,
                "remaining": remaining,
                "limit": config["calls"],
                "reset_time": window_start + config["period"],
                "retry_after": config["period"] - (current_time % config["period"]) if exceeded else 0,
                "message": f"Rate limit of {config['calls']} requests per {config['period']} seconds exceeded" if exceeded else ""
            }
            
        except Exception as e:
            logger.error(f"Error checking rate limits: {e}")
            # Allow request if checking fails
            return {
                "exceeded": False,
                "remaining": config["calls"],
                "limit": config["calls"],
                "reset_time": int(time.time()) + config["period"],
                "retry_after": 0,
                "message": ""
            }
    
    async def _update_rate_limits(self, request: Request, config: Dict[str, int], response_time: float):
        """Update rate limit counters"""
        try:
            current_time = int(time.time())
            window_start = current_time - (current_time % config["period"])
            
            # Generate rate limit keys
            keys = await self._get_rate_limit_keys(request)
            
            for key in keys:
                count_key = f"rate_limit:{key}:{window_start}"
                
                # Increment counter
                await redis_client.incr(count_key)
                
                # Set expiration for cleanup
                await redis_client.expire(count_key, config["period"] + 60)  # Extra 60s buffer
            
            # Store response time metrics
            await self._store_response_metrics(request, response_time, current_time)
            
        except Exception as e:
            logger.error(f"Error updating rate limits: {e}")
    
    async def _get_rate_limit_keys(self, request: Request) -> list:
        """Generate rate limit keys for the request"""
        keys = []
        
        # IP-based rate limiting
        if self.per_ip:
            client_ip = self._get_client_ip(request)
            keys.append(f"ip:{client_ip}")
        
        # User-based rate limiting
        if self.per_user:
            user_id = await self._get_user_id(request)
            if user_id:
                keys.append(f"user:{user_id}")
        
        # Endpoint-based rate limiting
        endpoint = self._normalize_endpoint(request.url.path)
        keys.append(f"endpoint:{endpoint}")
        
        # Global rate limiting
        keys.append("global")
        
        return keys
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers first
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip.strip()
        
        # Fallback to client IP
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _get_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request"""
        try:
            # Try to get user ID from JWT token
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
                
                # Import here to avoid circular imports
                from middleware.auth import auth
                
                payload = await auth.verify_token(token)
                if payload:
                    return payload.get("user_id")
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting user ID: {e}")
            return None
    
    def _normalize_endpoint(self, path: str) -> str:
        """Normalize endpoint path for rate limiting"""
        # Remove query parameters
        if "?" in path:
            path = path.split("?")[0]
        
        # Replace dynamic segments with placeholders
        path_parts = path.split("/")
        normalized_parts = []
        
        for part in path_parts:
            if part == "":
                continue
            
            # Check if part looks like an ID (UUID, numeric, etc.)
            if self._is_dynamic_segment(part):
                normalized_parts.append("{id}")
            else:
                normalized_parts.append(part)
        
        return "/" + "/".join(normalized_parts)
    
    def _is_dynamic_segment(self, segment: str) -> bool:
        """Check if a path segment is dynamic (ID, UUID, etc.)"""
        # UUID pattern
        if len(segment) == 36 and segment.count("-") == 4:
            return True
        
        # Numeric ID
        if segment.isdigit():
            return True
        
        # Long alphanumeric strings (likely IDs)
        if len(segment) > 20 and segment.isalnum():
            return True
        
        return False
    
    async def _store_response_metrics(self, request: Request, response_time: float, timestamp: int):
        """Store response time metrics"""
        try:
            endpoint = self._normalize_endpoint(request.url.path)
            metrics_key = f"metrics:response_time:{endpoint}:{timestamp // 60}"  # Per minute
            
            # Store response time
            await redis_client.lpush(metrics_key, response_time)
            
            # Keep only last 100 response times per minute
            await redis_client.ltrim(metrics_key, 0, 99)
            
            # Set expiration (keep metrics for 1 hour)
            await redis_client.expire(metrics_key, 3600)
            
        except Exception as e:
            logger.error(f"Error storing response metrics: {e}")


class SlowApiMiddleware:
    """Additional rate limiting using slowapi (in-memory backup)"""
    
    def __init__(self):
        self.requests = {}
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    async def __call__(self, request: Request, call_next):
        """Simple in-memory rate limiting as backup"""
        try:
            await self._cleanup_old_entries()
            
            client_ip = self._get_client_ip(request)
            current_time = time.time()
            
            # Simple rate limiting: 1000 requests per hour per IP
            hour_window = int(current_time // 3600)
            key = f"{client_ip}:{hour_window}"
            
            if key not in self.requests:
                self.requests[key] = 0
            
            self.requests[key] += 1
            
            if self.requests[key] > 1000:  # 1000 per hour
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "error": "Rate limit exceeded",
                        "detail": "Too many requests from this IP address"
                    }
                )
            
            response = await call_next(request)
            return response
            
        except Exception as e:
            logger.error(f"Error in slow API middleware: {e}")
            response = await call_next(request)
            return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        if hasattr(request, "client") and request.client:
            return request.client.host
        
        return "unknown"
    
    async def _cleanup_old_entries(self):
        """Clean up old rate limiting entries"""
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        try:
            current_hour = int(current_time // 3600)
            
            # Remove entries older than 2 hours
            keys_to_remove = []
            for key in self.requests.keys():
                if ":" in key:
                    hour = int(key.split(":")[1])
                    if current_hour - hour > 2:
                        keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self.requests[key]
            
            self.last_cleanup = current_time
            
            logger.info(f"Cleaned up {len(keys_to_remove)} old rate limit entries")
            
        except Exception as e:
            logger.error(f"Error cleaning up rate limit entries: {e}")


# Rate limiter instances
rate_limiter = RateLimitMiddleware(
    calls=100,          # 100 requests per minute default
    period=60,          # 1 minute window
    per_ip=True,        # Limit per IP
    per_user=True,      # Limit per user
    skip_successful_requests=False
)

slow_limiter = SlowApiMiddleware()


async def get_rate_limit_stats(ip_address: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
    """Get current rate limit statistics"""
    try:
        current_time = int(time.time())
        stats = {}
        
        if ip_address:
            # Get IP-based stats
            window_start = current_time - (current_time % 60)
            ip_key = f"rate_limit:ip:{ip_address}:{window_start}"
            ip_count = await redis_client.get(ip_key) or 0
            
            stats["ip"] = {
                "current_count": int(ip_count) if isinstance(ip_count, (str, bytes)) else ip_count,
                "limit": 100,
                "remaining": max(0, 100 - (int(ip_count) if isinstance(ip_count, (str, bytes)) else ip_count)),
                "window_start": window_start,
                "window_end": window_start + 60
            }
        
        if user_id:
            # Get user-based stats
            window_start = current_time - (current_time % 60)
            user_key = f"rate_limit:user:{user_id}:{window_start}"
            user_count = await redis_client.get(user_key) or 0
            
            stats["user"] = {
                "current_count": int(user_count) if isinstance(user_count, (str, bytes)) else user_count,
                "limit": 100,
                "remaining": max(0, 100 - (int(user_count) if isinstance(user_count, (str, bytes)) else user_count)),
                "window_start": window_start,
                "window_end": window_start + 60
            }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting rate limit stats: {e}")
        return {}