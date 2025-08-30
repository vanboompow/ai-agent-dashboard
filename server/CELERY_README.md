# AI Agent Dashboard - Celery Task Processing System

This document provides comprehensive information about the Celery task processing system implemented for the AI Agent Dashboard.

## Overview

The Celery system provides robust, scalable task processing for AI agent operations with the following key features:

- **Multi-Queue Architecture**: High priority, normal, and background queues
- **Agent Simulation**: Realistic simulation of different AI agent types (GPT-4, Claude, Gemini, etc.)
- **Real-time Events**: Publisher/subscriber system for live dashboard updates
- **Comprehensive Monitoring**: Worker health, queue depths, system metrics, and alerting
- **Dead Letter Queue**: Automatic retry handling and failure management
- **Task Orchestration**: Intelligent task distribution and load balancing

## Architecture Components

### 1. Core Components

#### `celery_app.py` - Enhanced Celery Configuration
- Multi-queue routing with priority levels
- Task compression and serialization
- Retry policies and error handling
- Periodic task scheduling (Beat)
- Result backend with Redis

#### `tasks.py` - Task Implementations
- `process_agent_task()` - Main AI agent task processing with realistic simulation
- `collect_metrics()` - System and agent performance metrics collection
- `heartbeat_check()` - Agent health monitoring and status updates
- `task_orchestrator()` - Intelligent task assignment to available agents
- `cleanup_completed()` - Archive completed tasks and clean up logs
- Enhanced system control tasks (pause/resume/throttle)

#### `agent_simulator.py` - AI Agent Simulation
- Realistic simulation of 12+ different AI agent types
- Variable processing speeds, token rates, and costs
- Failure scenarios and retry logic
- Agent specialization and complexity handling
- Performance metrics and insights generation

#### `events.py` - Real-time Event System
- Redis pub/sub integration for real-time updates
- Event batching for performance optimization
- Multiple event types (task progress, system alerts, metrics, etc.)
- Event statistics and replay capabilities
- Server-sent events (SSE) compatibility

#### `monitoring.py` - System Health Monitoring
- Worker health monitoring and alerting
- Queue depth tracking and performance metrics
- Dead letter queue handling with automatic retries
- System resource monitoring (CPU, memory, disk)
- Comprehensive alerting system

### 2. Queue Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  High Priority  │    │     Normal      │    │   Background    │
│   Queue (10)    │    │   Queue (5)     │    │   Queue (1)     │
├─────────────────┤    ├─────────────────┤    ├─────────────────┤
│ • Agent tasks   │    │ • Metrics       │    │ • Cleanup       │
│ • Orchestration │    │ • Heartbeat     │    │ • Archival      │
│ • System ctrl   │    │ • General tasks │    │ • Maintenance   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 3. Event Flow

```
Tasks → Agent Simulator → Redis Events → SSE → Dashboard
  ↓                        ↓
Metrics → Monitoring → System Alerts → Real-time UI
```

## Quick Start

### 1. Install Dependencies

```bash
cd server
pip install -r requirements.txt
```

### 2. Start Redis

```bash
# Using Docker
docker run -d -p 6379:6379 redis:7-alpine

# Or using local Redis
redis-server
```

### 3. Start Workers

Using the provided worker management script:

```bash
# Start all workers with monitoring
python start_workers.py

# Start without Flower monitoring
python start_workers.py --no-monitoring

# Run in daemon mode
python start_workers.py --daemon

# Adjust log level
python start_workers.py --log-level DEBUG
```

### 4. Manual Worker Start

```bash
# High priority worker
celery -A app.celery_worker.celery_app worker --loglevel=info --hostname=high-priority-worker@%h --queues=high_priority --concurrency=1 --pool=solo

# Normal workers
celery -A app.celery_worker.celery_app worker --loglevel=info --hostname=normal-worker-1@%h --queues=normal --concurrency=4 --pool=threads

# Background worker  
celery -A app.celery_worker.celery_app worker --loglevel=info --hostname=background-worker@%h --queues=background --concurrency=2 --pool=threads

# Beat scheduler (for periodic tasks)
celery -A app.celery_worker.celery_app beat --loglevel=info

# Flower monitoring (optional)
celery -A app.celery_worker.celery_app flower --port=5555
```

