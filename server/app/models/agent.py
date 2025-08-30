from sqlalchemy import Column, String, TIMESTAMP, Enum, Integer, Float, Text, JSON, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
from .base import Base
import enum


class AgentStatus(enum.Enum):
    idle = "idle"
    working = "working"
    paused = "paused"
    error = "error"
    offline = "offline"


class AgentCapability(enum.Enum):
    text_processing = "text_processing"
    code_generation = "code_generation"
    data_analysis = "data_analysis"
    image_processing = "image_processing"
    web_scraping = "web_scraping"
    api_integration = "api_integration"
    database_operations = "database_operations"


class Agent(Base):
    __tablename__ = "agents"
    
    # Primary identification
    agent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name = Column(String(255), nullable=False)
    agent_type = Column(String(255), nullable=False)
    hostname = Column(String(255), nullable=False)
    version = Column(String(50), nullable=True)
    
    # Status tracking
    current_status = Column(Enum(AgentStatus), nullable=False, default=AgentStatus.idle)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    last_heartbeat = Column(TIMESTAMP(timezone=True), default=func.now())
    last_activity = Column(TIMESTAMP(timezone=True))
    
    # Capabilities and configuration
    capabilities = Column(JSON, nullable=True)  # Array of AgentCapability values
    max_concurrent_tasks = Column(Integer, default=1)
    current_task_count = Column(Integer, default=0)
    
    # Performance metrics
    total_tasks_completed = Column(Integer, default=0)
    total_tokens_processed = Column(Integer, default=0)
    total_processing_time_seconds = Column(Float, default=0.0)
    average_response_time_ms = Column(Float, nullable=True)
    
    # Resource usage
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    
    # Configuration and metadata
    config = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    
    # Error tracking
    last_error = Column(Text, nullable=True)
    error_count = Column(Integer, default=0)
    
    # Relationships
    tasks = relationship("Task", back_populates="assigned_agent", cascade="all, delete-orphan")
    metrics = relationship("AgentMetric", back_populates="agent", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_agent_status_heartbeat', 'current_status', 'last_heartbeat'),
        Index('idx_agent_hostname', 'hostname'),
        Index('idx_agent_type', 'agent_type'),
        Index('idx_agent_last_activity', 'last_activity'),
    )
    
    def is_available(self) -> bool:
        """Check if agent is available for new tasks"""
        return (
            self.current_status in [AgentStatus.idle, AgentStatus.working] and
            self.current_task_count < self.max_concurrent_tasks
        )
    
    def update_heartbeat(self):
        """Update the last heartbeat timestamp"""
        self.last_heartbeat = func.now()
    
    def __repr__(self):
        return f"<Agent(id={self.agent_id}, name={self.agent_name}, status={self.current_status.value})>"


class AgentMetric(Base):
    """Time-series metrics for individual agents"""
    __tablename__ = "agent_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    agent_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Performance metrics
    tasks_completed_count = Column(Integer, default=0)
    tokens_processed_count = Column(Integer, default=0)
    response_time_ms = Column(Float, nullable=True)
    throughput_tps = Column(Float, nullable=True)  # Tokens per second
    
    # Resource metrics
    cpu_usage_percent = Column(Float, nullable=True)
    memory_usage_mb = Column(Float, nullable=True)
    
    # Cost metrics
    estimated_cost_usd = Column(Float, nullable=True)
    
    # Additional metrics as JSON
    custom_metrics = Column(JSON, nullable=True)
    
    # Relationship
    agent = relationship("Agent", back_populates="metrics")
    
    # Indexes for time-series queries
    __table_args__ = (
        Index('idx_agent_metrics_agent_timestamp', 'agent_id', 'timestamp'),
        Index('idx_agent_metrics_timestamp', 'timestamp'),
    )