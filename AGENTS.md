# AI Agent Dashboard - AGENTS.md

## 🤖 Agent Specialization

**Primary Agent**: `ai-agent-dashboard-developer`  
**Domain**: Real-time monitoring dashboards, D3.js visualization, FastAPI + React integration  
**Expertise**: SSE streaming, MobX state management, radar-style UI components

## 🎯 Agent Instructions

### Core Responsibilities
1. **Real-Time Visualization Development**: D3.js radar components, interactive data visualization
2. **Full-Stack Integration**: FastAPI backend with React/TypeScript frontend coordination
3. **State Management**: MobX reactive patterns, SSE event handling
4. **Task Queue Management**: AG Grid integration, real-time data updates
5. **Performance Optimization**: SSE connection management, render optimization

### Development Patterns

#### Frontend Development (React/TypeScript)
```typescript
// MobX Store Pattern
class AgentRadarStore {
  @observable agents: Agent[] = []
  @observable connectionStatus: 'connected' | 'disconnected' = 'disconnected'
  
  @action updateAgent = (agent: Agent) => {
    const index = this.agents.findIndex(a => a.id === agent.id)
    if (index >= 0) this.agents[index] = agent
  }
}

// D3.js React Integration
const AgentRadar: React.FC = () => {
  const svgRef = useRef<SVGSVGElement>(null)
  const { agentStore } = useStore()
  
  useEffect(() => {
    if (!svgRef.current) return
    const svg = d3.select(svgRef.current)
    // D3 visualization logic
  }, [agentStore.agents])
}
```

#### Backend Development (FastAPI/Python)
```python
# SSE Endpoint Pattern
@app.get("/api/stream")
async def stream_events(request: Request):
    async def event_publisher():
        while True:
            if await request.is_disconnected():
                break
            # Fetch and yield data
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(0.1)
    
    return StreamingResponse(
        event_publisher(), 
        media_type="text/plain"
    )

# Celery Task Pattern
@celery.task
def process_agent_metrics(agent_id: str):
    # Process metrics and update database
    # Publish updates via Redis
    redis_client.publish("agent_updates", json.dumps(data))
```

### Code Quality Standards

#### TypeScript Configuration
- **Strict Mode**: Enabled with no implicit any
- **Coverage**: >90% for all components
- **Testing**: Jest + React Testing Library for components
- **Linting**: ESLint + Prettier with strict rules

#### Python Standards  
- **Type Hints**: Required for all functions
- **Coverage**: >85% with pytest
- **Formatting**: Black + isort for consistent style
- **Validation**: Pydantic for all data schemas

### Architecture Guidelines

#### Component Structure
```
components/
├── AgentRadar/
│   ├── AgentRadar.tsx       # Main component
│   ├── AgentRadar.css       # Component styles  
│   ├── hooks/               # Custom hooks
│   └── types.ts            # Component types
├── TaskQueue/               # AG Grid integration
├── MetricsPanel/           # Chart.js dashboards
└── ControlPanel/           # System controls
```

#### API Design Patterns
```python
# RESTful Resource Structure
/api/agents              # GET, POST - agent management
/api/agents/{id}         # GET, PUT, DELETE - specific agent
/api/agents/{id}/tasks   # GET - agent-specific tasks
/api/tasks              # GET, POST - task management
/api/stream             # GET - SSE endpoint
/api/metrics            # GET - performance metrics
```

### Real-Time Development

#### SSE Connection Management
```typescript
// SSE Client Pattern
class SSEClient {
  private eventSource: EventSource | null = null
  
  connect(url: string, onMessage: (data: any) => void) {
    this.eventSource = new EventSource(url)
    this.eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data)
      onMessage(data)
    }
    
    this.eventSource.onerror = () => {
      // Implement reconnection logic
      setTimeout(() => this.connect(url, onMessage), 5000)
    }
  }
}
```

#### MobX Reactive Patterns
```typescript
// Store Integration Pattern
const useSSEData = () => {
  const { rootStore } = useStore()
  
  useEffect(() => {
    const client = new SSEClient()
    client.connect('/api/stream', (data) => {
      switch (data.type) {
        case 'agent_update':
          rootStore.agentStore.updateAgent(data.payload)
          break
        case 'task_update':
          rootStore.taskStore.updateTask(data.payload)
          break
      }
    })
    
    return () => client.disconnect()
  }, [rootStore])
}
```

### Performance Requirements

#### Frontend Optimization
- **Render Performance**: <100ms for component updates
- **Memory Usage**: <50MB for dashboard with 100+ agents
- **Bundle Size**: <500KB main bundle, lazy-loaded components
- **Real-time Latency**: <500ms from server event to UI update

