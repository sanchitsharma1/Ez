from pydantic_settings import BaseSettings
from typing import List, Optional
import os
from pathlib import Path

class Settings(BaseSettings):
    """Application settings"""
    
    # Basic app settings
    APP_NAME: str = "Multi-Agent Personal Assistant"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    
    # API settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api"
    
    # CORS settings
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://localhost:3000",
        "https://localhost:8000"
    ]
    
    # Database settings
    DATABASE_URL: str = "postgresql://postgres:password@postgres:5432/assistant_db"
    DATABASE_ECHO: bool = False
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis settings
    REDIS_URL: str = "redis://redis:6379"
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTIONS: int = 20
    
    # Qdrant settings
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_COLLECTION_NAME: str = "assistant_memories"
    
    # Ollama settings
    OLLAMA_URL: str = "http://ollama:11434"
    DEFAULT_LOCAL_MODEL: str = "llama3:8b"
    
    # OpenAI settings
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_DEFAULT_MODEL: str = "gpt-4-turbo-preview"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-large"
    
    # Perplexity settings
    PERPLEXITY_API_KEY: Optional[str] = None
    
    # ElevenLabs settings
    ELEVENLABS_API_KEY: Optional[str] = None
    ELEVENLABS_VOICE_CAROL: str = "EXAVITQu4vr4xnSDxMaL"  # Female voice
    ELEVENLABS_VOICE_SOFIA: str = "21m00Tcm4TlvDq8ikWAM"  # Female voice
    ELEVENLABS_VOICE_JUDY: str = "AZnzlk1XvdvUeBnXmlld"   # Female voice
    ELEVENLABS_VOICE_ALEX: str = "ErXwobaYiN019PkySvjV"   # Male voice
    ELEVENLABS_VOICE_MORGAN: str = "VR6AewLTigWG4xSOukaG" # Male voice
    
    # Email settings (Gmail)
    GMAIL_CLIENT_ID: Optional[str] = None
    GMAIL_CLIENT_SECRET: Optional[str] = None
    GMAIL_REDIRECT_URI: str = "http://localhost:8000/auth/gmail/callback"
    
    # Email settings (Zoho)
    ZOHO_CLIENT_ID: Optional[str] = None
    ZOHO_CLIENT_SECRET: Optional[str] = None
    ZOHO_REDIRECT_URI: str = "http://localhost:8000/auth/zoho/callback"
    
    # Google Calendar settings
    GCAL_CLIENT_ID: Optional[str] = None
    GCAL_CLIENT_SECRET: Optional[str] = None
    GCAL_REDIRECT_URI: str = "http://localhost:8000/auth/gcal/callback"
    
    # WhatsApp Business settings
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    WHATSAPP_PHONE_NUMBER_ID: Optional[str] = None
    WHATSAPP_WEBHOOK_VERIFY_TOKEN: Optional[str] = None
    
    # Security settings
    SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # File upload settings
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_FILE_TYPES: List[str] = [
        ".pdf", ".txt", ".docx", ".doc", ".rtf",
        ".wav", ".mp3", ".mp4", ".flac", ".ogg"
    ]
    UPLOAD_DIR: str = "uploads"
    
    # Memory settings
    MEMORY_RETENTION_DAYS: int = 365
    MAX_CONVERSATION_LENGTH: int = 1000
    MEMORY_SYNC_INTERVAL: int = 300  # 5 minutes
    
    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW: int = 60  # seconds
    
    # System monitoring (Alex agent)
    SYSTEM_MONITORING_INTERVAL: int = 60  # seconds
    SYSTEM_METRICS_RETENTION: int = 7  # days
    
    # Prometheus settings
    PROMETHEUS_URL: str = "http://prometheus:9090"
    
    # Grafana settings
    GRAFANA_URL: str = "http://grafana:3000"
    GRAFANA_USER: str = "admin"
    GRAFANA_PASSWORD: str = "admin"
    
    # Logging settings
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    LOG_FILE: str = "logs/assistant.log"
    
    # Development settings
    RELOAD: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Create necessary directories
def create_directories():
    """Create necessary directories if they don't exist"""
    directories = [
        settings.UPLOAD_DIR,
        "logs",
        "data",
        "cache"
    ]
    
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)

create_directories()