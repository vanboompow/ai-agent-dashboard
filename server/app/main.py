from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import redis.asyncio as redis
from .config import settings
from .api import agents, tasks, system, stream, websocket


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    from .services.redis_pubsub import initialize_redis
    from .api.stream import cleanup_sse_connections
    from .api.websocket import cleanup_websocket_connections
    
    # Initialize Redis connection manager
    redis_manager = await initialize_redis(settings.redis_url)
    app.state.redis_manager = redis_manager
    
    # Keep backward compatibility
    app.state.redis = redis_manager.redis_client
    
    yield
    
    # Shutdown
    await cleanup_sse_connections()
    await cleanup_websocket_connections()
    await redis_manager.close()


app = FastAPI(
    title="AI Agent Dashboard API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(system.router, prefix="/api/system", tags=["system"])
app.include_router(stream.router, prefix="/api/stream", tags=["stream"])
app.include_router(websocket.router, prefix="/api/websocket", tags=["websocket"])


@app.get("/healthz")
async def health_check():
    return {"status": "healthy", "service": "ai-agent-dashboard"}


@app.get("/")
async def root():
    return {
        "message": "AI Agent Dashboard API",
        "docs": "/docs",
        "redoc": "/redoc"
    }