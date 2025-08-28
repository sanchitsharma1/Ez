from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum
import uuid

# Enums
class AgentMode(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# Base schemas
class BaseSchema(BaseModel):
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda dt: dt.isoformat(),
            uuid.UUID: lambda u: str(u)
        }

# User schemas
class UserBase(BaseSchema):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    full_name: Optional[str] = Field(None, max_length=255)

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseSchema):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[str] = Field(None, regex=r'^[\w\.-]+@[\w\.-]+\.\w+$')
    full_name: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None

class User(UserBase):
    id: uuid.UUID
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

# Authentication schemas
class TokenData(BaseSchema):
    user_id: uuid.UUID
    username: str
    exp: int

class LoginRequest(BaseSchema):
    username: str
    password: str

class LoginResponse(BaseSchema):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: User

# Chat schemas
class ChatRequest(BaseSchema):
    message: str = Field(..., min_length=1, max_length=10000)
    agent_id: Optional[str] = Field(None, regex=r'^(carol|alex|sofia|morgan|judy)$')
    session_id: Optional[str] = None
    mode: AgentMode = AgentMode.ONLINE
    voice_enabled: bool = False
    metadata: Optional[Dict[str, Any]] = None

class ChatResponse(BaseSchema):
    message: str
    agent_id: str
    session_id: str
    timestamp: datetime
    voice_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StreamChunk(BaseSchema):
    type: str  # "text", "voice", "metadata", "error"
    content: str
    agent_id: str
    session_id: str
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None

# Agent schemas
class AgentCapability(BaseSchema):
    name: str
    description: str
    enabled: bool = True

class AgentConfig(BaseSchema):
    id: str
    name: str
    nickname: Optional[str] = None
    description: Optional[str] = None
    persona: Optional[str] = None
    capabilities: List[AgentCapability] = []
    voice_id: Optional[str] = None
    is_active: bool = True
    config: Optional[Dict[str, Any]] = None

class AgentUpdate(BaseSchema):
    name: Optional[str] = None
    nickname: Optional[str] = None
    description: Optional[str] = None
    persona: Optional[str] = None
    capabilities: Optional[List[AgentCapability]] = None
    voice_id: Optional[str] = None
    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None

# Memory schemas
class MemoryEntry(BaseSchema):
    id: Optional[uuid.UUID] = None
    agent_id: Optional[str] = None
    session_id: Optional[uuid.UUID] = None
    content: str = Field(..., min_length=1)
    content_type: str = "conversation"
    tags: Optional[List[str]] = []
    importance_score: int = Field(1, ge=1, le=10)
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

class MemoryQuery(BaseSchema):
    query: str
    agent_id: Optional[str] = None
    content_type: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: int = Field(10, ge=1, le=100)
    threshold: float = Field(0.7, ge=0.0, le=1.0)

class MemorySearchResult(BaseSchema):
    memories: List[MemoryEntry]
    total: int
    query_time: float

# Task schemas
class TaskBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    priority: int = Field(1, ge=1, le=5)
    due_date: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

class TaskCreate(TaskBase):
    assigned_agent_id: Optional[str] = None

class TaskUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[int] = Field(None, ge=1, le=5)
    due_date: Optional[datetime] = None
    assigned_agent_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class Task(TaskBase):
    id: uuid.UUID
    user_id: uuid.UUID
    assigned_agent_id: Optional[str] = None
    status: TaskStatus
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

class TaskRequest(BaseSchema):
    action: str  # create, update, complete, delete
    task: Union[TaskCreate, TaskUpdate]
    task_id: Optional[uuid.UUID] = None

class TaskResponse(BaseSchema):
    success: bool
    task: Optional[Task] = None
    message: str

