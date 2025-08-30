"""Task service for handling task-related operations."""
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import uuid

from sqlalchemy.orm import Session
from app.models.task import Task, TaskLog
from app.models.agent import Agent


class TaskService:
    """Service class for task operations."""
    
    def __init__(self, db_session: Session, redis_client=None):
        self.db_session = db_session
        self.redis_client = redis_client
    
    async def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        return self.db_session.query(Task).all()
    
    async def get_tasks(self, limit: int = 100, offset: int = 0) -> List[Task]:
        """Get tasks with pagination."""
        return self.db_session.query(Task).offset(offset).limit(limit).all()
    
    async def get_task_by_id(self, task_id: uuid.UUID) -> Optional[Task]:
        """Get task by ID."""
        return self.db_session.query(Task).filter(Task.task_id == task_id).first()
    
    async def create_task(self, task_data: Dict[str, Any]) -> Task:
        """Create a new task."""
        task = Task(**task_data)
        self.db_session.add(task)
        self.db_session.commit()
        self.db_session.refresh(task)
        
        # Publish to Redis
        if self.redis_client:
            await self.redis_client.publish("task_updates", {
                "event": "task_created",
                "task_id": str(task.task_id)
            })
        
        return task
    
    async def update_task_status(self, task_id: uuid.UUID, status: str) -> bool:
        """Update task status."""
        task = await self.get_task_by_id(task_id)
        if task:
            # In a real implementation, this would update status_id based on status name
            self.db_session.commit()
            
            # Publish update
            if self.redis_client:
                await self.redis_client.publish("task_updates", {
                    "event": "task_status_updated",
                    "task_id": str(task_id),
                    "status": status
                })
            
            return True
        return False
    
    async def assign_task(self, task_id: uuid.UUID, agent_id: uuid.UUID) -> bool:
        """Assign task to an agent."""
        task = await self.get_task_by_id(task_id)
        if task:
            task.assigned_agent_id = agent_id
            self.db_session.commit()
            
            # Publish update
            if self.redis_client:
                await self.redis_client.publish("task_updates", {
                    "event": "task_assigned",
                    "task_id": str(task_id),
                    "agent_id": str(agent_id)
                })
            
            return True
        return False
    
    async def get_tasks_by_agent(self, agent_id: uuid.UUID) -> List[Task]:
        """Get tasks assigned to a specific agent."""
        return self.db_session.query(Task).filter(Task.assigned_agent_id == agent_id).all()
    
    async def delete_task(self, task_id: uuid.UUID) -> bool:
        """Delete a task."""
        task = await self.get_task_by_id(task_id)
        if task:
            self.db_session.delete(task)
            self.db_session.commit()
            
            # Publish update
            if self.redis_client:
                await self.redis_client.publish("task_updates", {
                    "event": "task_deleted",
                    "task_id": str(task_id)
                })
            
            return True
        return False
    
    async def add_task_log(self, task_id: uuid.UUID, log_data: Dict[str, Any]) -> TaskLog:
        """Add a log entry for a task."""
        log_entry = TaskLog(
            task_id=task_id,
            timestamp=log_data.get("timestamp", datetime.now(timezone.utc)),
            message=log_data["message"],
            log_level=log_data.get("log_level", "INFO")
        )
        self.db_session.add(log_entry)
        self.db_session.commit()
        self.db_session.refresh(log_entry)
        return log_entry
    
    async def get_task_logs(self, task_id: uuid.UUID) -> List[TaskLog]:
        """Get all logs for a task."""
        return self.db_session.query(TaskLog).filter(TaskLog.task_id == task_id).all()