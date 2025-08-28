from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime

from core.database import get_db_session
from models.database import User
from models.schemas import (
    LoginRequest, LoginResponse, UserCreate, User as UserSchema,
    TokenData
)
from middleware.auth import auth, get_current_user, security

router = APIRouter()

@router.post("/register", response_model=UserSchema, status_code=status.HTTP_201_CREATED)
async def register_user(user_data: UserCreate):
    """Register a new user"""
    try:
        async with get_db_session() as session:
            # Check if username already exists
            existing_user_query = select(User).where(User.username == user_data.username)
            existing_user_result = await session.execute(existing_user_query)
            if existing_user_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already registered"
                )
            
            # Check if email already exists
            existing_email_query = select(User).where(User.email == user_data.email)
            existing_email_result = await session.execute(existing_email_query)
            if existing_email_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Create new user
            hashed_password = auth.hash_password(user_data.password)
            new_user = User(
                id=uuid.uuid4(),
                username=user_data.username,
                email=user_data.email,
                full_name=user_data.full_name,
                hashed_password=hashed_password,
                is_active=True,
                is_admin=False,
                created_at=datetime.utcnow()
            )
            
            session.add(new_user)
            await session.commit()
            await session.refresh(new_user)
            
            return UserSchema(
                id=new_user.id,
                username=new_user.username,
                email=new_user.email,
                full_name=new_user.full_name,
                is_active=new_user.is_active,
                is_admin=new_user.is_admin,
                created_at=new_user.created_at,
                updated_at=new_user.updated_at
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )

@router.post("/login", response_model=LoginResponse)
async def login_user(login_data: LoginRequest):
    """Authenticate user and return access token"""
    try:
        # Authenticate user
        user = await auth.authenticate_user(login_data.username, login_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Create session and token
        access_token = await auth.create_user_session(user)
        
        return LoginResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=auth.expiration_hours * 3600,
            user=UserSchema(
                id=user.id,
                username=user.username,
                email=user.email,
                full_name=user.full_name,
                is_active=user.is_active,
                is_admin=user.is_admin,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )

@router.post("/logout")
async def logout_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Logout user and invalidate token"""
    try:
        await auth.invalidate_session(credentials.credentials)
        return {"message": "Successfully logged out"}
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

@router.get("/me", response_model=UserSchema)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserSchema(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )

@router.post("/verify-token")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify if token is valid"""
    try:
        payload = await auth.verify_token(credentials.credentials)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token"
            )
        
        return {
            "valid": True,
            "user_id": payload.get("user_id"),
            "username": payload.get("username"),
            "expires": payload.get("exp")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        return {
            "valid": False,
            "error": str(e)
        }

@router.post("/refresh-token")
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh user access token"""
    try:
        # Create new token
        new_token = await auth.create_user_session(current_user)
        
        return {
            "access_token": new_token,
            "token_type": "bearer",
            "expires_in": auth.expiration_hours * 3600
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )