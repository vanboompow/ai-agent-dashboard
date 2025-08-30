"""Prometheus metrics collection for the AI Agent Dashboard API."""
import time
from typing import Dict, List
from functools import wraps

from prometheus_client import Counter, Histogram, Gauge, Info, start_http_server, generate_latest
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import psutil

# Application info
app_info = Info('app_info', 'Application information')
app_info.info({
    'name': 'ai_agent_dashboard',
    'version': '1.0.0',
    'description': 'AI Agent Dashboard API'
})

# HTTP Metrics
http_requests_total = Counter(
    'http_requests_total',
    'Total number of HTTP requests',
    ['method', 'endpoint', 'status']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0]
)

http_request_size_bytes = Histogram(
    'http_request_size_bytes',
    'HTTP request size in bytes',
    ['method', 'endpoint'],
    buckets=[1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
)

http_response_size_bytes = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'endpoint'],
    buckets=[1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]
)

active_connections = Gauge(
    'active_connections',
    'Number of active HTTP connections'
)

# Business Logic Metrics
agents_total = Gauge(
    'agents_total',
    'Total number of agents',
    ['status']
)

tasks_total = Gauge(
    'tasks_total',
    'Total number of tasks',
    ['status', 'priority']
)

task_processing_duration_seconds = Histogram(
    'task_processing_duration_seconds',
    'Task processing duration in seconds',
    ['task_type', 'agent_type'],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)

tokens_processed_total = Counter(
    'tokens_processed_total',
    'Total number of tokens processed',
    ['agent_type']
)

api_costs_total = Counter(
    'api_costs_total',
    'Total API costs in USD',
    ['provider', 'model']
)

# System Metrics
system_cpu_usage = Gauge('system_cpu_usage_percent', 'System CPU usage percentage')
system_memory_usage = Gauge('system_memory_usage_percent', 'System memory usage percentage')
system_disk_usage = Gauge('system_disk_usage_percent', 'System disk usage percentage')

