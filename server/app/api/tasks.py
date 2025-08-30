from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

router = APIRouter()


class TaskCreate(BaseModel):
    description: str
    priority: str = "normal"
    sector: str
    assigned_agent_id: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    description: str
    status: str
    priority: str
    sector: str
    agent_id: Optional[str]
    created_at: datetime
    tps: Optional[int]
    time_elapsed: Optional[str]


@router.get("/", response_model=List[TaskResponse])
async def get_tasks(status: Optional[str] = None, limit: int = 50):
    """Get task queue with optional filtering"""
    # Mock data matching the task queue view
    tasks = [
        {
            "task_id": str(uuid.uuid4()),
            "description": "OUTLINE TAB PROJECT SPEC",
            "status": "working",
            "priority": "high",
            "sector": "PRODUCT",
            "agent_id": "E-3",
            "created_at": datetime.now(),
            "tps": 1195,
            "time_elapsed": "00:20"
        },
        {
            "task_id": str(uuid.uuid4()),
            "description": "WRITE UP THE PROJECT SPEC",
            "status": "pending",
            "priority": "normal",
            "sector": "PRODUCT",
            "agent_id": "S-2",
            "created_at": datetime.now(),
            "tps": None,
            "time_elapsed": None
        },
        {
            "task_id": str(uuid.uuid4()),
            "description": "EXECUTE SPEC AND MP ALIGN",
            "status": "working",
            "priority": "high",
            "sector": "PRODUCT",
            "agent_id": "P-4",
            "created_at": datetime.now(),
            "tps": 847,
            "time_elapsed": "00:15"
        }
    ]
    
    if status:
        tasks = [t for t in tasks if t["status"] == status]
    
    return tasks[:limit]


@router.post("/", response_model=TaskResponse)
async def create_task(task: TaskCreate):
    """Create a new task and enqueue it"""
    new_task = {
        "task_id": str(uuid.uuid4()),
        "description": task.description,
        "status": "pending",
        "priority": task.priority,
        "sector": task.sector,
        "agent_id": task.assigned_agent_id,
        "created_at": datetime.now(),
        "tps": None,
        "time_elapsed": None
    }
    # Here you would enqueue to Celery
    return new_task


@router.delete("/{task_id}")
async def cancel_task(task_id: str):
    """Cancel a specific task"""
    return {"message": f"Task {task_id} cancelled", "status": "cancelled"}


@router.post("/{task_id}/reassign")
async def reassign_task(task_id: str, agent_id: str):
    """Reassign task to different agent"""
    return {
        "message": f"Task {task_id} reassigned to {agent_id}",
        "task_id": task_id,
        "agent_id": agent_id
    }