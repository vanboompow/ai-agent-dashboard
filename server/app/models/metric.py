from sqlalchemy import Column, String, Integer, BigInteger, Float, TIMESTAMP, Enum, JSON, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from .base import Base


class MetricType(enum.Enum):
    system = "system"
    agent = "agent"
    task = "task"
    cost = "cost"
    performance = "performance"
    error = "error"


class SystemMetric(Base):
    """System-wide metrics time series"""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Agent metrics
    active_agents_count = Column(Integer, default=0)
    idle_agents_count = Column(Integer, default=0)
    working_agents_count = Column(Integer, default=0)
    offline_agents_count = Column(Integer, default=0)
    error_agents_count = Column(Integer, default=0)
    
    # Task metrics
    pending_tasks_count = Column(Integer, default=0)
    running_tasks_count = Column(Integer, default=0)
    completed_tasks_count = Column(Integer, default=0)
    failed_tasks_count = Column(Integer, default=0)
    
    # Performance metrics
    avg_response_time_ms = Column(Float, nullable=True)
    tokens_per_second = Column(Float, nullable=True)
    tasks_per_minute = Column(Float, nullable=True)
    
    # Resource utilization
    avg_cpu_usage_percent = Column(Float, nullable=True)
    avg_memory_usage_mb = Column(Float, nullable=True)
    
    # Cost metrics
    total_cost_usd = Column(Float, nullable=True)
    cost_per_token = Column(Float, nullable=True)
    hourly_burn_rate_usd = Column(Float, nullable=True)
    
    # Error metrics
    error_rate_percent = Column(Float, nullable=True)
    timeout_rate_percent = Column(Float, nullable=True)
    
    # Additional metrics as JSON
    custom_metrics = Column(JSON, nullable=True)
    
    # Indexes for time-series queries
    __table_args__ = (
        Index('idx_system_metrics_timestamp', 'timestamp'),
        Index('idx_system_metrics_timestamp_desc', 'timestamp', postgresql_using='btree'),
    )
    
    def __repr__(self):
        return f"<SystemMetric(timestamp={self.timestamp}, active_agents={self.active_agents_count})>"


