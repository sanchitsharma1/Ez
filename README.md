# Multi-Agent Personal Assistant

A production-grade, containerized personal assistant system with multiple specialized AI agents, featuring hybrid online/offline capabilities, voice interaction, and comprehensive integrations.

## 🏗️ Architecture

The system consists of 5 specialized agents orchestrated through LangGraph:

- **Carol Garcia**: Executive assistant and main coordinator
- **Alex**: System monitoring and operations specialist  
- **Sofia**: Knowledge management and content creation
- **Morgan**: Financial analysis and market intelligence
- **Judy**: Decision validation and consensus building

## ✨ Features

### Core Capabilities
- 🤖 **Multi-Agent Orchestration** - LangGraph-based intelligent routing
- 🎙️ **Voice Interaction** - Speech-to-text and text-to-speech with VAD
- 🌐 **Hybrid Mode** - Online (OpenAI/Perplexity) and offline (Ollama) operation
- 🧠 **Advanced Memory** - Persistent context with Letta + Qdrant vector search
- ✅ **Approval System** - User approval for sensitive actions
- 📊 **Real-time Monitoring** - Prometheus + Grafana dashboards

### Integrations
- 📧 **Email** - Gmail and Zoho Mail management
- 📅 **Calendar** - Google Calendar synchronization
- 📱 **WhatsApp** - Business API integration
- 💼 **Productivity** - Task management and scheduling
- 🔍 **Financial** - Market data and analysis (yfinance)

### Production Features
- 🐳 **Containerized** - Complete Docker Compose setup
- 🔒 **Secure** - OAuth2, JWT authentication, TLS support
- 📈 **Observable** - Comprehensive logging and metrics
- 🚀 **Scalable** - Async architecture with Redis caching
- 🔧 **Configurable** - Environment-based configuration

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for development)
- Node.js 18+ (for development)
- Git

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/multi-agent-assistant.git
cd multi-agent-assistant
```

### 2. Environment Setup
```bash
# Copy environment template
cp .env.template .env

# Edit .env file with your API keys and configuration
nano .env
```

### 3. Start Services
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Check service health
docker-compose ps
```

### 4. Access Applications
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Grafana Dashboard**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090
- **n8n Workflows**: http://localhost:5678 (admin/password)

## 📊 Service Overview

| Service | Port | Description |
|---------|------|-------------|
| Frontend | 3000 | Next.js web interface |
| API | 8000 | FastAPI backend |
| PostgreSQL | 5432 | Primary database |
| Redis | 6379 | Caching and sessions |
| Qdrant | 6333 | Vector database |
| Ollama | 11434 | Local LLM server |
| Prometheus | 9090 | Metrics collection |
| Grafana | 3001 | Monitoring dashboards |
| n8n | 5678 | Workflow automation |

## 🔧 Configuration

### API Keys Required

1. **OpenAI** (for online mode)
   ```env
   OPENAI_API_KEY=sk-your-openai-key
   ```

2. **ElevenLabs** (for voice synthesis)
   ```env
   ELEVENLABS_API_KEY=your-elevenlabs-key
   ```

3. **Google APIs** (for Gmail/Calendar)
   ```env
   GMAIL_CLIENT_ID=your-client-id
   GMAIL_CLIENT_SECRET=your-client-secret
   GCAL_CLIENT_ID=your-calendar-client-id
   GCAL_CLIENT_SECRET=your-calendar-secret
   ```

4. **WhatsApp Business** (optional)
   ```env
   WHATSAPP_ACCESS_TOKEN=your-access-token
   WHATSAPP_PHONE_NUMBER_ID=your-phone-id
   ```

### Agent Configuration

Agents can be customized through the UI or API:

```python
# Update agent persona
PUT /api/agents/carol
{
  "persona": "Your custom persona description",
  "voice_id": "custom-voice-id",
  "capabilities": [...]
}
```

## 💬 Usage Examples

### Basic Chat
```
User: "Schedule a meeting with John tomorrow at 2pm"
Carol: "I'll schedule a meeting with John for tomorrow at 2:00 PM. 
       Should I send him an email invitation?"
```

