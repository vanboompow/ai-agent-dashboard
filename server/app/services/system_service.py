"""System service for handling system-wide operations."""
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session
from app.models.agent import Agent, AgentStatus
from app.models.task import Task, SystemMetric


class SystemService:
    """Service class for system operations."""
    
    def __init__(self, db_session: Session, redis_client=None, celery_app=None):
        self.db_session = db_session
        self.redis_client = redis_client
        self.celery_app = celery_app
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system metrics."""
        active_agents = self.db_session.query(Agent).filter(
            Agent.current_status != AgentStatus.paused
        ).count()
        
        queued_tasks = self.db_session.query(Task).filter(
            Task.completed_at.is_(None)
        ).count()
        
        return {
            "active_agents_count": active_agents,
            "tasks_queued": queued_tasks,
            "tokens_per_second": 0,  # Would be calculated from recent metrics
            "cost_per_second_usd": 0.0,  # Would be calculated from recent metrics
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status."""
        return {
            "status": "running",
            "uptime": 3600,  # Would calculate actual uptime
            "version": "1.0.0",
            "agents_connected": self.db_session.query(Agent).count(),
            "tasks_queued": self.db_session.query(Task).filter(
                Task.completed_at.is_(None)
            ).count()
        }
    
    async def start_system(self) -> bool:
        """Start the system."""
        if self.redis_client:
            await self.redis_client.publish("system_control", {
                "command": "start_system",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        return True
    
    async def pause_all_agents(self) -> bool:
        """Pause all agents."""
        agents = self.db_session.query(Agent).filter(
            Agent.current_status != AgentStatus.paused
        ).all()
        
        for agent in agents:
            agent.current_status = AgentStatus.paused
        
        self.db_session.commit()
        
        if self.redis_client:
            await self.redis_client.publish("system_control", {
                "command": "pause_all_agents",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return True
    
    async def stop_new_tasks(self) -> bool:
        """Stop accepting new tasks."""
        if self.redis_client:
            await self.redis_client.publish("system_control", {
                "command": "stop_new_tasks",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        return True
    
    async def set_throttle_rate(self, rate: float) -> bool:
        """Set system throttle rate."""
        if self.redis_client:
            await self.redis_client.publish("system_control", {
                "command": "set_throttle_rate",
                "rate": rate,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        return True
    
    async def emergency_stop(self) -> bool:
        """Emergency stop of all operations."""
        # Purge all queued tasks
        if self.celery_app:
            self.celery_app.control.purge()
        
        # Pause all agents
        await self.pause_all_agents()
        
        if self.redis_client:
            await self.redis_client.publish("system_control", {
                "command": "emergency_stop",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        
        return True