from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid
import enum

Base = declarative_base()

class TaskStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class ApprovalStatus(enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class AgentType(enum.Enum):
    CAROL = "carol"
    ALEX = "alex"
    SOFIA = "sofia"
    MORGAN = "morgan"
    JUDY = "judy"

class User(Base):
    """User model"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # OAuth tokens
    gmail_token = Column(JSON, nullable=True)
    zoho_token = Column(JSON, nullable=True)
    gcal_token = Column(JSON, nullable=True)
    
    # Relationships
    sessions = relationship("Session", back_populates="user")
    tasks = relationship("Task", back_populates="user")
    calendar_events = relationship("CalendarEvent", back_populates="user")
    approvals = relationship("Approval", back_populates="user")

class Session(Base):
    """User session model"""
    __tablename__ = "sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    session_token = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    conversations = relationship("Conversation", back_populates="session")

class Agent(Base):
    """Agent configuration model"""
    __tablename__ = "agents"
    
    id = Column(String(50), primary_key=True)  # carol, alex, sofia, morgan, judy
    name = Column(String(100), nullable=False)
    nickname = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    persona = Column(Text, nullable=True)
    capabilities = Column(JSON, nullable=True)
    voice_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    config = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    conversations = relationship("Conversation", back_populates="agent")
    tasks = relationship("Task", back_populates="assigned_agent")

class Conversation(Base):
    """Conversation model"""
    __tablename__ = "conversations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=False)
    agent_id = Column(String(50), ForeignKey("agents.id"), nullable=False)
    user_message = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    session = relationship("Session", back_populates="conversations")
    agent = relationship("Agent", back_populates="conversations")

class Memory(Base):
    """Memory storage model"""
    __tablename__ = "memories"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String(50), ForeignKey("agents.id"), nullable=True)
    session_id = Column(UUID(as_uuid=True), ForeignKey("sessions.id"), nullable=True)
    content = Column(Text, nullable=False)
    content_type = Column(String(50), nullable=False)  # conversation, fact, task, etc.
    tags = Column(JSON, nullable=True)
    importance_score = Column(Integer, default=1)  # 1-10
    vector_id = Column(String(255), nullable=True)  # Qdrant vector ID
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)

class Task(Base):
    """Task management model"""
    __tablename__ = "tasks"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    assigned_agent_id = Column(String(50), ForeignKey("agents.id"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING)
    priority = Column(Integer, default=1)  # 1-5
    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="tasks")
    assigned_agent = relationship("Agent", back_populates="tasks")

class CalendarEvent(Base):
    """Calendar event model"""
    __tablename__ = "calendar_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    google_event_id = Column(String(255), nullable=True)  # Google Calendar ID
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    location = Column(String(255), nullable=True)
    attendees = Column(JSON, nullable=True)
    reminder_minutes = Column(Integer, default=15)
    is_all_day = Column(Boolean, default=False)
    created_by_agent = Column(String(50), nullable=True)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="calendar_events")

class Approval(Base):
    """Approval request model"""
    __tablename__ = "approvals"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    agent_id = Column(String(50), ForeignKey("agents.id"), nullable=False)
    action_type = Column(String(100), nullable=False)  # send_email, run_command, etc.
    action_description = Column(Text, nullable=False)
    action_payload = Column(JSON, nullable=False)
    status = Column(Enum(ApprovalStatus), default=ApprovalStatus.PENDING)
    risk_level = Column(String(20), default="medium")  # low, medium, high, critical
    judge_verdict = Column(JSON, nullable=True)  # Judy's assessment
    user_decision = Column(String(20), nullable=True)  # approved, rejected
    decision_reason = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="approvals")

class SystemMetric(Base):
    """System metrics model (for Alex agent)"""
    __tablename__ = "system_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(String(255), nullable=False)
    metric_unit = Column(String(50), nullable=True)
    metric_type = Column(String(50), nullable=False)  # cpu, memory, disk, network, etc.
    host_name = Column(String(255), nullable=False)
    metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class EmailTemplate(Base):
    """Email template model"""
    __tablename__ = "email_templates"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    subject_template = Column(String(500), nullable=False)
    body_template = Column(Text, nullable=False)
    template_variables = Column(JSON, nullable=True)
    created_by_agent = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class KnowledgeBase(Base):
    """Knowledge base entries (for Sofia agent)"""
    __tablename__ = "knowledge_base"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    content_type = Column(String(50), nullable=False)  # document, summary, analysis, etc.
    source_file = Column(String(500), nullable=True)
    tags = Column(JSON, nullable=True)
    vector_id = Column(String(255), nullable=True)  # Qdrant vector ID
    created_by_agent = Column(String(50), default="sofia")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class SystemCommand(Base):
    """System command history (for Alex agent)"""
    __tablename__ = "system_commands"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    command = Column(Text, nullable=False)
    command_type = Column(String(50), nullable=False)
    approval_id = Column(UUID(as_uuid=True), ForeignKey("approvals.id"), nullable=True)
    executed_by = Column(String(50), default="alex")
    execution_status = Column(String(20), nullable=False)  # success, failed, denied
    output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    risk_assessment = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime, nullable=True)