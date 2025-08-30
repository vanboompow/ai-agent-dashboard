from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from uuid import UUID
from pydantic import BaseModel

from app.services.task_service_enhanced import EnhancedTaskService
from app.models import TaskStatus, TaskPriority, TaskType
from app.database import get_db

router = APIRouter()


class TaskCreate(BaseModel):
    title: str
    description: str
    task_type: str  # Will be converted to TaskType enum
    priority: str = "normal"  # Will be converted to TaskPriority enum
    sector: Optional[str] = None
    input_data: Optional[Dict[str, Any]] = None
    config: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None
    deadline: Optional[datetime] = None
    assigned_agent_id: Optional[str] = None
    max_retries: int = 3
    timeout_seconds: Optional[int] = None
    created_by: Optional[str] = None


class TaskResponse(BaseModel):
    task_id: str
    title: str
    description: Optional[str]
    status: str
    priority: str
    task_type: str
    sector: Optional[str]
    agent_id: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    progress_percent: int
    tps: Optional[float]  # Tokens per second
    time_elapsed: Optional[str]
    token_usage: Optional[int]
    estimated_cost_usd: Optional[float]
    actual_cost_usd: Optional[float]
    error_message: Optional[str]


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    deadline: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


def convert_task_to_response(task) -> TaskResponse:
    """Convert database task model to API response"""
    # Calculate time elapsed
    time_elapsed = None
    if task.started_at:
        if task.completed_at:
            delta = task.completed_at - task.started_at
        else:
            delta = datetime.utcnow() - task.started_at
        
        total_seconds = int(delta.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        time_elapsed = f"{minutes:02d}:{seconds:02d}"
    
    return TaskResponse(
        task_id=str(task.task_id),
        title=task.title,
        description=task.description,
        status=task.status.value,
        priority=task.priority.value,
        task_type=task.task_type.value,
        sector=task.sector,
        agent_id=str(task.assigned_agent_id) if task.assigned_agent_id else None,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        progress_percent=task.progress_percent or 0,
        tps=float(task.tokens_per_second) if task.tokens_per_second else None,
        time_elapsed=time_elapsed,
        token_usage=task.token_usage,
        estimated_cost_usd=float(task.estimated_cost_usd) if task.estimated_cost_usd else None,
        actual_cost_usd=float(task.actual_cost_usd) if task.actual_cost_usd else None,
        error_message=task.error_message
    )


@router.get("/", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[str] = None,
    priority: Optional[str] = None,
    task_type: Optional[str] = None,
    sector: Optional[str] = None,
    assigned_agent_id: Optional[str] = None,
    created_by: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get tasks with optional filtering"""
    # For now, return enhanced mock data
    import uuid as uuid_lib
    
    mock_tasks = [
        {
            "task_id": str(uuid_lib.uuid4()),
            "title": "OUTLINE TAB PROJECT SPEC",
            "description": "Create comprehensive project specification with technical requirements",
            "status": "running",
            "priority": "high",
            "task_type": "text_processing",
            "sector": "PRODUCT",
            "agent_id": "E-3",
            "created_at": datetime.now() - timedelta(minutes=25),
            "started_at": datetime.now() - timedelta(minutes=20),
            "completed_at": None,
            "progress_percent": 65,
            "tps": 1195.5,
            "time_elapsed": "00:20",
            "token_usage": 14340,
            "estimated_cost_usd": 0.0287,
            "actual_cost_usd": None,
            "error_message": None
        },
        {
            "task_id": str(uuid_lib.uuid4()),
            "title": "WRITE UP THE PROJECT SPEC",
            "description": "Document the final project specification based on outline",
            "status": "pending",
            "priority": "normal",
            "task_type": "text_processing",
            "sector": "PRODUCT",
            "agent_id": None,
            "created_at": datetime.now() - timedelta(minutes=10),
            "started_at": None,
            "completed_at": None,
            "progress_percent": 0,
            "tps": None,
            "time_elapsed": None,
            "token_usage": 0,
            "estimated_cost_usd": 0.025,
            "actual_cost_usd": None,
            "error_message": None
        },
        {
            "task_id": str(uuid_lib.uuid4()),
            "title": "EXECUTE SPEC AND MP ALIGN",
            "description": "Execute the specification and align with master plan",
            "status": "running",
            "priority": "high",
            "task_type": "code_generation",
            "sector": "PRODUCT",
            "agent_id": "P-4",
            "created_at": datetime.now() - timedelta(minutes=20),
            "started_at": datetime.now() - timedelta(minutes=15),
            "completed_at": None,
            "progress_percent": 45,
            "tps": 847.2,
            "time_elapsed": "00:15",
            "token_usage": 7611,
            "estimated_cost_usd": 0.038,
            "actual_cost_usd": None,
            "error_message": None
        },
        {
            "task_id": str(uuid_lib.uuid4()),
            "title": "DATA ANALYSIS PIPELINE",
            "description": "Analyze user behavior data and generate insights",
            "status": "completed",
            "priority": "normal",
            "task_type": "data_analysis",
            "sector": "ANALYTICS",
            "agent_id": "D-1",
            "created_at": datetime.now() - timedelta(hours=2),
            "started_at": datetime.now() - timedelta(minutes=90),
            "completed_at": datetime.now() - timedelta(minutes=30),
            "progress_percent": 100,
            "tps": 1250.8,
            "time_elapsed": "01:00",
            "token_usage": 75048,
            "estimated_cost_usd": 0.15,
            "actual_cost_usd": 0.147,
            "error_message": None
        }
    ]
    
    # Apply filters
    filtered_tasks = mock_tasks
    if status:
        filtered_tasks = [t for t in filtered_tasks if t["status"] == status]
    if priority:
        filtered_tasks = [t for t in filtered_tasks if t["priority"] == priority]
    if sector:
        filtered_tasks = [t for t in filtered_tasks if t["sector"] == sector]
    
    # Apply pagination
    paginated_tasks = filtered_tasks[offset:offset + limit]
    
    return [TaskResponse(**task) for task in paginated_tasks]


@router.post("/", response_model=TaskResponse)
async def create_task(
    task: TaskCreate,
    db: Session = Depends(get_db)
):
    """Create a new task and enqueue it"""
    # For now, return mock response
    import uuid as uuid_lib
    
    # Convert string enums
    try:
        task_type_enum = TaskType(task.task_type)
        priority_enum = TaskPriority(task.priority)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid enum value: {e}")
    
    # Create mock response
    new_task = TaskResponse(
        task_id=str(uuid_lib.uuid4()),
        title=task.title,
        description=task.description,
        status="pending",
        priority=task.priority,
        task_type=task.task_type,
        sector=task.sector,
        agent_id=task.assigned_agent_id,
        created_at=datetime.now(),
        started_at=None,
        completed_at=None,
        progress_percent=0,
        tps=None,
        time_elapsed=None,
        token_usage=0,
        estimated_cost_usd=0.025,
        actual_cost_usd=None,
        error_message=None
    )
    
    return new_task


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Get specific task details"""
    try:
        UUID(task_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    # Mock response for now
    return TaskResponse(
        task_id=task_id,
        title="Sample Task",
        description="This is a sample task",
        status="running",
        priority="normal",
        task_type="text_processing",
        sector="GENERAL",
        agent_id="A-1",
        created_at=datetime.now() - timedelta(minutes=15),
        started_at=datetime.now() - timedelta(minutes=10),
        completed_at=None,
        progress_percent=35,
        tps=950.3,
        time_elapsed="00:10",
        token_usage=9503,
        estimated_cost_usd=0.019,
        actual_cost_usd=None,
        error_message=None
    )


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_update: TaskUpdate,
    db: Session = Depends(get_db)
):
    """Update task details"""
    try:
        UUID(task_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    # Mock response showing updated task
    return TaskResponse(
        task_id=task_id,
        title=task_update.title or "Updated Task",
        description=task_update.description or "This task has been updated",
        status="pending",
        priority=task_update.priority or "normal",
        task_type="text_processing",
        sector="GENERAL",
        agent_id=None,
        created_at=datetime.now() - timedelta(minutes=15),
        started_at=None,
        completed_at=None,
        progress_percent=0,
        tps=None,
        time_elapsed=None,
        token_usage=0,
        estimated_cost_usd=0.025,
        actual_cost_usd=None,
        error_message=None
    )


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Cancel/delete a specific task"""
    try:
        UUID(task_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    return {
        "message": f"Task {task_id} cancelled",
        "reason": reason or "No reason provided",
        "status": "cancelled",
        "cancelled_at": datetime.now()
    }


@router.post("/{task_id}/assign")
async def assign_task(
    task_id: str,
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Assign task to a specific agent"""
    try:
        UUID(task_id)  # Validate task UUID format
        UUID(agent_id)  # Validate agent UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ID format")
    
    return {
        "message": f"Task {task_id} assigned to agent {agent_id}",
        "task_id": task_id,
        "agent_id": agent_id,
        "assigned_at": datetime.now(),
        "status": "assigned"
    }


@router.post("/{task_id}/start")
async def start_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """Start task execution"""
    try:
        UUID(task_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    return {
        "message": f"Task {task_id} started",
        "task_id": task_id,
        "status": "running",
        "started_at": datetime.now()
    }


@router.post("/{task_id}/complete")
async def complete_task(
    task_id: str,
    output_data: Optional[Dict[str, Any]] = None,
    tokens_used: Optional[int] = None,
    actual_cost_usd: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Mark task as completed"""
    try:
        UUID(task_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    return {
        "message": f"Task {task_id} completed",
        "task_id": task_id,
        "status": "completed",
        "completed_at": datetime.now(),
        "tokens_used": tokens_used,
        "actual_cost_usd": actual_cost_usd,
        "output_data": output_data
    }


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    level: Optional[str] = None,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get task logs"""
    try:
        UUID(task_id)  # Validate UUID format
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid task ID format")
    
    # Mock logs
    mock_logs = [
        {
            "timestamp": datetime.now() - timedelta(minutes=10),
            "level": "INFO",
            "message": "Task started",
            "context": {"agent_id": "A-1"}
        },
        {
            "timestamp": datetime.now() - timedelta(minutes=5),
            "level": "INFO",
            "message": "Processing input data",
            "context": {"progress": "50%"}
        },
        {
            "timestamp": datetime.now() - timedelta(minutes=2),
            "level": "WARNING",
            "message": "High memory usage detected",
            "context": {"memory_mb": 1024}
        }
    ]
    
    if level:
        mock_logs = [log for log in mock_logs if log["level"] == level.upper()]
    
    return {
        "task_id": task_id,
        "logs": mock_logs[:limit]
    }


@router.get("/statistics/overview")
async def get_task_statistics(db: Session = Depends(get_db)):
    """Get task queue statistics"""
    return {
        "status_counts": {
            "pending": 15,
            "assigned": 3,
            "running": 8,
            "paused": 1,
            "completed": 234,
            "failed": 12,
            "cancelled": 5
        },
        "priority_counts": {
            "critical": 2,
            "high": 8,
            "normal": 45,
            "low": 12
        },
        "total_tasks": 278,
        "avg_wait_time_seconds": 145.7,
        "throughput_last_hour": 23,
        "avg_processing_time_seconds": 287.3,
        "success_rate_percent": 91.2,
        "cost_per_hour_usd": 4.73
    }