# 🚀 AI Agent Dashboard - Quick Start Guide

## Prerequisites
- Docker & Docker Compose installed
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- PostgreSQL 14+ (for local development)
- Redis 7+ (for local development)

## 🎯 Fastest Start (Docker)

```bash
# Clone and start everything with one command
./start.sh
```

Access the dashboard at: **http://localhost:5173**

## 🛠️ Local Development Setup

### Backend Setup
```bash
cd server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start FastAPI server
uvicorn app.main:app --reload --port 8000

# In another terminal, start Celery worker
celery -A app.celery_worker.celery_app worker --loglevel=info
```

### Frontend Setup
```bash
cd client
npm install
npm run dev
```

### Required Services
```bash
# PostgreSQL
docker run -d -p 5432:5432 \
  -e POSTGRES_USER=aiagent \
  -e POSTGRES_PASSWORD=aiagent123 \
  -e POSTGRES_DB=ai_dashboard \
  postgres:16-alpine

# Redis
docker run -d -p 6379:6379 redis:7-alpine
```

## 📊 Dashboard Features

### Radar View
- Real-time agent positioning
- Color-coded status indicators
- Animated sweep line
- Interactive tooltips

### Task Queue
- Sortable/filterable grid
- Real-time status updates
- Task reassignment
- Priority indicators

### Metrics Panel
- Tokens per second
- Cost tracking
- Completion rates
- Live updates via SSE

### Control Panel
- System start/pause/stop
- Throttle control (0-3x)
- Emergency stop
- System status indicator

## 🔧 Configuration

### Environment Variables
Copy `.env.example` to `.env` and adjust:
```env
DATABASE_URL=postgresql://aiagent:aiagent123@localhost:5432/ai_dashboard
REDIS_URL=redis://localhost:6379
VITE_API_URL=http://localhost:8000
```

### Port Configuration
- Frontend: 5173
- Backend API: 8000
- PostgreSQL: 5432
- Redis: 6379

## 📡 API Endpoints

### Core Endpoints
- `GET /api/agents` - List all agents
- `GET /api/tasks` - Get task queue
- `POST /api/tasks` - Create new task
- `GET /api/system/metrics` - System metrics
- `POST /api/system/run` - Start system
- `POST /api/system/pause-all` - Pause all agents
- `GET /api/stream` - SSE event stream

### Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🧪 Testing

```bash
# Frontend tests
cd client && npm test

# Backend tests
cd server && pytest

# E2E tests
npm run test:e2e
```

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Check what's using the port
   lsof -i :5173  # or :8000, :5432, :6379
   ```

2. **Database connection failed**
   ```bash
   # Check PostgreSQL is running
   docker ps | grep postgres
   
   # Check connection
   psql -h localhost -U aiagent -d ai_dashboard
   ```

3. **SSE not connecting**
   - Check CORS settings in backend
   - Verify frontend proxy configuration
   - Check browser console for errors

4. **Celery workers not processing**
   ```bash
   # Check worker status
   celery -A app.celery_worker.celery_app status
   
   # Check Redis connection
   redis-cli ping
   ```

## 🚀 Production Deployment

### Docker Compose Production
```bash
docker-compose -f docker-compose.prod.yml up -d
```

### Kubernetes
```bash
kubectl apply -f k8s/
```

### Environment-specific configs:
- Set `NODE_ENV=production`
- Use production database
- Configure SSL/TLS
- Set up monitoring (Prometheus/Grafana)
- Configure log aggregation

## 📚 Additional Resources

- [Architecture Documentation](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Contributing Guide](CONTRIBUTING.md)
- [Security Guidelines](SECURITY.md)

## 💬 Support

- GitHub Issues: [Report bugs](https://github.com/yourusername/ai-agent-dashboard/issues)
- Documentation: [Wiki](https://github.com/yourusername/ai-agent-dashboard/wiki)
- Discord: [Join community](https://discord.gg/aiagentdash)