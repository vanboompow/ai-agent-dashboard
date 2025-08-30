"""Structured logging middleware for the AI Agent Dashboard API."""
import json
import time
import uuid
from typing import Callable
import logging
from contextvars import ContextVar

from fastapi import Request, Response
from fastapi.responses import StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
import structlog


# Context variable to store correlation ID throughout request lifecycle
correlation_id_ctx: ContextVar[str] = ContextVar('correlation_id', default='')

# Configure structlog for structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger("ai_dashboard.api")


class LoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured logging of HTTP requests and responses."""
    
    def __init__(self, app: Callable, logger_name: str = "ai_dashboard.api"):
        super().__init__(app)
        self.logger = structlog.get_logger(logger_name)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and response with structured logging."""
        # Generate correlation ID for request tracing
        correlation_id = str(uuid.uuid4())
        correlation_id_ctx.set(correlation_id)
        
        # Extract request information
        start_time = time.time()
        request_id = correlation_id
        method = request.method
        url = str(request.url)
        path = request.url.path
        query_params = dict(request.query_params)
        client_host = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        content_type = request.headers.get("content-type", "")
        
        # Add correlation ID to request headers for downstream services
        request.state.correlation_id = correlation_id
        
        # Log incoming request
        self.logger.info(
            "HTTP request received",
            correlation_id=correlation_id,
            request_id=request_id,
            method=method,
            url=url,
            path=path,
            query_params=query_params,
            client_host=client_host,
            user_agent=user_agent,
            content_type=content_type,
            event_type="request_received"
        )
        
        # Track request body size for non-streaming requests
        request_size = 0
        if hasattr(request, '_body'):
            request_size = len(request._body) if request._body else 0
        
        try:
            # Process the request
            response = await call_next(request)
            
            # Calculate response time
            process_time = time.time() - start_time
            
            # Extract response information
            status_code = response.status_code
            response_size = 0
            
            # Handle different response types
            if isinstance(response, StreamingResponse):
                # For streaming responses, we can't easily get the size
                response_type = "streaming"
            else:
                response_type = "standard"
                if hasattr(response, 'body') and response.body:
                    response_size = len(response.body)
            
            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Process-Time"] = str(process_time)
            
            # Determine log level based on status code
            if status_code >= 500:
                log_level = "error"
            elif status_code >= 400:
                log_level = "warning"
            else:
                log_level = "info"
            
            # Log response
            log_method = getattr(self.logger, log_level)
            log_method(
                "HTTP request completed",
                correlation_id=correlation_id,
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                process_time_ms=round(process_time * 1000, 2),
                request_size_bytes=request_size,
                response_size_bytes=response_size,
                response_type=response_type,
                client_host=client_host,
                event_type="request_completed"
            )
            
            return response
            
        except Exception as exc:
            # Calculate response time for failed requests
            process_time = time.time() - start_time
            
            # Log exception
            self.logger.error(
                "HTTP request failed with exception",
                correlation_id=correlation_id,
                request_id=request_id,
                method=method,
                path=path,
                process_time_ms=round(process_time * 1000, 2),
                exception=str(exc),
                exception_type=type(exc).__name__,
                client_host=client_host,
                event_type="request_failed",
                exc_info=True
            )
            
            # Re-raise the exception to let FastAPI handle it
            raise


class MetricsCollectionMiddleware(BaseHTTPMiddleware):
    """Middleware for collecting application metrics."""
    
    def __init__(self, app: Callable):
        super().__init__(app)
        self.request_count = {}
        self.request_duration = {}
        self.response_size_total = {}
        self.active_requests = 0
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collect metrics for requests and responses."""
        start_time = time.time()
        path = request.url.path
        method = request.method
        
        # Track active requests
        self.active_requests += 1
        
        try:
            response = await call_next(request)
            
            # Calculate metrics
            duration = time.time() - start_time
            status_code = response.status_code
            
            # Update metrics
            metric_key = f"{method}:{path}:{status_code}"
            self.request_count[metric_key] = self.request_count.get(metric_key, 0) + 1
            
            if metric_key not in self.request_duration:
                self.request_duration[metric_key] = []
            self.request_duration[metric_key].append(duration)
            
            # Track response size if available
            response_size = 0
            if hasattr(response, 'body') and response.body:
                response_size = len(response.body)
                size_key = f"{method}:{path}"
                self.response_size_total[size_key] = (
                    self.response_size_total.get(size_key, 0) + response_size
                )
            
            # Add metrics headers
            response.headers["X-Response-Time"] = str(round(duration * 1000, 2))
            response.headers["X-Active-Requests"] = str(self.active_requests)
            
            return response
            
        finally:
            self.active_requests -= 1


def get_correlation_id() -> str:
    """Get the current correlation ID from context."""
    return correlation_id_ctx.get('')


def create_child_logger(name: str, **kwargs) -> structlog.stdlib.BoundLogger:
    """Create a child logger with additional context."""
    correlation_id = get_correlation_id()
    logger_context = {"correlation_id": correlation_id, **kwargs}
    return structlog.get_logger(name).bind(**logger_context)


def setup_logging(app_name: str = "ai_dashboard", log_level: str = "INFO"):
    """Set up application logging configuration."""
    # Configure root logger
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format="%(message)s",
    )
    
    # Configure specific loggers
    loggers = [
        "ai_dashboard",
        "uvicorn.access",
        "uvicorn.error",
        "sqlalchemy.engine",
        "alembic",
        "celery"
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, log_level.upper()))
    
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)