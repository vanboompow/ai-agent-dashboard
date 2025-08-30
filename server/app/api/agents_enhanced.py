from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
import uuid
import random
import math

from app.services.agent_service import AgentService
from app.services.metric_service import MetricService
from app.models import AgentStatus
from pydantic import BaseModel

router = APIRouter()

# Mock database dependency for now
def get_db():
    return None


class AgentResponse(BaseModel):
    agentId: str
    status: str
    taskCategory: Optional[str] = None
    currentTask: Optional[str] = None
    elapsedTime: int
    angle: Optional[float] = None
    distance: Optional[float] = None
    hostname: Optional[str] = None
    tasksCompleted: Optional[int] = None
    tokensProcessed: Optional[int] = None
    uptime: Optional[str] = None
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    cpu_usage_percent: Optional[float] = None
    memory_usage_mb: Optional[float] = None
    average_response_time_ms: Optional[float] = None


class AgentCreate(BaseModel):
    agent_name: str
    agent_type: str
    hostname: str
    capabilities: Optional[List[str]] = []
    max_concurrent_tasks: int = 1
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None


def generate_radar_position(agent_id: str, status: str) -> tuple[float, float]:
    """Generate consistent radar position based on agent ID and status"""
    # Use agent_id hash for consistent positioning
    hash_val = hash(agent_id) % 360
    
    # Adjust distance based on status
    distance_map = {
        "working": 0.7,
        "idle": 0.4,
        "paused": 0.3,
        "error": 0.9,
        "offline": 0.2
    }
    
    distance = distance_map.get(status, 0.5)
    # Add some randomness for visual appeal
    distance += random.uniform(-0.1, 0.1)
    distance = max(0.1, min(0.9, distance))  # Clamp between 0.1 and 0.9
    
    return hash_val, distance


@router.get("/", response_model=List[AgentResponse])
async def get_agents(
    status: Optional[str] = None,
    agent_type: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get all registered agents with their current status"""
    # For now, return enhanced mock data that matches the new schema
    mock_agents = [
        {
            "agentId": "E-3",
            "status": "working",
            "taskCategory": "engineering",
            "currentTask": "Verify Alignment & Vision",
            "elapsedTime": 125,
            "angle": 45,
            "distance": 0.6,
            "hostname": "worker-e3",
            "tasksCompleted": 47,
            "tokensProcessed": 234567,
            "uptime": "4h 23m",
            "agent_name": "Engineering Agent E-3",
            "agent_type": "code_generator",
            "cpu_usage_percent": 65.2,
            "memory_usage_mb": 512.8,
            "average_response_time_ms": 1250.5
        },
        {
            "agentId": "S-2",
            "status": "idle",
            "taskCategory": "design",
            "currentTask": None,
            "elapsedTime": 0,
            "angle": 135,
            "distance": 0.4,
            "hostname": "worker-s2",
            "tasksCompleted": 23,
            "tokensProcessed": 89432,
            "uptime": "2h 15m",
            "agent_name": "Design Agent S-2",
            "agent_type": "text_processor",
            "cpu_usage_percent": 12.1,
            "memory_usage_mb": 256.3,
            "average_response_time_ms": 890.2
        },
        {
            "agentId": "P-4",
            "status": "working",
            "taskCategory": "product",
            "currentTask": "Execute Spec and MP Align",
            "elapsedTime": 89,
            "angle": 225,
            "distance": 0.5,
            "hostname": "worker-p4",
            "tasksCompleted": 35,
            "tokensProcessed": 156789,
            "uptime": "6h 45m",
            "agent_name": "Product Agent P-4",
            "agent_type": "data_analyst",
            "cpu_usage_percent": 78.4,
            "memory_usage_mb": 768.1,
            "average_response_time_ms": 1456.7
        }
    ]
    
    return [AgentResponse(**agent) for agent in mock_agents]


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Get specific agent details"""
    # Enhanced mock response
    angle, distance = generate_radar_position(agent_id, "working")
    
    return AgentResponse(
        agentId=agent_id,
        status="working",
        hostname=f"worker-{agent_id.lower()}",
        taskCategory="engineering",
        currentTask="Processing task",
        tasksCompleted=47,
        tokensProcessed=234567,
        uptime="4h 23m",
        elapsedTime=125,
        angle=angle,
        distance=distance,
        agent_name=f"Agent {agent_id}",
        agent_type="code_generator",
        cpu_usage_percent=65.2,
        memory_usage_mb=512.8,
        average_response_time_ms=1250.5
    )


@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str, db: Session = Depends(get_db)):
    """Pause a specific agent"""
    return {"message": f"Agent {agent_id} paused", "status": "paused"}


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str, db: Session = Depends(get_db)):
    """Resume a specific agent"""
    return {"message": f"Agent {agent_id} resumed", "status": "working"}


@router.post("/{agent_id}/heartbeat")
async def agent_heartbeat(
    agent_id: str,
    cpu_usage: Optional[float] = None,
    memory_usage: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db)
):
    """Update agent heartbeat with optional resource metrics"""
    return {"message": "Heartbeat updated", "timestamp": datetime.utcnow()}


@router.get("/{agent_id}/metrics")
async def get_agent_metrics(agent_id: str, hours: int = 24, db: Session = Depends(get_db)):
    """Get agent performance metrics"""
    # Mock metrics data
    return {
        "agent_id": agent_id,
        "metrics": [
            {
                "timestamp": "2024-08-30T10:00:00Z",
                "tasks_completed": 5,
                "tokens_processed": 12500,
                "avg_response_time_ms": 1250.5,
                "cpu_usage_percent": 65.2,
                "memory_usage_mb": 512.8
            }
        ],
        "timeframe_hours": hours
    }


@router.get("/statistics/overview")
async def get_agent_statistics(db: Session = Depends(get_db)):
    """Get overall agent statistics"""
    return {
        "total_agents": 3,
        "status_counts": {
            "idle": 1,
            "working": 2,
            "paused": 0,
            "error": 0,
            "offline": 0
        },
        "total_capacity": 6,
        "current_load": 3,
        "utilization_percent": 50.0,
        "avg_response_time_ms": 1199.1
    }