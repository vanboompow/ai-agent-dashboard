# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 🎯 Project Overview

**AI Agent Dashboard** - Real-time monitoring and orchestration dashboard for distributed AI agents with radar-style visualization.

**Status**: ✅ **NEW PROJECT** - Active Development  
**Priority**: 40% of development focus  
**Tech Stack**: React/TypeScript, FastAPI/Python, D3.js, MobX, AG Grid  

## 🚀 Development Commands

```bash
# Full stack development (recommended)
npm run dev                    # Runs both client and server concurrently

# Individual services
npm run dev:client            # Frontend only (Vite dev server)
npm run dev:server            # Backend only (uvicorn with reload)

# Alternative individual commands
cd client && npm run dev      # Client: Vite dev server on port 5173
cd server && uvicorn app.main:app --reload  # Server: FastAPI on port 8000

# Docker stack (complete environment)
./start.sh                    # Automated Docker setup script
docker-compose up --build     # Manual Docker setup
```

### Testing Commands

```bash
# Run all tests
npm test                      # Both client and server tests
npm run test:client          # Frontend tests only
npm run test:server          # Backend tests only

# Client testing
cd client && npm test        # Vitest unit tests
cd client && npm run lint    # ESLint type checking

# Server testing  
cd server && pytest          # All backend tests
cd server && pytest --cov   # With coverage reports
```

### Build & Production

```bash
npm run build               # Build client for production
cd client && npm run build  # TypeScript compilation + Vite build
cd client && npm run preview # Preview production build locally
```

## 🏗️ Architecture Overview

### Frontend Architecture (client/)
- **React 18** with TypeScript strict mode and Vite
- **MobX** state management with RootStore pattern (`stores/RootStore.ts`)
- **Server-Sent Events (SSE)** for real-time updates (`/api/stream` endpoint)
- **Component Architecture**: AgentRadar (D3.js), TaskQueue (AG Grid), MetricsPanel (Chart.js), ControlPanel

### Backend Architecture (server/)
- **FastAPI** with async/await patterns (`app/main.py`)
- **Router-based API structure** (`api/` directory with modular endpoints)
- **SQLAlchemy** models with Alembic migrations
- **Redis** integration for real-time event streaming
- **Celery** workers for background task processing

### Real-Time Data Flow
```
RootStore (MobX) ←→ EventSource (SSE) ←→ FastAPI Stream Router ←→ Redis Pub/Sub ←→ Celery Workers
```

### Key State Management Pattern
The `RootStore` class centralizes:
- Agent status and metrics tracking
- SSE connection lifecycle management  
- API calls with error handling
- Reactive UI updates via MobX observables

## 📁 Project Structure

```
ai-agent-dashboard/
├── client/                 # React TypeScript frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── AgentRadar/     # D3.js radar visualization
│   │   │   ├── TaskQueue/      # AG Grid task management
│   │   │   ├── MetricsPanel/   # Chart.js dashboards
│   │   │   └── ControlPanel/   # System controls
│   │   ├── stores/             # MobX state management
│   │   └── services/           # API integration
│   └── package.json
├── server/                 # FastAPI Python backend
│   ├── app/
│   │   ├── api/               # REST endpoints
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── services/          # Business logic
│   ├── celery_worker/         # Celery task processing
│   └── alembic/              # Database migrations
└── docker-compose.yml     # Full stack orchestration
```

## 🧰 Key Components

### AgentRadar Component
- **Technology**: D3.js with React integration
- **Purpose**: Real-time visualization of agent activity and status
- **Features**: Interactive nodes, status indicators, performance metrics

### TaskQueue Component  
- **Technology**: AG Grid with MobX integration
- **Purpose**: Interactive task management and monitoring
- **Features**: Sorting, filtering, real-time updates, bulk operations

### MetricsPanel Component
- **Technology**: Chart.js with responsive design
- **Purpose**: System performance and cost tracking
- **Features**: Token usage, response times, cost analysis

### ControlPanel Component
- **Technology**: React with global state management
- **Purpose**: System-wide controls and configuration
- **Features**: Throttling controls, global settings, emergency stops

## 🔄 Real-Time Features

