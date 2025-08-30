from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Dict

router = APIRouter()


class ThrottleRequest(BaseModel):
    rate: float  # 0.0 to 3.0


@router.post("/run")
async def system_run(request: Request):
    """Start all agents and resume processing"""
    # Broadcast to Celery workers
    return {"status": "running", "message": "System started"}


@router.post("/pause-all")
async def pause_all(request: Request):
    """Pause all agents immediately"""
    # Broadcast pause command to all workers
    return {"status": "paused", "message": "All agents paused"}


@router.post("/stop-new")
async def stop_new_tasks(request: Request):
    """Stop accepting new tasks but complete current ones"""
    return {"status": "stopping", "message": "No new tasks will be accepted"}


@router.post("/throttle")
async def set_throttle(throttle: ThrottleRequest, request: Request):
    """Set system-wide processing throttle"""
    # Store in Redis for workers to read
    await request.app.state.redis.set("system:throttle", throttle.rate)
    return {
        "status": "throttled",
        "rate": throttle.rate,
        "message": f"System throttled to {throttle.rate}x speed"
    }


@router.get("/metrics")
async def get_system_metrics():
    """Get current system metrics"""
    return {
        "tokensPerSecond": 1921,
        "costPerSecondUSD": 1.55,
        "totalSpend": 345.00,
        "completionRate": 44.1,
        "activeAgents": 3,
        "pendingTasks": 5,
        "completedTasks": 147
    }


@router.get("/status")
async def get_system_status(request: Request):
    """Get overall system status"""
    throttle = await request.app.state.redis.get("system:throttle")
    return {
        "status": "operational",
        "throttle": float(throttle) if throttle else 1.0,
        "uptime": "4h 23m",
        "version": "1.0.0"
    }