from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
import uuid

router = APIRouter()


@router.get("/")
async def get_agents():
    """Get all registered agents with their current status"""
    # Mock data matching the radar view
    agents = [
        {
            "agentId": "E-3",
            "status": "working",
            "taskCategory": "engineering",
            "currentTask": "Verify Alignment & Vision",
            "elapsedTime": 125,
            "angle": 45,
            "distance": 0.6
        },
        {
            "agentId": "S-2",
            "status": "idle",
            "taskCategory": "design",
            "currentTask": None,
            "elapsedTime": 0,
            "angle": 135,
            "distance": 0.4
        },
        {
            "agentId": "P-4",
            "status": "working",
            "taskCategory": "product",
            "currentTask": "Execute Spec and MP Align",
            "elapsedTime": 89,
            "angle": 225,
            "distance": 0.5
        }
    ]
    return agents


@router.get("/{agent_id}")
async def get_agent(agent_id: str):
    """Get specific agent details"""
    return {
        "agentId": agent_id,
        "status": "working",
        "hostname": f"worker-{agent_id.lower()}",
        "taskCategory": "engineering",
        "currentTask": "Processing task",
        "tasksCompleted": 47,
        "tokensProcessed": 234567,
        "uptime": "4h 23m"
    }


@router.post("/{agent_id}/pause")
async def pause_agent(agent_id: str):
    """Pause a specific agent"""
    return {"message": f"Agent {agent_id} paused", "status": "paused"}


@router.post("/{agent_id}/resume")
async def resume_agent(agent_id: str):
    """Resume a specific agent"""
    return {"message": f"Agent {agent_id} resumed", "status": "working"}