### System Monitoring
```
User: "Check system performance"
Alex: "System Status:
      - CPU Usage: 45%
      - Memory: 2.1GB/8GB (26%)
      - Disk: 120GB/500GB (24%)
      - All services operational"
```

### Document Analysis
```
User: "Summarize this quarterly report" [uploads PDF]
Sofia: "I've analyzed your Q3 report. Key findings:
       - Revenue increased 12% YoY
       - Customer acquisition up 8%
       - Profit margins improved to 15.2%
       [Detailed summary follows...]"
```

### Financial Analysis
```
User: "What's the latest on AAPL stock?"
Morgan: "Apple (AAPL) Analysis:
        - Current: $185.23 (+2.4%)
        - 52-week range: $124.17 - $199.62
        - Market cap: $2.89T
        - Strong quarterly earnings, iPhone sales solid"
```

## 🎙️ Voice Features

### Voice Commands
- "Hey Assistant" - Wake phrase
- Natural speech recognition with VAD
- Agent-specific voices (ElevenLabs)
- Barge-in interruption support

### Voice Settings
```javascript
// Enable voice mode
setVoiceEnabled(true);

// Configure per agent
{
  "carol": "professional female voice",
  "alex": "technical male voice",
  "sofia": "articulate female voice"
}
```

## 🔐 Security

### Authentication
- JWT-based authentication
- OAuth2 integration for external services
- Session management with Redis
- Role-based access control (RBAC)

### Approval System
Sensitive actions require user approval:
- Sending emails
- System commands (Alex)
- Financial operations
- External API calls

### Data Protection
- TLS encryption in production
- Database connection encryption
- API key secure storage
- File upload validation

## 📊 Monitoring & Observability

### Metrics (Prometheus)
- Request latency and throughput
- Agent response times
- System resource usage
- Error rates and types
- Memory usage patterns

### Dashboards (Grafana)
- System overview
- Agent performance
- API metrics
- Database health
- User activity

### Logging
- Structured logging with correlation IDs
- Error tracking and alerting
- Performance profiling
- Security audit logs

## 🛠️ Development

### Local Development Setup

1. **Backend Development**
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Frontend Development**
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

3. **Database Migrations**
   ```bash
   # Create migration
   alembic revision --autogenerate -m "Description"
   
   # Apply migrations
   alembic upgrade head
   ```

### Testing

```bash
# Backend tests
cd backend
pytest tests/ -v --cov

# Frontend tests
cd frontend
npm test
```

### Code Quality

```bash
# Backend linting
ruff check .
black . --check
mypy .

# Frontend linting
npm run lint
npm run type-check
```

## 🔧 Troubleshooting

### Common Issues

1. **Services not starting**
   ```bash
   # Check logs
   docker-compose logs [service-name]
   
   # Restart specific service
   docker-compose restart [service-name]
   ```

2. **Database connection issues**
   ```bash
   # Reset database
   docker-compose down -v
   docker-compose up -d postgres
   ```

3. **Ollama model issues**
   ```bash
   # Download models manually
   docker exec -it multi-agent-assistant_ollama_1 ollama pull llama3:8b
   ```

4. **Voice not working**
   - Check browser permissions for microphone
   - Ensure HTTPS in production
   - Verify ElevenLabs API key

### Performance Optimization

1. **Memory Usage**
   - Adjust `MEMORY_RETENTION_DAYS`
   - Configure garbage collection
   - Monitor vector database size

2. **Response Time**
   - Use offline mode for faster responses
   - Cache frequent queries
   - Optimize model selection

## 📈 Scaling

### Production Deployment

1. **Load Balancing**
   ```yaml
   # Add to docker-compose.yml
   nginx:
     image: nginx:alpine
     ports:
       - "80:80"
       - "443:443"
   ```

2. **High Availability**
   - PostgreSQL cluster
   - Redis Sentinel
   - Multiple API instances

3. **Resource Limits**
   ```yaml
   deploy:
     resources:
       limits:
         memory: 2G
         cpus: '1.0'
   ```