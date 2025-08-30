import os
import secrets
from typing import List, Optional
from pydantic import AnyHttpUrl, validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # API Configuration
    project_name: str = "AI Agent Dashboard"
    version: str = "1.0.0"
    api_v1_str: str = "/api/v1"
    secret_key: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    
    # Security
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080"
    ]
    
    # Database Configuration
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://aiagent:aiagent123@localhost:5432/ai_dashboard"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 30
    database_pool_timeout: int = 30
    database_pool_recycle: int = 3600
    
    # Redis Configuration
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_max_connections: int = 50
    redis_connection_timeout: int = 5
    
    # Celery Configuration
    celery_broker_url: str = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    celery_result_backend: str = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
    celery_task_serializer: str = "json"
    celery_result_serializer: str = "json"
    celery_accept_content: List[str] = ["json"]
    celery_timezone: str = "UTC"
    celery_enable_utc: bool = True
    
    # Logging Configuration
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_file: Optional[str] = os.getenv("LOG_FILE", None)
    enable_json_logging: bool = os.getenv("ENABLE_JSON_LOGGING", "false").lower() == "true"
    
    # Performance Configuration
    max_workers: int = int(os.getenv("MAX_WORKERS", "4"))
    worker_timeout: int = 120
    keep_alive: int = 2
    max_requests: int = 1000
    max_requests_jitter: int = 50
    
    # Rate Limiting
    rate_limit_per_minute: int = 100
    burst_rate_limit: int = 200
    
    # Task Configuration
    default_task_timeout: int = 300  # 5 minutes
    max_task_retries: int = 3
    task_result_expires: int = 3600  # 1 hour
    
    # Agent Configuration
    agent_heartbeat_interval: int = 30  # seconds
    agent_offline_threshold: int = 300  # 5 minutes
    max_agents_per_type: int = 10
    
    # Metrics and Monitoring
    metrics_collection_interval: int = 60  # seconds
    metrics_retention_days: int = 30
    enable_performance_monitoring: bool = True
    enable_cost_tracking: bool = True
    
    # Alert Configuration
    enable_alerts: bool = True
    alert_email_enabled: bool = False
    alert_slack_enabled: bool = False
    alert_webhook_url: Optional[str] = None
    
    # Thresholds
    response_time_threshold_ms: float = 5000
    cpu_usage_threshold: float = 80.0
    memory_usage_threshold: float = 1024.0
    error_rate_threshold: float = 5.0
    cost_threshold_hourly: float = 100.0
    
    # File Storage
    upload_max_size: int = 10 * 1024 * 1024  # 10MB
    allowed_file_types: List[str] = [".txt", ".json", ".csv", ".py", ".js", ".md"]
    
    # External Services
    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    
    # Development Settings
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    testing: bool = os.getenv("TESTING", "false").lower() == "true"
    reload: bool = os.getenv("RELOAD", "false").lower() == "true"
    
    # Health Check Configuration
    health_check_interval: int = 30  # seconds
    health_check_timeout: int = 10   # seconds
    
    @validator("database_url", pre=True)
    def validate_database_url(cls, v) -> str:
        if not v.startswith(("postgresql://", "postgresql+asyncpg://")):
            raise ValueError("Database URL must be a PostgreSQL connection string")
        return v
    
    @validator("redis_url", pre=True)
    def validate_redis_url(cls, v) -> str:
        if not v.startswith("redis://"):
            raise ValueError("Redis URL must start with redis://")
        return v
    
    # Derived configuration
    @property
    def database_settings(self) -> dict:
        return {
            "pool_size": self.database_pool_size,
            "max_overflow": self.database_max_overflow,
            "pool_timeout": self.database_pool_timeout,
            "pool_recycle": self.database_pool_recycle,
            "echo": self.debug,
        }
    
    @property
    def redis_settings(self) -> dict:
        return {
            "max_connections": self.redis_max_connections,
            "socket_connect_timeout": self.redis_connection_timeout,
            "health_check_interval": 30,
            "retry_on_timeout": True,
        }
    
    class Config:
        env_file = ".env"
        case_sensitive = True


# Create enhanced settings instance
enhanced_settings = Settings()