### Server-Sent Events (SSE)
- **Endpoint**: `/api/stream`
- **Events**: agent_status, task_updates, metrics_data
- **Reliability**: Auto-reconnection, heartbeat monitoring

### State Management (MobX)
- **RootStore**: Central state coordination
- **Reactive Updates**: Automatic UI updates from SSE data
- **Performance**: Optimized renders, minimal re-computations

## 🧪 Testing Strategy

### Frontend Testing
```bash
cd client
npm run test              # Jest + React Testing Library
npm run test:coverage     # Coverage reports
npm run test:e2e         # Playwright integration tests
```

### Backend Testing
```bash
cd server
pytest                   # Unit tests with pytest
pytest --cov           # Coverage reports  
pytest -m integration  # Integration tests
```

### Performance Requirements
- **Frontend**: >90% test coverage, <100ms component renders
- **Backend**: >85% test coverage, <200ms API responses
- **Real-time**: <500ms SSE event delivery

## 🔧 Environment & Configuration

### Development Setup Requirements
- **Node.js**: >=18.0.0 (for Vite and modern React features)
- **Python**: >=3.9 (for FastAPI async support)
- **PostgreSQL**: >=14.0 (for database backend)
- **Redis**: >=6.0 (for pub/sub and Celery broker)

### Docker Development (Recommended)
The `docker-compose.yml` provides a complete development environment:
```bash
./start.sh                    # Automated setup with health checks
# Services: PostgreSQL (5432), Redis (6379), Backend (8000), Frontend (5173)
```

### Local Development Configuration
```bash
# Backend environment (server/.env)
DATABASE_URL=postgresql://aiagent:aiagent123@localhost:5432/ai_dashboard
REDIS_URL=redis://localhost:6379
CELERY_BROKER_URL=redis://redis:6379/0

# Frontend environment (client/.env.local)  
VITE_API_URL=http://localhost:8000
```

### Key API Endpoints
- **Health**: `GET /healthz` - Service health status
- **API Docs**: `http://localhost:8000/docs` (Swagger UI)
- **Stream**: `GET /api/stream` - SSE endpoint for real-time updates
- **Agents**: `GET /api/agents` - Agent status and management
- **Tasks**: `GET /api/tasks` - Task queue operations
- **System**: `POST /api/system/{run|pause-all|stop-new}` - System controls

### QM0Dev Integration
- **Port Assignment**: Use `~/.qm0dev/port-manager.sh` for all services
- **Database**: Integrate with QM0Dev PostgreSQL instance
- **Monitoring**: CRAG health checks via `/api/status` endpoint

## 🗄️ Database Operations

```bash
# Database migrations (server directory)
cd server && alembic upgrade head              # Apply migrations
cd server && alembic revision --autogenerate   # Create new migration
```

## 🚨 Troubleshooting & Common Issues

### Service Startup Issues
```bash
# Docker environment issues
./start.sh                     # Uses automated health checks
docker-compose logs -f         # View all service logs
docker-compose restart backend # Restart individual service

# Database connection issues  
brew services restart postgresql@14
docker-compose restart postgres

# Redis connection issues
brew services restart redis
docker-compose restart redis
```

### Port Conflicts (QM0Dev Integration)
```bash
~/.qm0dev/port-manager.sh list                      # Check current assignments
~/.qm0dev/port-manager.sh assign ai-agent-dashboard # Assign proper ports
```

## 🔍 Development Patterns & Key Files

### MobX State Management Pattern
- **Central Store**: `client/src/stores/RootStore.ts` - Single source of truth
- **SSE Integration**: Automatic reconnection and event handling
- **Reactive Updates**: UI automatically updates when store data changes

### Component Architecture
- **AgentRadar**: `client/src/components/AgentRadar/` - D3.js radar visualization
- **TaskQueue**: `client/src/components/TaskQueue/` - AG Grid task management  
- **MetricsPanel**: `client/src/components/MetricsPanel/` - Chart.js dashboards
- **ControlPanel**: `client/src/components/ControlPanel/` - System controls

### Backend Router Structure  
- **Main App**: `server/app/main.py` - FastAPI app with CORS and lifecycle
- **API Routes**: `server/app/api/` - Modular endpoint organization
- **Models**: `server/app/models/` - SQLAlchemy database models
- **Celery**: `server/app/celery_worker/` - Background task processing