## Configuration

### Environment Variables

```bash
# Redis connection
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Database (for task persistence)
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_dashboard
```

### Queue Configuration

The system uses three main queues with different priorities:

- **high_priority** (Priority 10): Critical tasks, agent processing, system control
- **normal** (Priority 5): Regular metrics, heartbeat checks, general operations  
- **background** (Priority 1): Cleanup, archival, maintenance tasks

## Task Types and Usage

### 1. Agent Task Processing

```python
from app.celery_worker.tasks import process_agent_task

# Submit a task
task_data = {
    'task_id': 'unique_task_id',
    'agent_type': 'gpt-4',
    'description': 'Analyze document',
    'complexity': 7,  # 1-10 scale
    'priority': 'high'
}

result = process_agent_task.delay(task_data)
```

### 2. Task Orchestration

```python
from app.celery_worker.tasks import task_orchestrator

orchestration_request = {
    'tasks': [
        {'task_id': 'task1', 'description': 'Task 1'},
        {'task_id': 'task2', 'description': 'Task 2'}
    ],
    'agent_preferences': ['gpt-4', 'claude-3-sonnet'],
    'priority': 'high',
    'batch_size': 5
}

result = task_orchestrator.delay(orchestration_request)
```

### 3. System Control

```python
from app.celery_worker.tasks import broadcast_pause_all, adjust_throttle

# Pause all agents
broadcast_pause_all.delay()

# Adjust processing throttle (0.1 to 2.0)
adjust_throttle.delay(0.5)  # 50% speed
```

## Monitoring and Health

### 1. Flower Web Interface

Access the Flower monitoring interface at `http://localhost:5555` (if started with monitoring).

Default credentials:
- Username: `admin`
- Password: `admin123`

### 2. System Health Monitoring

The monitoring system automatically tracks:

- **Worker Health**: CPU usage, memory consumption, task processing rates
- **Queue Health**: Depth monitoring, processing rates, wait times  
- **System Metrics**: Resource utilization, Redis connectivity, task statistics
- **Dead Letter Queue**: Failed task handling and retry management

### 3. Real-time Events

Events are published to Redis channels for real-time dashboard updates:

- `ai_dashboard_events` - All events
- `ai_dashboard_task_progress` - Task progress updates
- `ai_dashboard_metrics_update` - System metrics
- `ai_dashboard_system_alert` - System alerts

### 4. Health Check Endpoints

Monitor system health via the FastAPI endpoints:

```bash
# System status
curl http://localhost:8000/api/system/status

# Worker health
curl http://localhost:8000/api/system/workers

# Queue depths  
curl http://localhost:8000/api/system/queues
```

## Agent Types and Capabilities

The system simulates 12+ different AI agent types with realistic characteristics:

| Agent Type | Speed | Cost/1K tokens | Specialization | Max Complexity |
|------------|-------|----------------|----------------|----------------|
| GPT-4 | 0.8x | $0.030 | Reasoning, Analysis | 10 |
| GPT-4 Turbo | 1.2x | $0.010 | Speed, Reasoning | 10 |
| GPT-3.5 Turbo | 1.5x | $0.001 | General, Speed | 7 |
| Claude 3 Opus | 0.7x | $0.075 | Analysis, Safety | 10 |
| Claude 3 Sonnet | 1.0x | $0.015 | General, Balanced | 8 |
| Claude 3 Haiku | 2.0x | $0.0025 | Speed, Concise | 6 |
| Gemini Pro | 1.1x | $0.005 | Multimodal | 8 |
| Gemini Ultra | 0.9x | $0.020 | Reasoning, Multimodal | 10 |
| Llama 2 70B | 0.6x | $0.000 | Open Source | 8 |
| Llama 2 13B | 1.3x | $0.000 | Open Source, Speed | 6 |
| Mistral Large | 0.9x | $0.008 | Reasoning, Multilingual | 9 |
| Mistral Medium | 1.4x | $0.0027 | General, Multilingual | 7 |

## Error Handling and Recovery

### 1. Task Retry Logic

- Automatic retries for transient failures (network, rate limits, etc.)
- Exponential backoff with configurable delays
- Maximum retry limits per task type
- Dead letter queue for permanently failed tasks

### 2. Worker Recovery

