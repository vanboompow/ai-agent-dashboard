"""Enhanced task service for comprehensive task lifecycle management."""
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import and_, or_, desc
from app.models import Task, TaskStatus, TaskPriority, TaskType, TaskLog, Agent, TaskTemplate
from app.services.agent_service import AgentService
from app.services.redis_pubsub import RedisPublisher
import logging
import json
import uuid

logger = logging.getLogger(__name__)


class EnhancedTaskService:
    """Enhanced service class for comprehensive task operations."""
    
    def __init__(self, db_session: Session, redis_publisher: Optional[RedisPublisher] = None):
        self.db = db_session
        self.redis_publisher = redis_publisher
        self.agent_service = AgentService(db_session)
    
    # Core CRUD Operations
    
    async def create_task(
        self,
        title: str,
        description: str,
        task_type: TaskType,
        priority: TaskPriority = TaskPriority.normal,
        sector: Optional[str] = None,
        input_data: Optional[Dict[str, Any]] = None,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[List[str]] = None,
        deadline: Optional[datetime] = None,
        scheduled_at: Optional[datetime] = None,
        parent_task_id: Optional[UUID] = None,
        dependencies: Optional[List[UUID]] = None,
        max_retries: int = 3,
        timeout_seconds: Optional[int] = None,
        created_by: Optional[str] = None
    ) -> Task:
        """Create a new comprehensive task"""
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            sector=sector,
            input_data=input_data,
            config=config,
            metadata=metadata,
            tags=tags,
            deadline=deadline,
            scheduled_at=scheduled_at,
            parent_task_id=parent_task_id,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
            created_by=created_by
        )
        
        self.db.add(task)
        self.db.flush()  # Get the task_id
        
        # Add dependencies if specified
        if dependencies:
            dep_tasks = self.db.query(Task).filter(Task.task_id.in_(dependencies)).all()
            task.dependencies.extend(dep_tasks)
        
        self.db.commit()
        self.db.refresh(task)
        
        # Log task creation
        await self.add_task_log(
            task.task_id,
            "INFO",
            f"Task '{title}' created with priority {priority.value}",
            {"task_type": task_type.value, "created_by": created_by}
        )
        
        # Publish to Redis
        if self.redis_publisher:
            await self.redis_publisher.publish_task_update(
                str(task.task_id),
                task.status.value,
                task.progress_percent,
                str(task.assigned_agent_id) if task.assigned_agent_id else None
            )
        
        logger.info(f"Created task {task.task_id}: {title}")
        return task
    
    async def get_task(self, task_id: UUID) -> Optional[Task]:
        """Get task by ID"""
        return self.db.query(Task).filter(Task.task_id == task_id).first()
    
    async def complete_task(
        self,
        task_id: UUID,
        output_data: Optional[Dict[str, Any]] = None,
        actual_cost_usd: Optional[float] = None,
        tokens_used: Optional[int] = None
    ) -> Optional[Task]:
        """Complete task successfully"""
        task = await self.get_task(task_id)
        if not task:
            return None
        
        task.status = TaskStatus.completed
        task.completed_at = func.now()
        task.output_data = output_data
        task.progress_percent = 100
        
        if actual_cost_usd:
            task.actual_cost_usd = actual_cost_usd
        if tokens_used:
            task.token_usage = tokens_used
        
        # Calculate processing time
        if task.started_at:
            processing_time = (datetime.utcnow() - task.started_at).total_seconds()
            task.processing_time_seconds = processing_time
            
            if tokens_used and processing_time > 0:
                task.tokens_per_second = tokens_used / processing_time
        
        task.updated_at = func.now()
        
        # Update agent metrics
        if task.assigned_agent_id:
            await self.agent_service.complete_task_for_agent(
                task.assigned_agent_id,
                processing_time_seconds=float(task.processing_time_seconds or 0),
                tokens_processed=tokens_used
            )
        
        self.db.commit()
        self.db.refresh(task)
        
        await self.add_task_log(
            task_id,
            "INFO",
            "Task completed successfully",
            {
                "processing_time_seconds": float(task.processing_time_seconds or 0),
                "tokens_used": tokens_used,
                "cost_usd": actual_cost_usd
            }
        )
        
        # Publish update
        if self.redis_publisher:
            await self.redis_publisher.publish_task_update(
                str(task_id),
                task.status.value,
                task.progress_percent,
                str(task.assigned_agent_id) if task.assigned_agent_id else None
            )
        
        logger.info(f"Completed task {task_id}")
        return task
    
    async def add_task_log(
        self,
        task_id: UUID,
        level: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskLog:
        """Add log entry for a task"""
        log_entry = TaskLog(
            task_id=task_id,
            log_level=level,
            message=message,
            context=context
        )
        
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        
        return log_entry