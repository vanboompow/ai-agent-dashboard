from sqlalchemy import Column, String, Integer, ForeignKey, BigInteger, Text, TIMESTAMP, DECIMAL, Enum, JSON, Index, Boolean, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from .base import Base


class TaskStatus(enum.Enum):
    pending = "pending"
    assigned = "assigned"
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    retry = "retry"


class TaskPriority(enum.Enum):
    critical = "critical"
    high = "high"
    normal = "normal"
    low = "low"


class TaskType(enum.Enum):
    text_processing = "text_processing"
    code_generation = "code_generation"
    data_analysis = "data_analysis"
    web_scraping = "web_scraping"
    api_call = "api_call"
    file_processing = "file_processing"
    computation = "computation"


# Association table for task dependencies (many-to-many)
task_dependencies = Table(
    'task_dependencies',
    Base.metadata,
    Column('task_id', UUID(as_uuid=True), ForeignKey('tasks.task_id'), primary_key=True),
    Column('depends_on_task_id', UUID(as_uuid=True), ForeignKey('tasks.task_id'), primary_key=True),
    Index('idx_task_dependencies_task', 'task_id'),
    Index('idx_task_dependencies_depends', 'depends_on_task_id')
)


class Task(Base):
    __tablename__ = "tasks"
    
    # Primary identification
    task_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.task_id"), nullable=True)
    
    # Task definition
    title = Column(String(255), nullable=False)
    description = Column(Text)
    task_type = Column(Enum(TaskType), nullable=False)
    sector = Column(String(100), nullable=True)
    
    # Status and priority
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.pending)
    priority = Column(Enum(TaskPriority), nullable=False, default=TaskPriority.normal)
    
    # Assignment and execution
    assigned_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id"), nullable=True)
    queue_name = Column(String(100), nullable=True)
    
    # Timing and scheduling
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    scheduled_at = Column(TIMESTAMP(timezone=True), nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    deadline = Column(TIMESTAMP(timezone=True), nullable=True)
    
    # Execution details
    max_retries = Column(Integer, default=3)
    retry_count = Column(Integer, default=0)
    timeout_seconds = Column(Integer, nullable=True)
    
    # Input/Output
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    
    # Progress tracking
    progress_percent = Column(Integer, default=0)
    steps_completed = Column(Integer, default=0)
    total_steps = Column(Integer, nullable=True)
    
    # Resource usage and costs
    token_usage = Column(BigInteger, default=0)
    estimated_cost_usd = Column(DECIMAL(10, 6), nullable=True)
    actual_cost_usd = Column(DECIMAL(10, 6), nullable=True)
    
    # Performance metrics
    processing_time_seconds = Column(DECIMAL(10, 3), nullable=True)
    tokens_per_second = Column(DECIMAL(10, 2), nullable=True)
    
    # Error handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Configuration and metadata
    config = Column(JSON, nullable=True)
    metadata = Column(JSON, nullable=True)
    tags = Column(JSON, nullable=True)  # Array of string tags
    
    # Audit fields
    created_by = Column(String(255), nullable=True)
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Relationships
    assigned_agent = relationship("Agent", back_populates="tasks")
    subtasks = relationship("Task", backref="parent_task", remote_side=[task_id])
    logs = relationship("TaskLog", back_populates="task", cascade="all, delete-orphan")
    
    # Dependencies (many-to-many)
    dependencies = relationship(
        "Task",
        secondary=task_dependencies,
        primaryjoin=task_id == task_dependencies.c.task_id,
        secondaryjoin=task_id == task_dependencies.c.depends_on_task_id,
        backref="dependent_tasks"
    )
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_task_status_created', 'status', 'created_at'),
        Index('idx_task_agent_status', 'assigned_agent_id', 'status'),
        Index('idx_task_priority_created', 'priority', 'created_at'),
        Index('idx_task_type_sector', 'task_type', 'sector'),
        Index('idx_task_queue', 'queue_name', 'status'),
        Index('idx_task_parent', 'parent_task_id'),
        Index('idx_task_scheduled', 'scheduled_at'),
        Index('idx_task_deadline', 'deadline'),
    )
    
    def can_start(self) -> bool:
        """Check if task dependencies are satisfied"""
        if not self.dependencies:
            return True
        return all(dep.status == TaskStatus.completed for dep in self.dependencies)
    
    def is_overdue(self) -> bool:
        """Check if task is past its deadline"""
        if not self.deadline:
            return False
        return func.now() > self.deadline
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds since task started"""
        if not self.started_at:
            return 0.0
        end_time = self.completed_at or func.now()
        return (end_time - self.started_at).total_seconds()
    
    def __repr__(self):
        return f"<Task(id={self.task_id}, title={self.title}, status={self.status.value})>"


class TaskLog(Base):
    __tablename__ = "task_logs"
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.task_id"), nullable=False)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    log_level = Column(String(20), nullable=False)  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    message = Column(Text, nullable=False)
    context = Column(JSON, nullable=True)  # Additional context data
    
    # Relationship
    task = relationship("Task", back_populates="logs")
    
    # Indexes
    __table_args__ = (
        Index('idx_task_log_task_timestamp', 'task_id', 'timestamp'),
        Index('idx_task_log_level_timestamp', 'log_level', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<TaskLog(task_id={self.task_id}, level={self.log_level}, message={self.message[:50]})>"


class TaskTemplate(Base):
    """Reusable task templates for common operations"""
    __tablename__ = "task_templates"
    
    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, unique=True)
    description = Column(Text)
    task_type = Column(Enum(TaskType), nullable=False)
    
    # Default values
    default_priority = Column(Enum(TaskPriority), default=TaskPriority.normal)
    default_timeout_seconds = Column(Integer, nullable=True)
    default_max_retries = Column(Integer, default=3)
    
    # Template configuration
    input_schema = Column(JSON, nullable=True)  # JSON schema for input validation
    default_config = Column(JSON, nullable=True)
    required_capabilities = Column(JSON, nullable=True)  # Array of required capabilities
    
    # Metadata
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    created_by = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<TaskTemplate(name={self.name}, type={self.task_type.value})>"