#### Backend Performance  
- **API Response Time**: <200ms for all endpoints
- **SSE Event Delivery**: <100ms from database update to client
- **Database Query Time**: <50ms for agent/task queries
- **Memory Usage**: <256MB per FastAPI worker process

### Testing Strategy

#### Frontend Testing Approach
```typescript
// Component Testing Pattern
describe('AgentRadar', () => {
  it('renders agents correctly', () => {
    const mockStore = createMockStore({ agents: mockAgents })
    render(
      <Provider store={mockStore}>
        <AgentRadar />
      </Provider>
    )
    
    expect(screen.getByTestId('radar-container')).toBeInTheDocument()
    expect(mockStore.agentStore.agents).toHaveLength(mockAgents.length)
  })
  
  it('updates on SSE events', async () => {
    const mockStore = createMockStore()
    mockSSEClient.emit('agent_update', mockAgentUpdate)
    
    await waitFor(() => {
      expect(mockStore.agentStore.agents).toContain(mockAgentUpdate)
    })
  })
})
```

#### Backend Testing Approach
```python
# API Testing Pattern
def test_agent_list_endpoint(client: TestClient, db: Session):
    response = client.get("/api/agents")
    assert response.status_code == 200
    assert len(response.json()) >= 0

def test_sse_endpoint(client: TestClient):
    with client.stream("GET", "/api/stream") as response:
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
        # Test SSE event delivery
```

### Security & Configuration

#### Environment Management
```bash
# Development Environment
VITE_API_URL=http://localhost:8000
VITE_SSE_ENDPOINT=http://localhost:8000/api/stream
DATABASE_URL=postgresql://user:password@localhost:5432/ai_dashboard
REDIS_URL=redis://localhost:6379

# Production Environment  
VITE_API_URL=https://api.dashboard.company.com
DATABASE_URL=$DATABASE_URL  # From environment
REDIS_URL=$REDIS_URL       # From environment
```

#### Security Configuration
```python
# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://dashboard.company.com"],
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"]
)

# Rate Limiting
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Implement Redis-based rate limiting
    pass
```

### Integration Requirements

#### QM0Dev Integration
- **Port Assignment**: Use `~/.qm0dev/port-manager.sh assign ai-agent-dashboard-api`
- **Health Checks**: Implement `/health` endpoint for CRAG monitoring
- **Database**: Use separate schema in existing PostgreSQL instance
- **Session Coordination**: Log activities via session-manager.sh

#### CRAG System Integration
```python
# Health Check Endpoint
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": await check_database_health(),
            "redis": await check_redis_health(),
            "celery": await check_celery_health()
        }
    }
```

### Deployment & Operations

#### Docker Configuration
```dockerfile
# Multi-stage build for frontend
FROM node:18-alpine as frontend-build
COPY client/package*.json ./
RUN npm ci --only=production
COPY client/ .
RUN npm run build

# Python backend
FROM python:3.11-slim
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server/ .
COPY --from=frontend-build /app/dist ./static
```

#### Development Workflow
```bash
# Full development setup
npm run dev                    # Start both frontend and backend
cd client && npm run test:watch  # Frontend test watcher
cd server && pytest --watch     # Backend test watcher

# Production build and deployment
npm run build                  # Build frontend
docker-compose up --build      # Container deployment
```

### Troubleshooting Guide

#### Common Issues & Solutions

**SSE Connection Failures**:
```bash
# Check Redis pub/sub
redis-cli monitor

# Verify CORS configuration
curl -H "Origin: http://localhost:5173" -v http://localhost:8000/api/stream
```

**Performance Issues**:
```bash
# Frontend performance profiling
npm run build:analyze

# Backend profiling with py-spy
pip install py-spy
py-spy record -o profile.svg -- python -m uvicorn app.main:app
```

**Database Connection Issues**:
```bash
# Check PostgreSQL connection
psql $DATABASE_URL -c "SELECT version();"

# Check Alembic migration status
cd server && alembic current
```

### Agent Communication

**Handoff Protocols**: When transitioning to other agents, provide:
1. Current component/API endpoint being worked on
2. Pending integration tests or functionality gaps  
3. Performance metrics or benchmarks to maintain
4. Any infrastructure dependencies (Redis, PostgreSQL state)

**Context Preservation**: Always include:
- Current SSE connection state
- MobX store structure and active subscriptions
- D3.js visualization state and data transformations
- AG Grid configuration and filter states