class AgentPerformanceMetric(Base):
    """Detailed agent performance metrics"""
    __tablename__ = "agent_performance_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id"), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Task execution metrics
    tasks_completed = Column(Integer, default=0)
    tasks_failed = Column(Integer, default=0)
    avg_task_duration_seconds = Column(Float, nullable=True)
    
    # Token processing metrics
    tokens_processed = Column(BigInteger, default=0)
    tokens_per_second = Column(Float, nullable=True)
    
    # Response time metrics
    avg_response_time_ms = Column(Float, nullable=True)
    min_response_time_ms = Column(Float, nullable=True)
    max_response_time_ms = Column(Float, nullable=True)
    p95_response_time_ms = Column(Float, nullable=True)
    
    # Quality metrics
    success_rate_percent = Column(Float, nullable=True)
    retry_rate_percent = Column(Float, nullable=True)
    
    # Resource usage
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    
    # Cost metrics
    cost_usd = Column(Float, nullable=True)
    cost_per_token = Column(Float, nullable=True)
    
    # Relationship
    agent = relationship("Agent")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_agent_perf_agent_timestamp', 'agent_id', 'timestamp'),
        Index('idx_agent_perf_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<AgentPerformanceMetric(agent_id={self.agent_id}, timestamp={self.timestamp})>"


class TaskPerformanceMetric(Base):
    """Task-level performance metrics"""
    __tablename__ = "task_performance_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.task_id"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id"), nullable=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Timing metrics
    queue_time_seconds = Column(Float, nullable=True)  # Time from creation to start
    execution_time_seconds = Column(Float, nullable=True)  # Time from start to completion
    total_time_seconds = Column(Float, nullable=True)  # Total time from creation to completion
    
    # Processing metrics
    tokens_processed = Column(BigInteger, nullable=True)
    tokens_per_second = Column(Float, nullable=True)
    
    # Quality metrics
    completion_status = Column(String(50), nullable=True)
    retry_attempts = Column(Integer, default=0)
    
    # Cost metrics
    cost_usd = Column(Float, nullable=True)
    
    # Error metrics (if task failed)
    error_type = Column(String(100), nullable=True)
    error_count = Column(Integer, default=0)
    
    # Additional metrics
    custom_metrics = Column(JSON, nullable=True)
    
    # Relationships
    task = relationship("Task")
    agent = relationship("Agent")
    
    # Indexes
    __table_args__ = (
        Index('idx_task_perf_task_timestamp', 'task_id', 'timestamp'),
        Index('idx_task_perf_agent_timestamp', 'agent_id', 'timestamp'),
        Index('idx_task_perf_timestamp', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<TaskPerformanceMetric(task_id={self.task_id}, execution_time={self.execution_time_seconds})>"


class CostMetric(Base):
    """Detailed cost tracking and analysis"""
    __tablename__ = "cost_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Entity association (can be system, agent, or task)
    entity_type = Column(Enum(MetricType), nullable=False)
    entity_id = Column(String(255), nullable=True)  # UUID as string for flexibility
    
    # Cost breakdown
    input_tokens = Column(BigInteger, default=0)
    output_tokens = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)
    
    # Pricing details
    input_cost_per_token = Column(Float, nullable=True)
    output_cost_per_token = Column(Float, nullable=True)
    
    # Total costs
    input_cost_usd = Column(Float, nullable=True)
    output_cost_usd = Column(Float, nullable=True)
    total_cost_usd = Column(Float, nullable=True)
    
    # Additional cost factors
    compute_cost_usd = Column(Float, nullable=True)
    storage_cost_usd = Column(Float, nullable=True)
    bandwidth_cost_usd = Column(Float, nullable=True)
    
    # Model/provider information
    model_name = Column(String(100), nullable=True)
    provider = Column(String(50), nullable=True)
    
    # Additional context
    metadata = Column(JSON, nullable=True)
    
    # Indexes for cost analysis
    __table_args__ = (
        Index('idx_cost_entity_timestamp', 'entity_type', 'entity_id', 'timestamp'),
        Index('idx_cost_timestamp', 'timestamp'),
        Index('idx_cost_model_timestamp', 'model_name', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<CostMetric(entity_type={self.entity_type.value}, total_cost=${self.total_cost_usd})>"


class AlertMetric(Base):
    """System alerts and thresholds monitoring"""
    __tablename__ = "alert_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Alert details
    alert_type = Column(String(100), nullable=False)  # CPU_HIGH, COST_THRESHOLD, ERROR_RATE, etc.
    severity = Column(String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Entity association
    entity_type = Column(Enum(MetricType), nullable=True)
    entity_id = Column(String(255), nullable=True)
    
    # Alert content
    title = Column(String(255), nullable=False)
    message = Column(String(1000), nullable=False)
    
    # Threshold information
    threshold_value = Column(Float, nullable=True)
    actual_value = Column(Float, nullable=True)
    
    # Status tracking
    is_acknowledged = Column(Integer, default=0)  # Boolean as int for performance
    acknowledged_at = Column(TIMESTAMP(timezone=True), nullable=True)
    acknowledged_by = Column(String(255), nullable=True)
    
    # Resolution
    is_resolved = Column(Integer, default=0)  # Boolean as int for performance
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    resolution_notes = Column(String(1000), nullable=True)
    
    # Additional context
    metadata = Column(JSON, nullable=True)
    
    # Indexes for alert management
    __table_args__ = (
        Index('idx_alert_type_severity', 'alert_type', 'severity'),
        Index('idx_alert_timestamp', 'timestamp'),
        Index('idx_alert_unresolved', 'is_resolved', 'timestamp'),
        Index('idx_alert_entity', 'entity_type', 'entity_id'),
    )
    
    def __repr__(self):
        return f"<AlertMetric(type={self.alert_type}, severity={self.severity}, resolved={bool(self.is_resolved)})>"


class MetricAggregation(Base):
    """Pre-computed metric aggregations for dashboard performance"""
    __tablename__ = "metric_aggregations"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Aggregation metadata
    metric_name = Column(String(100), nullable=False)
    aggregation_type = Column(String(50), nullable=False)  # hourly, daily, weekly
    period_start = Column(TIMESTAMP(timezone=True), nullable=False)
    period_end = Column(TIMESTAMP(timezone=True), nullable=False)
    
    # Entity scope (optional)
    entity_type = Column(Enum(MetricType), nullable=True)
    entity_id = Column(String(255), nullable=True)
    
    # Aggregated values
    count = Column(BigInteger, nullable=True)
    sum_value = Column(Float, nullable=True)
    avg_value = Column(Float, nullable=True)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    stddev_value = Column(Float, nullable=True)
    
    # Additional aggregated data
    percentile_50 = Column(Float, nullable=True)
    percentile_95 = Column(Float, nullable=True)
    percentile_99 = Column(Float, nullable=True)
    
    # Metadata
    computed_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    data_points_count = Column(Integer, nullable=True)
    
    # Indexes for fast dashboard queries
    __table_args__ = (
        Index('idx_aggregation_metric_period', 'metric_name', 'aggregation_type', 'period_start'),
        Index('idx_aggregation_entity_period', 'entity_type', 'entity_id', 'period_start'),
        Index('idx_aggregation_period', 'period_start', 'period_end'),
    )
    
    def __repr__(self):
        return f"<MetricAggregation(metric={self.metric_name}, type={self.aggregation_type}, period={self.period_start})>"