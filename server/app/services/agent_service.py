from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import and_, or_
from app.models.agent import Agent, AgentStatus
import logging
import asyncio

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(self, db_session: Session, redis_client=None):
        self.db_session = db_session
        self.redis_client = redis_client
    
    # CRUD Operations
    
    async def create_agent(self, agent_data: Dict[str, Any]) -> Agent:
        """Create a new agent"""
        agent = Agent(
            agent_type=agent_data.get("agent_type"),
            hostname=agent_data.get("hostname"),
            current_status=agent_data.get("current_status", AgentStatus.idle),
            created_at=datetime.now()
        )
        
        self.db_session.add(agent)
        self.db_session.commit()
        self.db_session.refresh(agent)
        
        # Publish to Redis
        if self.redis_client:
            await self.redis_client.publish("agent_updates", {
                "event": "agent_created",
                "agent_id": str(agent.agent_id)
            })
        
        logger.info(f"Created agent {agent.agent_id} on {agent.hostname}")
        return agent
    
    async def get_agent(self, agent_id: UUID) -> Optional[Agent]:
        """Get agent by ID"""
        return self.db.query(Agent).filter(Agent.agent_id == agent_id).first()
    
    async def get_agent_by_name(self, agent_name: str) -> Optional[Agent]:
        """Get agent by name"""
        return self.db.query(Agent).filter(Agent.agent_name == agent_name).first()
    
    async def get_all_agents(
        self,
        status: Optional[AgentStatus] = None,
        agent_type: Optional[str] = None,
        hostname: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Agent]:
        """Get all agents with optional filtering"""
        query = self.db.query(Agent)
        
        if status:
            query = query.filter(Agent.current_status == status)
        if agent_type:
            query = query.filter(Agent.agent_type == agent_type)
        if hostname:
            query = query.filter(Agent.hostname == hostname)
        
        return query.offset(offset).limit(limit).all()
    
    async def update_agent(
        self,
        agent_id: UUID,
        **kwargs
    ) -> Optional[Agent]:
        """Update agent fields"""
        agent = await self.get_agent(agent_id)
        if not agent:
            return None
        
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        self.db.commit()
        self.db.refresh(agent)
        
        logger.info(f"Updated agent {agent_id}: {kwargs}")
        return agent
    
    async def delete_agent(self, agent_id: UUID) -> bool:
        """Delete agent"""
        agent = await self.get_agent(agent_id)
        if not agent:
            return False
        
        self.db.delete(agent)
        self.db.commit()
        
        logger.info(f"Deleted agent {agent_id}")
        return True
    
    # Status Management
    
    async def update_agent_status(
        self,
        agent_id: UUID,
        status: AgentStatus,
        error_message: Optional[str] = None
    ) -> Optional[Agent]:
        """Update agent status"""
        agent = await self.get_agent(agent_id)
        if not agent:
            return None
        
        old_status = agent.current_status
        agent.current_status = status
        agent.last_activity = func.now()
        
        if status == AgentStatus.error and error_message:
            agent.last_error = error_message
            agent.error_count += 1
        elif status != AgentStatus.error:
            agent.last_error = None
        
        self.db.commit()
        self.db.refresh(agent)
        
        logger.info(f"Agent {agent_id} status changed from {old_status.value} to {status.value}")
        return agent
    
    async def heartbeat(
        self,
        agent_id: UUID,
        cpu_usage: Optional[float] = None,
        memory_usage: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[Agent]:
        """Update agent heartbeat with optional resource metrics"""
        agent = await self.get_agent(agent_id)
        if not agent:
            return None
        
        agent.last_heartbeat = func.now()
        
        if cpu_usage is not None:
            agent.cpu_usage_percent = cpu_usage
        if memory_usage is not None:
            agent.memory_usage_mb = memory_usage
        
        if metadata:
            agent.metadata = {**(agent.metadata or {}), **metadata}
        
        self.db.commit()
        
        return agent
    
    # Availability and Load Balancing
    
    async def get_available_agents(
        self,
        agent_type: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None
    ) -> List[Agent]:
        """Get agents available for new tasks"""
        query = self.db.query(Agent).filter(
            Agent.current_status.in_([AgentStatus.idle, AgentStatus.working]),
            Agent.current_task_count < Agent.max_concurrent_tasks
        )
        
        if agent_type:
            query = query.filter(Agent.agent_type == agent_type)
        
        agents = query.all()
        
        # Filter by capabilities if specified
        if required_capabilities:
            available_agents = []
            for agent in agents:
                agent_caps = set(agent.capabilities or [])
                if set(required_capabilities).issubset(agent_caps):
                    available_agents.append(agent)
            return available_agents
        
        return agents
    
    async def get_best_agent_for_task(
        self,
        task_type: str,
        required_capabilities: Optional[List[str]] = None,
        preferred_agent_type: Optional[str] = None
    ) -> Optional[Agent]:
        """Find the best available agent for a task using load balancing"""
        available_agents = await self.get_available_agents(
            agent_type=preferred_agent_type,
            required_capabilities=required_capabilities
        )
        
        if not available_agents:
            return None
        
        # Sort by load (current tasks) and performance
        def agent_score(agent: Agent) -> float:
            load_factor = agent.current_task_count / max(agent.max_concurrent_tasks, 1)
            performance_factor = agent.average_response_time_ms or 1000  # Default to 1s
            return load_factor + (performance_factor / 10000)  # Normalize response time
        
        best_agent = min(available_agents, key=agent_score)
        return best_agent
    
    async def assign_task_to_agent(self, agent_id: UUID) -> Optional[Agent]:
        """Increment agent's current task count"""
        agent = await self.get_agent(agent_id)
        if not agent:
            return None
        
        agent.current_task_count += 1
        agent.last_activity = func.now()
        
        if agent.current_status == AgentStatus.idle:
            agent.current_status = AgentStatus.working
        
        self.db.commit()
        self.db.refresh(agent)
        
        return agent
    
    async def complete_task_for_agent(
        self,
        agent_id: UUID,
        processing_time_seconds: Optional[float] = None,
        tokens_processed: Optional[int] = None
    ) -> Optional[Agent]:
        """Decrement agent's current task count and update metrics"""
        agent = await self.get_agent(agent_id)
        if not agent:
            return None
        
        agent.current_task_count = max(0, agent.current_task_count - 1)
        agent.total_tasks_completed += 1
        agent.last_activity = func.now()
        
        if processing_time_seconds:
            agent.total_processing_time_seconds += processing_time_seconds
            # Update running average response time
            if agent.total_tasks_completed > 0:
                avg_time_ms = (agent.total_processing_time_seconds / agent.total_tasks_completed) * 1000
                agent.average_response_time_ms = avg_time_ms
        
        if tokens_processed:
            agent.total_tokens_processed += tokens_processed
        
        # Update status if no more tasks
        if agent.current_task_count == 0:
            agent.current_status = AgentStatus.idle
        
        self.db.commit()
        self.db.refresh(agent)
        
        return agent
    
    # Health and Monitoring
    
    async def get_offline_agents(
        self,
        offline_threshold_minutes: int = 5
    ) -> List[Agent]:
        """Get agents that haven't sent a heartbeat recently"""
        threshold = datetime.utcnow() - timedelta(minutes=offline_threshold_minutes)
        
        return self.db.query(Agent).filter(
            or_(
                Agent.last_heartbeat < threshold,
                Agent.last_heartbeat.is_(None)
            ),
            Agent.current_status != AgentStatus.offline
        ).all()
    
    async def mark_agents_offline(
        self,
        offline_threshold_minutes: int = 5
    ) -> List[Agent]:
        """Mark agents as offline if they haven't sent heartbeats"""
        offline_agents = await self.get_offline_agents(offline_threshold_minutes)
        
        for agent in offline_agents:
            agent.current_status = AgentStatus.offline
            logger.warning(f"Marking agent {agent.agent_id} as offline - last heartbeat: {agent.last_heartbeat}")
        
        if offline_agents:
            self.db.commit()
        
        return offline_agents
    
    async def get_agent_statistics(self) -> Dict[str, Any]:
        """Get overall agent statistics"""
        stats = self.db.query(
            Agent.current_status,
            func.count(Agent.agent_id).label('count')
        ).group_by(Agent.current_status).all()
        
        status_counts = {status.value: 0 for status in AgentStatus}
        for status, count in stats:
            status_counts[status.value] = count
        
        total_agents = sum(status_counts.values())
        
        # Calculate additional metrics
        active_agents = self.db.query(Agent).filter(
            Agent.current_status.in_([AgentStatus.idle, AgentStatus.working])
        ).all()
        
        total_capacity = sum(agent.max_concurrent_tasks for agent in active_agents)
        current_load = sum(agent.current_task_count for agent in active_agents)
        
        return {
            "total_agents": total_agents,
            "status_counts": status_counts,
            "total_capacity": total_capacity,
            "current_load": current_load,
            "utilization_percent": (current_load / max(total_capacity, 1)) * 100,
            "avg_response_time_ms": self.db.query(func.avg(Agent.average_response_time_ms)).scalar() or 0
        }
    
    # Metrics
    
    async def record_agent_metric(
        self,
        agent_id: UUID,
        tasks_completed_count: int = 0,
        tokens_processed_count: int = 0,
        response_time_ms: Optional[float] = None,
        cpu_usage_percent: Optional[float] = None,
        memory_usage_mb: Optional[float] = None,
        estimated_cost_usd: Optional[float] = None,
        custom_metrics: Optional[Dict[str, Any]] = None
    ) -> AgentMetric:
        """Record a metric data point for an agent"""
        metric = AgentMetric(
            agent_id=agent_id,
            tasks_completed_count=tasks_completed_count,
            tokens_processed_count=tokens_processed_count,
            response_time_ms=response_time_ms,
            throughput_tps=tokens_processed_count / max(response_time_ms / 1000, 0.001) if response_time_ms else None,
            cpu_usage_percent=cpu_usage_percent,
            memory_usage_mb=memory_usage_mb,
            estimated_cost_usd=estimated_cost_usd,
            custom_metrics=custom_metrics
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    async def get_agent_metrics(
        self,
        agent_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[AgentMetric]:
        """Get agent metrics for a time range"""
        query = self.db.query(AgentMetric).filter(AgentMetric.agent_id == agent_id)
        
        if start_time:
            query = query.filter(AgentMetric.timestamp >= start_time)
        if end_time:
            query = query.filter(AgentMetric.timestamp <= end_time)
        
        return query.order_by(AgentMetric.timestamp.desc()).limit(limit).all()