# Calendar schemas
class CalendarEventBase(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    location: Optional[str] = None
    attendees: Optional[List[str]] = []
    reminder_minutes: int = Field(15, ge=0)
    is_all_day: bool = False

class CalendarEventCreate(CalendarEventBase):
    pass

class CalendarEventUpdate(BaseSchema):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    location: Optional[str] = None
    attendees: Optional[List[str]] = None
    reminder_minutes: Optional[int] = Field(None, ge=0)
    is_all_day: Optional[bool] = None

class CalendarEvent(CalendarEventBase):
    id: uuid.UUID
    user_id: uuid.UUID
    google_event_id: Optional[str] = None
    created_by_agent: Optional[str] = None
    created_at: datetime
    updated_at: datetime

# Email schemas
class EmailMessage(BaseSchema):
    to: List[str] = Field(..., min_items=1)
    cc: Optional[List[str]] = []
    bcc: Optional[List[str]] = []
    subject: str = Field(..., min_length=1, max_length=500)
    body: str = Field(..., min_length=1)
    html_body: Optional[str] = None
    attachments: Optional[List[str]] = []  # File paths
    template_id: Optional[uuid.UUID] = None
    template_variables: Optional[Dict[str, Any]] = None

class EmailResponse(BaseSchema):
    success: bool
    message_id: Optional[str] = None
    message: str
    metadata: Optional[Dict[str, Any]] = None

# Approval schemas
class ApprovalRequest(BaseSchema):
    action_type: str
    action_description: str
    action_payload: Dict[str, Any]
    risk_level: RiskLevel = RiskLevel.MEDIUM
    expires_in_minutes: int = Field(60, ge=5, le=1440)  # 5 minutes to 24 hours

class JudgeVerdict(BaseSchema):
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    risk_assessment: RiskLevel
    recommendation: str  # "approve", "reject", "review"
    reasoning: str
    consensus_sources: List[str] = []

class ApprovalResponse(BaseSchema):
    decision: str  # "approved", "rejected"
    reason: Optional[str] = None

class Approval(BaseSchema):
    id: uuid.UUID
    user_id: uuid.UUID
    agent_id: str
    action_type: str
    action_description: str
    action_payload: Dict[str, Any]
    status: ApprovalStatus
    risk_level: RiskLevel
    judge_verdict: Optional[JudgeVerdict] = None
    user_decision: Optional[str] = None
    decision_reason: Optional[str] = None
    expires_at: datetime
    created_at: datetime

# System schemas (for Alex agent)
class SystemMetrics(BaseSchema):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, float]
    running_processes: int
    system_uptime: float
    timestamp: datetime

class SystemCommand(BaseSchema):
    command: str
    command_type: str
    risk_assessment: Optional[Dict[str, Any]] = None

class SystemCommandResult(BaseSchema):
    success: bool
    output: Optional[str] = None
    error_message: Optional[str] = None
    execution_time: float
    timestamp: datetime

# Voice schemas
class VoiceRequest(BaseSchema):
    text: str = Field(..., min_length=1)
    agent_id: str
    voice_settings: Optional[Dict[str, Any]] = None

class VoiceResponse(BaseSchema):
    audio_url: str
    duration: float
    format: str = "mp3"

class TranscriptionRequest(BaseSchema):
    audio_data: str  # Base64 encoded audio
    format: str = "wav"
    language: Optional[str] = "en"

class TranscriptionResponse(BaseSchema):
    text: str
    confidence: float
    language: str
    processing_time: float

# Knowledge Base schemas (for Sofia agent)
class KnowledgeEntry(BaseSchema):
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1)
    content_type: str = "document"
    source_file: Optional[str] = None
    tags: Optional[List[str]] = []

class KnowledgeQuery(BaseSchema):
    query: str = Field(..., min_length=1)
    content_type: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: int = Field(5, ge=1, le=20)

class KnowledgeResult(BaseSchema):
    results: List[KnowledgeEntry]
    total: int
    query_time: float
    summary: Optional[str] = None

# Financial schemas (for Morgan agent)
class FinancialQuery(BaseSchema):
    query_type: str  # stock_price, company_analysis, market_summary, etc.
    symbol: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None

class FinancialResult(BaseSchema):
    query_type: str
    data: Dict[str, Any]
    analysis: Optional[str] = None
    timestamp: datetime
    source: str

# WebSocket schemas
class WebSocketMessage(BaseSchema):
    type: str  # "chat", "voice", "system", "error"
    data: Dict[str, Any]
    timestamp: datetime

# Health check schemas
class HealthCheck(BaseSchema):
    status: str
    timestamp: datetime
    version: str

class ServiceStatus(BaseSchema):
    status: str
    services: Dict[str, str]
    timestamp: datetime