from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import and_, or_, desc, asc
from app.models import (
    SystemMetric, AgentPerformanceMetric, TaskPerformanceMetric, 
    CostMetric, AlertMetric, MetricAggregation, MetricType,
    Agent, Task, TaskStatus
)
import logging

logger = logging.getLogger(__name__)


class MetricService:
    def __init__(self, db: Session):
        self.db = db
    
    # System Metrics
    
    async def record_system_metrics(
        self,
        active_agents_count: int = 0,
        idle_agents_count: int = 0,
        working_agents_count: int = 0,
        offline_agents_count: int = 0,
        error_agents_count: int = 0,
        pending_tasks_count: int = 0,
        running_tasks_count: int = 0,
        completed_tasks_count: int = 0,
        failed_tasks_count: int = 0,
        avg_response_time_ms: Optional[float] = None,
        tokens_per_second: Optional[float] = None,
        tasks_per_minute: Optional[float] = None,
        avg_cpu_usage_percent: Optional[float] = None,
        avg_memory_usage_mb: Optional[float] = None,
        total_cost_usd: Optional[float] = None,
        cost_per_token: Optional[float] = None,
        hourly_burn_rate_usd: Optional[float] = None,
        error_rate_percent: Optional[float] = None,
        timeout_rate_percent: Optional[float] = None,
        custom_metrics: Optional[Dict[str, Any]] = None
    ) -> SystemMetric:
        """Record system-wide metrics"""
        metric = SystemMetric(
            active_agents_count=active_agents_count,
            idle_agents_count=idle_agents_count,
            working_agents_count=working_agents_count,
            offline_agents_count=offline_agents_count,
            error_agents_count=error_agents_count,
            pending_tasks_count=pending_tasks_count,
            running_tasks_count=running_tasks_count,
            completed_tasks_count=completed_tasks_count,
            failed_tasks_count=failed_tasks_count,
            avg_response_time_ms=avg_response_time_ms,
            tokens_per_second=tokens_per_second,
            tasks_per_minute=tasks_per_minute,
            avg_cpu_usage_percent=avg_cpu_usage_percent,
            avg_memory_usage_mb=avg_memory_usage_mb,
            total_cost_usd=total_cost_usd,
            cost_per_token=cost_per_token,
            hourly_burn_rate_usd=hourly_burn_rate_usd,
            error_rate_percent=error_rate_percent,
            timeout_rate_percent=timeout_rate_percent,
            custom_metrics=custom_metrics
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    async def get_system_metrics(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[SystemMetric]:
        """Get system metrics for a time range"""
        query = self.db.query(SystemMetric)
        
        if start_time:
            query = query.filter(SystemMetric.timestamp >= start_time)
        if end_time:
            query = query.filter(SystemMetric.timestamp <= end_time)
        
        return query.order_by(desc(SystemMetric.timestamp)).limit(limit).all()
    
    async def get_latest_system_metrics(self) -> Optional[SystemMetric]:
        """Get the most recent system metrics"""
        return self.db.query(SystemMetric).order_by(desc(SystemMetric.timestamp)).first()
    
    async def compute_current_system_metrics(self) -> Dict[str, Any]:
        """Compute current system metrics from database state"""
        # Agent counts by status
        agent_stats = self.db.query(
            Agent.current_status,
            func.count(Agent.agent_id).label('count')
        ).group_by(Agent.current_status).all()
        
        agent_counts = {}
        for status, count in agent_stats:
            agent_counts[status.value] = count
        
        # Task counts by status
        task_stats = self.db.query(
            Task.status,
            func.count(Task.task_id).label('count')
        ).group_by(Task.status).all()
        
        task_counts = {}
        for status, count in task_stats:
            task_counts[status.value] = count
        
        # Calculate performance metrics
        active_agents = self.db.query(Agent).filter(
            Agent.current_status.in_(['idle', 'working'])
        ).all()
        
        avg_response_time = None
        avg_cpu_usage = None
        avg_memory_usage = None
        
        if active_agents:
            response_times = [a.average_response_time_ms for a in active_agents if a.average_response_time_ms]
            cpu_usages = [a.cpu_usage_percent for a in active_agents if a.cpu_usage_percent]
            memory_usages = [a.memory_usage_mb for a in active_agents if a.memory_usage_mb]
            
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
            if cpu_usages:
                avg_cpu_usage = sum(cpu_usages) / len(cpu_usages)
            if memory_usages:
                avg_memory_usage = sum(memory_usages) / len(memory_usages)
        
        # Calculate throughput (tasks completed in last minute)
        one_minute_ago = datetime.utcnow() - timedelta(minutes=1)
        tasks_per_minute = self.db.query(Task).filter(
            Task.status == TaskStatus.completed,
            Task.completed_at >= one_minute_ago
        ).count()
        
        # Calculate tokens per second (from last minute of completed tasks)
        recent_tasks = self.db.query(Task).filter(
            Task.status == TaskStatus.completed,
            Task.completed_at >= one_minute_ago,
            Task.token_usage.isnot(None),
            Task.processing_time_seconds.isnot(None)
        ).all()
        
        tokens_per_second = None
        if recent_tasks:
            total_tokens = sum(task.token_usage for task in recent_tasks)
            total_time = sum(float(task.processing_time_seconds) for task in recent_tasks)
            if total_time > 0:
                tokens_per_second = total_tokens / total_time
        
        return {
            "active_agents_count": agent_counts.get('idle', 0) + agent_counts.get('working', 0),
            "idle_agents_count": agent_counts.get('idle', 0),
            "working_agents_count": agent_counts.get('working', 0),
            "offline_agents_count": agent_counts.get('offline', 0),
            "error_agents_count": agent_counts.get('error', 0),
            "pending_tasks_count": task_counts.get('pending', 0),
            "running_tasks_count": task_counts.get('running', 0),
            "completed_tasks_count": task_counts.get('completed', 0),
            "failed_tasks_count": task_counts.get('failed', 0),
            "avg_response_time_ms": avg_response_time,
            "tokens_per_second": tokens_per_second,
            "tasks_per_minute": float(tasks_per_minute),
            "avg_cpu_usage_percent": avg_cpu_usage,
            "avg_memory_usage_mb": avg_memory_usage
        }
    
    # Agent Performance Metrics
    
    async def record_agent_performance(
        self,
        agent_id: UUID,
        tasks_completed: int = 0,
        tasks_failed: int = 0,
        avg_task_duration_seconds: Optional[float] = None,
        tokens_processed: int = 0,
        tokens_per_second: Optional[float] = None,
        avg_response_time_ms: Optional[float] = None,
        min_response_time_ms: Optional[float] = None,
        max_response_time_ms: Optional[float] = None,
        p95_response_time_ms: Optional[float] = None,
        success_rate_percent: Optional[float] = None,
        retry_rate_percent: Optional[float] = None,
        cpu_usage_percent: Optional[float] = None,
        memory_usage_mb: Optional[float] = None,
        cost_usd: Optional[float] = None,
        cost_per_token: Optional[float] = None
    ) -> AgentPerformanceMetric:
        """Record agent performance metrics"""
        metric = AgentPerformanceMetric(
            agent_id=agent_id,
            tasks_completed=tasks_completed,
            tasks_failed=tasks_failed,
            avg_task_duration_seconds=avg_task_duration_seconds,
            tokens_processed=tokens_processed,
            tokens_per_second=tokens_per_second,
            avg_response_time_ms=avg_response_time_ms,
            min_response_time_ms=min_response_time_ms,
            max_response_time_ms=max_response_time_ms,
            p95_response_time_ms=p95_response_time_ms,
            success_rate_percent=success_rate_percent,
            retry_rate_percent=retry_rate_percent,
            cpu_usage_percent=cpu_usage_percent,
            memory_usage_mb=memory_usage_mb,
            cost_usd=cost_usd,
            cost_per_token=cost_per_token
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    async def get_agent_performance_metrics(
        self,
        agent_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[AgentPerformanceMetric]:
        """Get agent performance metrics for a time range"""
        query = self.db.query(AgentPerformanceMetric).filter(
            AgentPerformanceMetric.agent_id == agent_id
        )
        
        if start_time:
            query = query.filter(AgentPerformanceMetric.timestamp >= start_time)
        if end_time:
            query = query.filter(AgentPerformanceMetric.timestamp <= end_time)
        
        return query.order_by(desc(AgentPerformanceMetric.timestamp)).limit(limit).all()
    
    async def get_top_performing_agents(
        self,
        metric: str = "avg_response_time_ms",
        limit: int = 10,
        hours: int = 24
    ) -> List[Tuple[UUID, float]]:
        """Get top performing agents by a specific metric"""
        start_time = datetime.utcnow() - timedelta(hours=hours)
        
        if metric == "avg_response_time_ms":
            # Lower is better for response time
            query = self.db.query(
                AgentPerformanceMetric.agent_id,
                func.avg(AgentPerformanceMetric.avg_response_time_ms).label('avg_metric')
            )
        elif metric == "success_rate_percent":
            # Higher is better for success rate
            query = self.db.query(
                AgentPerformanceMetric.agent_id,
                func.avg(AgentPerformanceMetric.success_rate_percent).label('avg_metric')
            )
        elif metric == "tokens_per_second":
            # Higher is better for throughput
            query = self.db.query(
                AgentPerformanceMetric.agent_id,
                func.avg(AgentPerformanceMetric.tokens_per_second).label('avg_metric')
            )
        else:
            raise ValueError(f"Unknown metric: {metric}")
        
        query = query.filter(
            AgentPerformanceMetric.timestamp >= start_time
        ).group_by(AgentPerformanceMetric.agent_id)
        
        if metric == "avg_response_time_ms":
            query = query.order_by(asc('avg_metric'))  # Lower is better
        else:
            query = query.order_by(desc('avg_metric'))  # Higher is better
        
        results = query.limit(limit).all()
        return [(agent_id, float(metric_value)) for agent_id, metric_value in results if metric_value is not None]
    
    # Task Performance Metrics
    
    async def record_task_performance(
        self,
        task_id: UUID,
        agent_id: Optional[UUID] = None,
        queue_time_seconds: Optional[float] = None,
        execution_time_seconds: Optional[float] = None,
        total_time_seconds: Optional[float] = None,
        tokens_processed: Optional[int] = None,
        tokens_per_second: Optional[float] = None,
        completion_status: Optional[str] = None,
        retry_attempts: int = 0,
        cost_usd: Optional[float] = None,
        error_type: Optional[str] = None,
        error_count: int = 0,
        custom_metrics: Optional[Dict[str, Any]] = None
    ) -> TaskPerformanceMetric:
        """Record task performance metrics"""
        metric = TaskPerformanceMetric(
            task_id=task_id,
            agent_id=agent_id,
            queue_time_seconds=queue_time_seconds,
            execution_time_seconds=execution_time_seconds,
            total_time_seconds=total_time_seconds,
            tokens_processed=tokens_processed,
            tokens_per_second=tokens_per_second,
            completion_status=completion_status,
            retry_attempts=retry_attempts,
            cost_usd=cost_usd,
            error_type=error_type,
            error_count=error_count,
            custom_metrics=custom_metrics
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    # Cost Metrics
    
    async def record_cost_metrics(
        self,
        entity_type: MetricType,
        entity_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        input_cost_per_token: Optional[float] = None,
        output_cost_per_token: Optional[float] = None,
        input_cost_usd: Optional[float] = None,
        output_cost_usd: Optional[float] = None,
        total_cost_usd: Optional[float] = None,
        compute_cost_usd: Optional[float] = None,
        storage_cost_usd: Optional[float] = None,
        bandwidth_cost_usd: Optional[float] = None,
        model_name: Optional[str] = None,
        provider: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CostMetric:
        """Record cost metrics"""
        metric = CostMetric(
            entity_type=entity_type,
            entity_id=entity_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            input_cost_per_token=input_cost_per_token,
            output_cost_per_token=output_cost_per_token,
            input_cost_usd=input_cost_usd,
            output_cost_usd=output_cost_usd,
            total_cost_usd=total_cost_usd,
            compute_cost_usd=compute_cost_usd,
            storage_cost_usd=storage_cost_usd,
            bandwidth_cost_usd=bandwidth_cost_usd,
            model_name=model_name,
            provider=provider,
            metadata=metadata
        )
        
        self.db.add(metric)
        self.db.commit()
        self.db.refresh(metric)
        
        return metric
    
    async def get_cost_breakdown(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        entity_type: Optional[MetricType] = None,
        entity_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get cost breakdown for analysis"""
        query = self.db.query(CostMetric)
        
        if start_time:
            query = query.filter(CostMetric.timestamp >= start_time)
        if end_time:
            query = query.filter(CostMetric.timestamp <= end_time)
        if entity_type:
            query = query.filter(CostMetric.entity_type == entity_type)
        if entity_id:
            query = query.filter(CostMetric.entity_id == entity_id)
        
        metrics = query.all()
        
        # Calculate totals
        total_input_cost = sum(m.input_cost_usd or 0 for m in metrics)
        total_output_cost = sum(m.output_cost_usd or 0 for m in metrics)
        total_compute_cost = sum(m.compute_cost_usd or 0 for m in metrics)
        total_storage_cost = sum(m.storage_cost_usd or 0 for m in metrics)
        total_bandwidth_cost = sum(m.bandwidth_cost_usd or 0 for m in metrics)
        
        # Group by model/provider
        model_costs = {}
        provider_costs = {}
        
        for metric in metrics:
            if metric.model_name:
                model_costs[metric.model_name] = model_costs.get(metric.model_name, 0) + (metric.total_cost_usd or 0)
            if metric.provider:
                provider_costs[metric.provider] = provider_costs.get(metric.provider, 0) + (metric.total_cost_usd or 0)
        
        return {
            "total_cost_usd": total_input_cost + total_output_cost + total_compute_cost + total_storage_cost + total_bandwidth_cost,
            "breakdown": {
                "input_cost_usd": total_input_cost,
                "output_cost_usd": total_output_cost,
                "compute_cost_usd": total_compute_cost,
                "storage_cost_usd": total_storage_cost,
                "bandwidth_cost_usd": total_bandwidth_cost
            },
            "by_model": model_costs,
            "by_provider": provider_costs,
            "total_tokens": sum(m.total_tokens for m in metrics),
            "avg_cost_per_token": (total_input_cost + total_output_cost) / max(sum(m.total_tokens for m in metrics), 1)
        }
    
    # Alert Metrics
    
    async def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        threshold_value: Optional[float] = None,
        actual_value: Optional[float] = None,
        entity_type: Optional[MetricType] = None,
        entity_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AlertMetric:
        """Create a new alert"""
        alert = AlertMetric(
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            threshold_value=threshold_value,
            actual_value=actual_value,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata
        )
        
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        
        return alert
    
    async def get_active_alerts(self, severity: Optional[str] = None) -> List[AlertMetric]:
        """Get unresolved alerts"""
        query = self.db.query(AlertMetric).filter(AlertMetric.is_resolved == 0)
        
        if severity:
            query = query.filter(AlertMetric.severity == severity)
        
        return query.order_by(desc(AlertMetric.timestamp)).all()
    
    async def resolve_alert(
        self,
        alert_id: int,
        resolution_notes: Optional[str] = None
    ) -> Optional[AlertMetric]:
        """Resolve an alert"""
        alert = self.db.query(AlertMetric).filter(AlertMetric.id == alert_id).first()
        if not alert:
            return None
        
        alert.is_resolved = 1
        alert.resolved_at = func.now()
        alert.resolution_notes = resolution_notes
        
        self.db.commit()
        self.db.refresh(alert)
        
        return alert
    
    # Time-Series Analysis
    
    async def get_time_series_data(
        self,
        metric_name: str,
        start_time: datetime,
        end_time: datetime,
        entity_type: Optional[MetricType] = None,
        entity_id: Optional[str] = None,
        aggregation: str = "avg",  # avg, sum, min, max, count
        interval_minutes: int = 60
    ) -> List[Dict[str, Any]]:
        """Get time-series data for visualization"""
        # This is a simplified implementation
        # In production, you'd want to use specialized time-series queries
        
        if metric_name == "system_response_time":
            query = self.db.query(
                SystemMetric.timestamp,
                SystemMetric.avg_response_time_ms
            ).filter(
                SystemMetric.timestamp >= start_time,
                SystemMetric.timestamp <= end_time
            ).order_by(SystemMetric.timestamp)
            
            results = query.all()
            return [
                {
                    "timestamp": result.timestamp.isoformat(),
                    "value": result.avg_response_time_ms
                }
                for result in results if result.avg_response_time_ms is not None
            ]
        
        elif metric_name == "system_throughput":
            query = self.db.query(
                SystemMetric.timestamp,
                SystemMetric.tokens_per_second
            ).filter(
                SystemMetric.timestamp >= start_time,
                SystemMetric.timestamp <= end_time
            ).order_by(SystemMetric.timestamp)
            
            results = query.all()
            return [
                {
                    "timestamp": result.timestamp.isoformat(),
                    "value": result.tokens_per_second
                }
                for result in results if result.tokens_per_second is not None
            ]
        
        elif metric_name == "system_cost":
            query = self.db.query(
                SystemMetric.timestamp,
                SystemMetric.total_cost_usd
            ).filter(
                SystemMetric.timestamp >= start_time,
                SystemMetric.timestamp <= end_time
            ).order_by(SystemMetric.timestamp)
            
            results = query.all()
            return [
                {
                    "timestamp": result.timestamp.isoformat(),
                    "value": result.total_cost_usd
                }
                for result in results if result.total_cost_usd is not None
            ]
        
        else:
            logger.warning(f"Unknown metric: {metric_name}")
            return []
    
    # Cleanup
    
    async def cleanup_old_metrics(self, days_old: int = 30) -> Dict[str, int]:
        """Clean up old metric data"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        # Count records to be deleted
        system_count = self.db.query(SystemMetric).filter(SystemMetric.timestamp < cutoff_date).count()
        agent_perf_count = self.db.query(AgentPerformanceMetric).filter(AgentPerformanceMetric.timestamp < cutoff_date).count()
        task_perf_count = self.db.query(TaskPerformanceMetric).filter(TaskPerformanceMetric.timestamp < cutoff_date).count()
        cost_count = self.db.query(CostMetric).filter(CostMetric.timestamp < cutoff_date).count()
        
        # Delete old records
        self.db.query(SystemMetric).filter(SystemMetric.timestamp < cutoff_date).delete()
        self.db.query(AgentPerformanceMetric).filter(AgentPerformanceMetric.timestamp < cutoff_date).delete()
        self.db.query(TaskPerformanceMetric).filter(TaskPerformanceMetric.timestamp < cutoff_date).delete()
        self.db.query(CostMetric).filter(CostMetric.timestamp < cutoff_date).delete()
        
        self.db.commit()
        
        return {
            "system_metrics_deleted": system_count,
            "agent_performance_deleted": agent_perf_count,
            "task_performance_deleted": task_perf_count,
            "cost_metrics_deleted": cost_count
        }