# Database Metrics
db_connections_active = Gauge('db_connections_active', 'Active database connections')
db_connections_idle = Gauge('db_connections_idle', 'Idle database connections')
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['query_type'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

# Redis Metrics
redis_operations_total = Counter(
    'redis_operations_total',
    'Total Redis operations',
    ['operation', 'result']
)

redis_key_count = Gauge('redis_key_count', 'Number of keys in Redis')

# Celery Metrics
celery_tasks_total = Counter(
    'celery_tasks_total',
    'Total Celery tasks',
    ['task_name', 'status']
)

celery_task_duration_seconds = Histogram(
    'celery_task_duration_seconds',
    'Celery task duration in seconds',
    ['task_name'],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
)

celery_workers_active = Gauge('celery_workers_active', 'Number of active Celery workers')


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Middleware to collect Prometheus metrics for HTTP requests."""
    
    def __init__(self, app):
        super().__init__(app)
        self.active_requests = 0
    
    async def dispatch(self, request: Request, call_next):
        # Track active connections
        self.active_requests += 1
        active_connections.set(self.active_requests)
        
        start_time = time.time()
        method = request.method
        path = self.normalize_path(request.url.path)
        
        # Get request size
        request_size = 0
        if hasattr(request, '_body') and request._body:
            request_size = len(request._body)
        
        try:
            response = await call_next(request)
            
            # Calculate metrics
            duration = time.time() - start_time
            status_code = str(response.status_code)
            
            # Get response size
            response_size = 0
            if hasattr(response, 'body') and response.body:
                response_size = len(response.body)
            
            # Update metrics
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status=status_code
            ).inc()
            
            http_request_duration_seconds.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            if request_size > 0:
                http_request_size_bytes.labels(
                    method=method,
                    endpoint=path
                ).observe(request_size)
            
            if response_size > 0:
                http_response_size_bytes.labels(
                    method=method,
                    endpoint=path
                ).observe(response_size)
            
            return response
            
        except Exception as exc:
            # Track errors
            http_requests_total.labels(
                method=method,
                endpoint=path,
                status="500"
            ).inc()
            
            raise
            
        finally:
            self.active_requests -= 1
            active_connections.set(self.active_requests)
    
    def normalize_path(self, path: str) -> str:
        """Normalize URL path to reduce cardinality."""
        # Remove trailing slashes
        path = path.rstrip('/')
        
        # Replace UUIDs with placeholder
        import re
        uuid_pattern = r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
        path = re.sub(uuid_pattern, '/{id}', path, flags=re.IGNORECASE)
        
        # Replace numeric IDs with placeholder
        numeric_pattern = r'/\d+'
        path = re.sub(numeric_pattern, '/{id}', path)
        
        return path or '/'


def collect_system_metrics():
    """Collect system-level metrics."""
    try:
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=1)
        system_cpu_usage.set(cpu_percent)
        
        # Memory usage
        memory = psutil.virtual_memory()
        system_memory_usage.set(memory.percent)
        
        # Disk usage
        disk = psutil.disk_usage('/')
        system_disk_usage.set(disk.percent)
        
    except Exception as e:
        print(f"Error collecting system metrics: {e}")


def track_agent_metrics(agent_status_counts: Dict[str, int]):
    """Update agent-related metrics."""
    for status, count in agent_status_counts.items():
        agents_total.labels(status=status).set(count)


def track_task_metrics(task_counts: Dict[str, Dict[str, int]]):
    """Update task-related metrics."""
    for status, priority_counts in task_counts.items():
        for priority, count in priority_counts.items():
            tasks_total.labels(status=status, priority=priority).set(count)


def track_task_completion(task_type: str, agent_type: str, duration: float, tokens: int = 0):
    """Track task completion metrics."""
    task_processing_duration_seconds.labels(
        task_type=task_type,
        agent_type=agent_type
    ).observe(duration)
    
    if tokens > 0:
        tokens_processed_total.labels(agent_type=agent_type).inc(tokens)


def track_api_cost(provider: str, model: str, cost: float):
    """Track API costs."""
    api_costs_total.labels(provider=provider, model=model).inc(cost)


def track_db_operation(query_type: str, duration: float):
    """Track database operation metrics."""
    db_query_duration_seconds.labels(query_type=query_type).observe(duration)


def track_redis_operation(operation: str, success: bool):
    """Track Redis operation metrics."""
    result = "success" if success else "error"
    redis_operations_total.labels(operation=operation, result=result).inc()


def track_celery_task(task_name: str, status: str, duration: float = None):
    """Track Celery task metrics."""
    celery_tasks_total.labels(task_name=task_name, status=status).inc()
    
    if duration is not None:
        celery_task_duration_seconds.labels(task_name=task_name).observe(duration)


def metrics_decorator(metric_name: str = None):
    """Decorator to automatically track function execution metrics."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = metric_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track successful execution
                http_requests_total.labels(
                    method="INTERNAL",
                    endpoint=function_name,
                    status="200"
                ).inc()
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Track failed execution
                http_requests_total.labels(
                    method="INTERNAL",
                    endpoint=function_name,
                    status="500"
                ).inc()
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            function_name = metric_name or f"{func.__module__}.{func.__name__}"
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Track successful execution
                http_requests_total.labels(
                    method="INTERNAL",
                    endpoint=function_name,
                    status="200"
                ).inc()
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                # Track failed execution
                http_requests_total.labels(
                    method="INTERNAL",
                    endpoint=function_name,
                    status="500"
                ).inc()
                
                raise
        
        # Return appropriate wrapper based on whether function is async
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def init_metrics_server(port: int = 8080):
    """Initialize Prometheus metrics server."""
    try:
        start_http_server(port)
        print(f"Metrics server started on port {port}")
    except Exception as e:
        print(f"Failed to start metrics server: {e}")


def get_metrics() -> str:
    """Get current metrics in Prometheus format."""
    return generate_latest().decode('utf-8')