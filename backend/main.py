from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="SupremeAI Multi-Agent Assistant",
    description="Production-grade personal assistant with multiple specialized agents",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "service": "SupremeAI Backend"
    }

@app.get("/api/status")
async def status_check():
    """Detailed status check"""
    return {
        "status": "operational",
        "services": {
            "database": "ready",
            "redis": "ready", 
            "agents": "ready",
            "memory_broker": "ready"
        },
        "timestamp": datetime.utcnow().isoformat()
    }

# Basic API endpoints
@app.get("/api/agents")
async def list_agents():
    """List all available agents"""
    return {
        "agents": [
            {"id": "carol", "name": "Carol", "status": "active", "description": "Task Management Assistant"},
            {"id": "alex", "name": "Alex", "status": "active", "description": "Communications Manager"},
            {"id": "sofia", "name": "Sofia", "status": "active", "description": "Research Specialist"},
            {"id": "morgan", "name": "Morgan", "status": "active", "description": "Creative Assistant"},
            {"id": "judy", "name": "Judy", "status": "active", "description": "Executive Support"}
        ]
    }

class ChatRequest(BaseModel):
    message: str
    agent_id: str = "carol"
    session_id: str = ""
    mode: str = "online"
    voice_enabled: bool = False

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Handle chat messages"""
    try:
        # Simple response based on the message
        response_message = f"I received your message: '{request.message}'. I'm a basic implementation and will be enhanced with full AI capabilities soon!"
        
        return {
            "message": response_message,
            "agent_id": request.agent_id,
            "session_id": request.session_id or f"session_{int(datetime.utcnow().timestamp())}",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "mode": request.mode,
                "voice_enabled": request.voice_enabled
            }
        }
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/memory")
async def get_memories():
    """Get memories - basic implementation"""
    return {"memories": [], "total": 0}

@app.get("/api/tasks")
async def get_tasks():
    """Get tasks - basic implementation"""
    return {"tasks": [], "total": 0}

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "SupremeAI Multi-Agent Assistant API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )