from sqlalchemy import Column, String, Integer, BigInteger, Text, TIMESTAMP, Enum, JSON, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid
import enum
from .base import Base


class LogLevel(enum.Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(enum.Enum):
    system = "system"
    agent = "agent"
    task = "task"
    api = "api"
    security = "security"
    performance = "performance"
    error = "error"
    audit = "audit"


class SystemLog(Base):
    """System-wide logs for infrastructure and application events"""
    __tablename__ = "system_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now(), index=True)
    
    # Log classification
    level = Column(Enum(LogLevel), nullable=False, index=True)
    category = Column(Enum(LogCategory), nullable=False, index=True)
    
    # Log content
    message = Column(Text, nullable=False)
    source = Column(String(100), nullable=True)  # Module or component that generated the log
    
    # Context information
    request_id = Column(String(100), nullable=True, index=True)  # For tracing requests
    session_id = Column(String(100), nullable=True)
    user_id = Column(String(100), nullable=True)
    
    # Structured context data
    context = Column(JSON, nullable=True)
    
    # Error details (for ERROR/CRITICAL logs)
    error_code = Column(String(50), nullable=True)
    stack_trace = Column(Text, nullable=True)
    
    # Performance data (for performance logs)
    duration_ms = Column(Integer, nullable=True)
    
    # Metadata
    hostname = Column(String(255), nullable=True)
    process_id = Column(Integer, nullable=True)
    thread_id = Column(String(50), nullable=True)
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_system_log_timestamp_level', 'timestamp', 'level'),
        Index('idx_system_log_category_timestamp', 'category', 'timestamp'),
        Index('idx_system_log_source_timestamp', 'source', 'timestamp'),
        Index('idx_system_log_error_code', 'error_code'),
        Index('idx_system_log_request_id', 'request_id'),
    )
    
    def __repr__(self):
        return f"<SystemLog(level={self.level.value}, category={self.category.value}, message={self.message[:50]})>"


class AgentLog(Base):
    """Agent-specific logs for tracking agent behavior and performance"""
    __tablename__ = "agent_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Agent association
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id"), nullable=False, index=True)
    
    # Log classification
    level = Column(Enum(LogLevel), nullable=False)
    category = Column(Enum(LogCategory), nullable=False)
    
    # Log content
    message = Column(Text, nullable=False)
    event_type = Column(String(100), nullable=True)  # startup, shutdown, task_start, task_complete, etc.
    
    # Task association (if log is task-related)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.task_id"), nullable=True, index=True)
    
    # Context information
    context = Column(JSON, nullable=True)
    
    # Performance metrics (captured at log time)
    cpu_usage_percent = Column(Integer, nullable=True)
    memory_usage_mb = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    
    # Error details
    error_code = Column(String(50), nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Relationships
    agent = relationship("Agent")
    task = relationship("Task")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_agent_log_agent_timestamp', 'agent_id', 'timestamp'),
        Index('idx_agent_log_task_timestamp', 'task_id', 'timestamp'),
        Index('idx_agent_log_level_timestamp', 'level', 'timestamp'),
        Index('idx_agent_log_event_type', 'event_type'),
        Index('idx_agent_log_category_timestamp', 'category', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<AgentLog(agent_id={self.agent_id}, level={self.level.value}, event={self.event_type})>"


class APILog(Base):
    """API request and response logs for monitoring and debugging"""
    __tablename__ = "api_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Request identification
    request_id = Column(String(100), nullable=False, unique=True, index=True)
    
    # HTTP details
    method = Column(String(10), nullable=False)  # GET, POST, PUT, DELETE, etc.
    endpoint = Column(String(500), nullable=False, index=True)
    status_code = Column(Integer, nullable=False, index=True)
    
    # Performance metrics
    response_time_ms = Column(Integer, nullable=False)
    request_size_bytes = Column(Integer, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)
    
    # Client information
    client_ip = Column(String(45), nullable=True)  # IPv6 support
    user_agent = Column(String(1000), nullable=True)
    user_id = Column(String(100), nullable=True)
    
    # Request/Response data (limited for privacy/storage)
    query_params = Column(JSON, nullable=True)
    request_headers = Column(JSON, nullable=True)
    response_headers = Column(JSON, nullable=True)
    
    # Error details (for 4xx/5xx responses)
    error_message = Column(String(1000), nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Additional context
    metadata = Column(JSON, nullable=True)
    
    # Indexes for API monitoring
    __table_args__ = (
        Index('idx_api_log_timestamp_status', 'timestamp', 'status_code'),
        Index('idx_api_log_endpoint_timestamp', 'endpoint', 'timestamp'),
        Index('idx_api_log_method_endpoint', 'method', 'endpoint'),
        Index('idx_api_log_response_time', 'response_time_ms'),
        Index('idx_api_log_client_ip', 'client_ip'),
        Index('idx_api_log_user_id', 'user_id'),
    )
    
    def __repr__(self):
        return f"<APILog(method={self.method}, endpoint={self.endpoint}, status={self.status_code})>"


class SecurityLog(Base):
    """Security-related logs for audit and monitoring"""
    __tablename__ = "security_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Security event classification
    event_type = Column(String(100), nullable=False, index=True)  # login, logout, auth_failure, permission_denied, etc.
    severity = Column(String(20), nullable=False, index=True)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Actor information
    user_id = Column(String(100), nullable=True, index=True)
    client_ip = Column(String(45), nullable=True, index=True)
    user_agent = Column(String(1000), nullable=True)
    
    # Event details
    resource = Column(String(500), nullable=True)  # Resource being accessed
    action = Column(String(100), nullable=True)  # Action attempted
    outcome = Column(String(20), nullable=False)  # SUCCESS, FAILURE, BLOCKED
    
    # Context and details
    message = Column(Text, nullable=False)
    context = Column(JSON, nullable=True)
    
    # Investigation fields
    is_investigated = Column(Integer, default=0)  # Boolean as int for performance
    investigated_at = Column(TIMESTAMP(timezone=True), nullable=True)
    investigated_by = Column(String(100), nullable=True)
    investigation_notes = Column(Text, nullable=True)
    
    # Additional metadata
    metadata = Column(JSON, nullable=True)
    
    # Indexes for security monitoring
    __table_args__ = (
        Index('idx_security_log_event_timestamp', 'event_type', 'timestamp'),
        Index('idx_security_log_severity_timestamp', 'severity', 'timestamp'),
        Index('idx_security_log_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_security_log_ip_timestamp', 'client_ip', 'timestamp'),
        Index('idx_security_log_outcome', 'outcome'),
        Index('idx_security_log_uninvestigated', 'is_investigated', 'severity'),
    )
    
    def __repr__(self):
        return f"<SecurityLog(event_type={self.event_type}, severity={self.severity}, outcome={self.outcome})>"


class AuditLog(Base):
    """Audit logs for compliance and change tracking"""
    __tablename__ = "audit_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    
    # Actor information
    user_id = Column(String(100), nullable=True, index=True)
    user_name = Column(String(255), nullable=True)
    
    # Action details
    action = Column(String(100), nullable=False, index=True)  # CREATE, UPDATE, DELETE, READ
    resource_type = Column(String(100), nullable=False, index=True)  # Agent, Task, Config, etc.
    resource_id = Column(String(255), nullable=True, index=True)
    
    # Change tracking
    old_values = Column(JSON, nullable=True)  # Previous state
    new_values = Column(JSON, nullable=True)  # New state
    changes_summary = Column(Text, nullable=True)  # Human-readable summary
    
    # Context information
    client_ip = Column(String(45), nullable=True)
    user_agent = Column(String(1000), nullable=True)
    session_id = Column(String(100), nullable=True)
    request_id = Column(String(100), nullable=True)
    
    # Business context
    reason = Column(String(500), nullable=True)  # Why the change was made
    impact_level = Column(String(20), nullable=True)  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Additional metadata
    metadata = Column(JSON, nullable=True)
    
    # Indexes for audit queries
    __table_args__ = (
        Index('idx_audit_log_resource_timestamp', 'resource_type', 'resource_id', 'timestamp'),
        Index('idx_audit_log_user_timestamp', 'user_id', 'timestamp'),
        Index('idx_audit_log_action_timestamp', 'action', 'timestamp'),
        Index('idx_audit_log_impact_timestamp', 'impact_level', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<AuditLog(action={self.action}, resource_type={self.resource_type}, user={self.user_id})>"


class LogRetentionPolicy(Base):
    """Configuration for log retention policies"""
    __tablename__ = "log_retention_policies"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Policy identification
    policy_name = Column(String(100), nullable=False, unique=True)
    table_name = Column(String(100), nullable=False)  # Which log table this applies to
    
    # Retention rules
    retention_days = Column(Integer, nullable=False)  # How long to keep logs
    archive_after_days = Column(Integer, nullable=True)  # Archive to cold storage after X days
    
    # Filtering criteria
    log_levels = Column(JSON, nullable=True)  # Which log levels this applies to
    categories = Column(JSON, nullable=True)  # Which categories this applies to
    
    # Policy status
    is_active = Column(Integer, default=1)  # Boolean as int
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())
    
    # Last execution
    last_executed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_execution_status = Column(String(20), nullable=True)  # SUCCESS, FAILURE, PARTIAL
    
    def __repr__(self):
        return f"<LogRetentionPolicy(name={self.policy_name}, retention_days={self.retention_days})>"