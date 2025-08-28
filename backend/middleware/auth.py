import jwt
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status, Request, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db_session
from models.database import User, Session
from core.redis_client import redis_client

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

class AuthMiddleware:
    """Authentication and authorization middleware"""
    
    def __init__(self):
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.JWT_ALGORITHM
        self.expiration_hours = settings.JWT_EXPIRATION_HOURS
    
    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password"""
        return pwd_context.verify(plain_password, hashed_password)
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(hours=self.expiration_hours)
        to_encode.update({"exp": expire})
        
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    async def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token"""
        try:
            # Check if token is blacklisted
            blacklisted = await redis_client.get(f"blacklisted_token:{token}")
            if blacklisted:
                return None
            
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
            
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError:
            logger.warning("Invalid token")
            return None
    
    async def get_current_user(self, credentials: HTTPAuthorizationCredentials) -> Optional[User]:
        """Get current user from JWT token"""
        try:
            payload = await self.verify_token(credentials.credentials)
            if not payload:
                return None
            
            user_id = payload.get("user_id")
            if not user_id:
                return None
            
            async with get_db_session() as session:
                query = select(User).where(User.id == user_id, User.is_active == True)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                
                return user
                
        except Exception as e:
            logger.error(f"Error getting current user: {e}")
            return None
    
    async def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user credentials"""
        try:
            async with get_db_session() as session:
                query = select(User).where(User.username == username, User.is_active == True)
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                
                if user and self.verify_password(password, user.hashed_password):
                    return user
                
                return None
                
        except Exception as e:
            logger.error(f"Error authenticating user: {e}")
            return None
    
    async def create_user_session(self, user: User) -> str:
        """Create user session"""
        try:
            session_token = self.create_access_token({
                "user_id": str(user.id),
                "username": user.username,
                "is_admin": user.is_admin
            })
            
            # Store session in database
            async with get_db_session() as db_session:
                user_session = Session(
                    user_id=user.id,
                    session_token=session_token,
                    expires_at=datetime.utcnow() + timedelta(hours=self.expiration_hours),
                    is_active=True
                )
                db_session.add(user_session)
                await db_session.commit()
            
            # Cache session in Redis
            await redis_client.set(
                f"user_session:{session_token}",
                {
                    "user_id": str(user.id),
                    "username": user.username,
                    "is_admin": user.is_admin,
                    "created_at": datetime.utcnow().isoformat()
                },
                expire=self.expiration_hours * 3600
            )
            
            return session_token
            
        except Exception as e:
            logger.error(f"Error creating user session: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not create session"
            )
    
    async def invalidate_session(self, token: str):
        """Invalidate user session"""
        try:
            # Add to blacklist
            await redis_client.set(
                f"blacklisted_token:{token}",
                "true",
                expire=self.expiration_hours * 3600
            )
            
            # Remove from Redis cache
            await redis_client.delete(f"user_session:{token}")
            
            # Deactivate in database
            async with get_db_session() as session:
                from sqlalchemy import update
                await session.execute(
                    update(Session)
                    .where(Session.session_token == token)
                    .values(is_active=False)
                )
                await session.commit()
                
        except Exception as e:
            logger.error(f"Error invalidating session: {e}")
    
    async def require_auth(self, request: Request) -> User:
        """Require authentication for protected routes"""
        try:
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Missing or invalid authorization header",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            token = auth_header.split(" ")[1]
            credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            
            user = await self.get_current_user(credentials)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in auth requirement: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication error"
            )
    
    async def require_admin(self, request: Request) -> User:
        """Require admin authentication"""
        user = await self.require_auth(request)
        
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        return user

# Global auth instance
auth = AuthMiddleware()

# FastAPI dependency functions
async def get_current_user(credentials: HTTPAuthorizationCredentials = security) -> User:
    """FastAPI dependency for getting current user"""
    user = await auth.get_current_user(credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

async def get_current_active_user(current_user: User = get_current_user) -> User:
    """FastAPI dependency for getting current active user"""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user

async def get_admin_user(current_user: User = get_current_active_user) -> User:
    """FastAPI dependency for admin users"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return current_user