- Automatic worker restart on process failure
- Health monitoring with automatic alerts
- Graceful shutdown handling
- Resource leak prevention

### 3. Dead Letter Queue Processing

```python
from app.celery_worker.monitoring import DeadLetterQueueHandler

# Process DLQ (runs automatically every 5 minutes)
dlq_handler = DeadLetterQueueHandler(redis_client)
results = dlq_handler.process_dlq(max_age_hours=24)
```

## Performance Optimization

### 1. Worker Configuration

- **High Priority Queue**: Single-threaded (`solo` pool) for reliability
- **Normal Queue**: Multi-threaded (`threads` pool) for throughput  
- **Background Queue**: Lower concurrency for resource management

### 2. Resource Management

- Task-based memory limits
- CPU throttling support
- Connection pooling for Redis
- Result expiration and cleanup

### 3. Event Batching

Events are automatically batched for performance while maintaining real-time responsiveness:

- Batch size: 5-10 events
- Batch timeout: 1-2 seconds
- High-priority events bypass batching

## Development and Testing

### 1. Running Tests

```bash
# All tests
pytest

# Celery-specific tests
pytest tests/test_celery/

# With coverage
pytest --cov=app.celery_worker --cov-report=html
```

### 2. Development Mode

```bash
# Start workers with auto-reload
celery -A app.celery_worker.celery_app worker --loglevel=debug --reload

# Monitor events
python -c "from app.celery_worker.events import EventSubscriber; EventSubscriber().subscribe_to_events()"
```

### 3. Testing Agent Types

```python
from app.celery_worker.agent_simulator import run_agent_comparison

# Compare different agents on same task
results = run_agent_comparison(task_complexity=6, num_trials=3)
print(results)
```

## Troubleshooting

### Common Issues

1. **Workers not starting**:
   - Check Redis connectivity: `redis-cli ping`
   - Verify Python path includes `app` directory
   - Check for port conflicts

2. **Tasks not processing**:
   - Verify queue names match task routing
   - Check worker logs for errors
   - Ensure Redis has sufficient memory

3. **High memory usage**:
   - Reduce worker concurrency
   - Enable task result expiration
   - Monitor for memory leaks in custom tasks

4. **Slow processing**:
   - Check system resource usage
   - Adjust throttling settings
   - Scale workers horizontally

### Logging

Comprehensive logging is available at multiple levels:

```python
# Enable debug logging
import logging
logging.getLogger('app.celery_worker').setLevel(logging.DEBUG)
```

### Health Checks

```bash
# Check worker status
celery -A app.celery_worker.celery_app inspect active

# Check queue lengths
celery -A app.celery_worker.celery_app inspect reserved

# System stats
celery -A app.celery_worker.celery_app inspect stats
```

## Production Deployment

### 1. Systemd Service

Create `/etc/systemd/system/ai-dashboard-workers.service`:

```ini
[Unit]
Description=AI Dashboard Celery Workers
After=redis.service postgresql.service

[Service]
Type=notify
User=celery
Group=celery
WorkingDirectory=/opt/ai-dashboard/server
ExecStart=/opt/ai-dashboard/venv/bin/python start_workers.py --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Process Management

```bash
# Enable and start service
systemctl enable ai-dashboard-workers
systemctl start ai-dashboard-workers

# Monitor status
systemctl status ai-dashboard-workers
journalctl -u ai-dashboard-workers -f
```

### 3. Scaling

- Horizontal: Add more worker processes/machines
- Vertical: Increase worker concurrency per process
- Queue-based: Add specialized workers for specific task types

## Integration with Dashboard

The Celery system integrates with the dashboard frontend through:

1. **REST API**: Task submission and status endpoints
2. **Server-Sent Events**: Real-time progress updates
3. **WebSocket**: Optional bi-directional communication
4. **Metrics API**: Performance and health data

See the main FastAPI application (`app/main.py`) for API endpoints and SSE implementation.

## Security Considerations

- Redis authentication and SSL/TLS encryption in production
- Task input validation and sanitization
- Resource limits to prevent DoS attacks
- Audit logging for sensitive operations
- Network segmentation for worker processes

For additional support and advanced configuration, refer to the [Celery documentation](https://docs.celeryproject.org/) and the project's API documentation.