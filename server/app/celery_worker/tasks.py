from celery import Task
from celery.exceptions import Retry
from .celery_app import celery_app
from .agent_simulator import AgentSimulator
from .events import publish_event
import time
import random
import logging
import json
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import psutil
import uuid

logger = logging.getLogger(__name__)

# Redis connection for shared state
redis_client = redis.Redis.from_url("redis://localhost:6379/0", decode_responses=True)


class CallbackTask(Task):
    """Enhanced task with callbacks and comprehensive logging"""
    
    def on_success(self, retval, task_id, args, kwargs):
        """Success callback with event publishing"""
        logger.info(f"Task {task_id} succeeded with result: {retval}")
        publish_event('task_completed', {
            'task_id': task_id,
            'result': retval,
            'completed_at': datetime.utcnow().isoformat(),
            'execution_time': getattr(self.request, 'execution_time', 0)
        })
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Failure callback with enhanced error tracking"""
        logger.error(f"Task {task_id} failed with exception: {exc}")
        publish_event('task_failed', {
            'task_id': task_id,
            'error': str(exc),
            'error_type': type(exc).__name__,
            'traceback': str(einfo),
            'failed_at': datetime.utcnow().isoformat(),
            'args': args,
            'kwargs': kwargs
        })
        
        # Store failure in Redis for monitoring
        redis_client.hset(f"task_failures:{task_id}", mapping={
            'error': str(exc),
            'failed_at': datetime.utcnow().isoformat(),
            'retry_count': self.request.retries
        })
        redis_client.expire(f"task_failures:{task_id}", 86400)  # Expire after 24 hours
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Retry callback for tracking retry attempts"""
        logger.warning(f"Task {task_id} retry #{self.request.retries}: {exc}")
        publish_event('task_retry', {
            'task_id': task_id,
            'retry_count': self.request.retries,
            'error': str(exc),
            'retry_at': datetime.utcnow().isoformat()
        })


@celery_app.task(base=CallbackTask, bind=True, autoretry_for=(Exception,), retry_kwargs={'max_retries': 3, 'countdown': 60})
def process_agent_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process an agent task with realistic simulation and comprehensive tracking
    
    Args:
        task_data: Dictionary containing task information
            - task_id: Unique task identifier
            - agent_type: Type of agent (gpt-4, claude-3, gemini-pro, etc.)
            - description: Task description
            - complexity: Task complexity (1-10 scale)
            - priority: Task priority (low, normal, high, urgent)
    
    Returns:
        Dictionary with task results and metrics
    """
    start_time = datetime.utcnow()
    task_id = task_data.get('task_id', str(uuid.uuid4()))
    agent_type = task_data.get('agent_type', 'gpt-4')
    description = task_data.get('description', 'Processing task')
    complexity = task_data.get('complexity', 5)
    priority = task_data.get('priority', 'normal')
    
    logger.info(f"Starting task {task_id} with agent {agent_type}, complexity: {complexity}")
    
    # Initialize agent simulator
    simulator = AgentSimulator(agent_type)
    
    try:
        # Update task status to 'working'
        self.update_state(state='PROGRESS', meta={
            'current': 0,
            'total': 100,
            'status': 'Initializing agent...',
            'agent_type': agent_type,
            'started_at': start_time.isoformat()
        })
        
        # Store task in Redis for tracking
        redis_client.hset(f"active_tasks:{task_id}", mapping={
            'agent_type': agent_type,
            'description': description,
            'complexity': complexity,
            'priority': priority,
            'started_at': start_time.isoformat(),
            'status': 'in_progress'
        })
        redis_client.expire(f"active_tasks:{task_id}", 7200)  # 2 hours
        
        # Simulate realistic processing with agent-specific behavior
        total_steps = simulator.calculate_steps(complexity)
        tokens_processed = 0
        
        for step in range(total_steps):
            # Simulate processing step
            step_result = simulator.process_step(step, total_steps, complexity)
            
            if step_result.get('should_fail', False):
                # Simulate random failures for testing retry logic
                raise Exception(f"Simulated failure at step {step}: {step_result.get('error_message')}")
            
            tokens_processed += step_result.get('tokens', 0)
            
            # Update progress with realistic timing
            progress = int((step + 1) / total_steps * 100)
            self.update_state(state='PROGRESS', meta={
                'current': progress,
                'total': 100,
                'status': step_result.get('status', f'Processing step {step + 1}/{total_steps}'),
                'tokens_processed': tokens_processed,
                'estimated_cost': simulator.calculate_cost(tokens_processed),
                'agent_type': agent_type,
                'complexity': complexity
            })
            
            # Publish progress event
            publish_event('task_progress', {
                'task_id': task_id,
                'progress': progress,
                'status': step_result.get('status'),
                'tokens_processed': tokens_processed,
                'agent_type': agent_type
            })
            
            # Simulate processing time
            time.sleep(step_result.get('duration', 0.1))
            
            # Check for throttling
            throttle_rate = float(redis_client.get('system_throttle_rate') or 1.0)
            if throttle_rate < 1.0:
                time.sleep((1.0 - throttle_rate) * 2)  # Additional delay for throttling
        
        # Task completed successfully
        end_time = datetime.utcnow()
        execution_time = (end_time - start_time).total_seconds()
        
        final_result = simulator.generate_final_result(tokens_processed, execution_time)
        
        # Update Redis with completion status
        redis_client.hset(f"completed_tasks:{task_id}", mapping={
            'agent_type': agent_type,
            'description': description,
            'tokens_used': final_result['tokens_used'],
            'cost_usd': final_result['cost_usd'],
            'completed_at': end_time.isoformat(),
            'execution_time': execution_time
        })
        redis_client.expire(f"completed_tasks:{task_id}", 86400)  # 24 hours
        redis_client.delete(f"active_tasks:{task_id}")
        
        # Store execution time for callback
        self.request.execution_time = execution_time
        
        logger.info(f"Task {task_id} completed in {execution_time:.2f}s")
        
        return {
            'task_id': task_id,
            'status': 'completed',
            'agent_type': agent_type,
            'tokens_used': final_result['tokens_used'],
            'cost_usd': final_result['cost_usd'],
            'execution_time': execution_time,
            'completed_at': end_time.isoformat(),
            'complexity': complexity,
            'priority': priority,
            **final_result
        }
        
    except Exception as exc:
        # Clean up active task on failure
        redis_client.delete(f"active_tasks:{task_id}")
        logger.error(f"Task {task_id} failed: {exc}")
        raise


@celery_app.task(bind=True)
def collect_metrics(self) -> Dict[str, Any]:
    """
    Collect comprehensive system and agent metrics
    
    Returns:
        Dictionary containing system metrics
    """
    try:
        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Redis metrics
        redis_info = redis_client.info()
        
        # Active task metrics
        active_tasks = redis_client.keys("active_tasks:*")
        completed_tasks_today = redis_client.keys("completed_tasks:*")
        failed_tasks = redis_client.keys("task_failures:*")
        
        # Agent type distribution
        agent_types = {}
        for task_key in active_tasks:
            agent_type = redis_client.hget(task_key, 'agent_type')
            if agent_type:
                agent_types[agent_type] = agent_types.get(agent_type, 0) + 1
        
        # Cost tracking (last 24 hours)
        total_cost_today = 0.0
        for task_key in completed_tasks_today:
            cost = redis_client.hget(task_key, 'cost_usd')
            if cost:
                total_cost_today += float(cost)
        
        # Queue depths (requires Celery inspect)
        from celery import current_app
        inspect = current_app.control.inspect()
        active = inspect.active()
        reserved = inspect.reserved()
        
        queue_depths = {
            'high_priority': 0,
            'normal': 0,
            'background': 0
        }
        
        # Calculate queue depths from active and reserved tasks
        if active:
            for worker, tasks in active.items():
                for task in tasks:
                    queue = task.get('delivery_info', {}).get('routing_key', 'normal')
                    queue_depths[queue] = queue_depths.get(queue, 0) + 1
        
        if reserved:
            for worker, tasks in reserved.items():
                for task in tasks:
                    queue = task.get('delivery_info', {}).get('routing_key', 'normal')
                    queue_depths[queue] = queue_depths.get(queue, 0) + 1
        
        metrics = {
            'timestamp': datetime.utcnow().isoformat(),
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_total_gb': memory.total / (1024**3),
                'disk_percent': disk.percent,
                'disk_used_gb': disk.used / (1024**3),
                'disk_total_gb': disk.total / (1024**3)
            },
            'redis': {
                'connected_clients': redis_info.get('connected_clients', 0),
                'used_memory_mb': redis_info.get('used_memory', 0) / (1024**2),
                'keyspace_hits': redis_info.get('keyspace_hits', 0),
                'keyspace_misses': redis_info.get('keyspace_misses', 0)
            },
            'tasks': {
                'active_count': len(active_tasks),
                'completed_today': len(completed_tasks_today),
                'failed_count': len(failed_tasks),
                'agent_distribution': agent_types,
                'queue_depths': queue_depths
            },
            'costs': {
                'total_today_usd': round(total_cost_today, 2),
                'average_per_task_usd': round(total_cost_today / max(len(completed_tasks_today), 1), 3)
            }
        }
        
        # Store metrics in Redis with timestamp
        redis_client.zadd('metrics_history', {
            json.dumps(metrics): int(datetime.utcnow().timestamp())
        })
        
        # Keep only last 24 hours of metrics
        yesterday = int((datetime.utcnow() - timedelta(hours=24)).timestamp())
        redis_client.zremrangebyscore('metrics_history', 0, yesterday)
        
        # Publish metrics event
        publish_event('metrics_update', metrics)
        
        logger.debug(f"Collected metrics: {len(active_tasks)} active tasks, {cpu_percent}% CPU")
        
        return metrics
        
    except Exception as exc:
        logger.error(f"Failed to collect metrics: {exc}")
        return {'error': str(exc), 'timestamp': datetime.utcnow().isoformat()}


@celery_app.task(bind=True)
def heartbeat_check(self) -> Dict[str, Any]:
    """
    Monitor agent health and update status
    
    Returns:
        Dictionary containing health status
    """
    try:
        # Check Redis connectivity
        redis_client.ping()
        
        # Get active tasks for health assessment
        active_tasks = redis_client.keys("active_tasks:*")
        stale_tasks = []
        
        # Check for stale tasks (running > 1 hour)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)
        
        for task_key in active_tasks:
            started_at_str = redis_client.hget(task_key, 'started_at')
            if started_at_str:
                started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                if started_at < cutoff_time:
                    task_id = task_key.split(':')[1]
                    stale_tasks.append({
                        'task_id': task_id,
                        'started_at': started_at_str,
                        'duration_hours': (datetime.utcnow() - started_at).total_seconds() / 3600
                    })
        
        # System health indicators
        cpu_percent = psutil.cpu_percent()
        memory_percent = psutil.virtual_memory().percent
        
        health_status = 'healthy'
        alerts = []
        
        # Health checks
        if cpu_percent > 90:
            health_status = 'warning'
            alerts.append(f"High CPU usage: {cpu_percent}%")
        
        if memory_percent > 90:
            health_status = 'warning'  
            alerts.append(f"High memory usage: {memory_percent}%")
        
        if len(stale_tasks) > 0:
            health_status = 'warning'
            alerts.append(f"{len(stale_tasks)} stale tasks detected")
        
        if len(active_tasks) > 100:
            health_status = 'warning'
            alerts.append(f"High task load: {len(active_tasks)} active tasks")
        
        # Worker health check
        from celery import current_app
        inspect = current_app.control.inspect()
        active_workers = inspect.active()
        
        worker_count = len(active_workers) if active_workers else 0
        if worker_count == 0:
            health_status = 'critical'
            alerts.append("No active workers detected")
        
        heartbeat = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': health_status,
            'alerts': alerts,
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'active_tasks': len(active_tasks),
                'stale_tasks': len(stale_tasks),
                'active_workers': worker_count
            },
            'stale_tasks': stale_tasks[:5]  # Include first 5 stale tasks
        }
        
        # Store heartbeat
        redis_client.set('system_heartbeat', json.dumps(heartbeat), ex=30)  # Expire in 30 seconds
        
        # Publish heartbeat event
        publish_event('heartbeat', heartbeat)
        
        # Log warnings and critical issues
        if health_status == 'warning':
            logger.warning(f"System health warning: {', '.join(alerts)}")
        elif health_status == 'critical':
            logger.error(f"System health critical: {', '.join(alerts)}")
        
        return heartbeat
        
    except Exception as exc:
        logger.error(f"Heartbeat check failed: {exc}")
        critical_heartbeat = {
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'critical',
            'error': str(exc),
            'alerts': ['Heartbeat check failed']
        }
        
        publish_event('heartbeat', critical_heartbeat)
        return critical_heartbeat


@celery_app.task(bind=True)
def task_orchestrator(self, orchestration_request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrate task assignment to available agents
    
    Args:
        orchestration_request: Dictionary containing orchestration parameters
            - tasks: List of tasks to orchestrate
            - agent_preferences: Preferred agent types
            - priority: Overall priority level
            - batch_size: Number of tasks to process simultaneously
    
    Returns:
        Dictionary with orchestration results
    """
    try:
        tasks = orchestration_request.get('tasks', [])
        agent_preferences = orchestration_request.get('agent_preferences', ['gpt-4'])
        priority = orchestration_request.get('priority', 'normal')
        batch_size = orchestration_request.get('batch_size', 5)
        
        logger.info(f"Orchestrating {len(tasks)} tasks with priority {priority}")
        
        # Get system load for intelligent scheduling
        active_tasks_count = len(redis_client.keys("active_tasks:*"))
        cpu_percent = psutil.cpu_percent()
        
        # Adjust batch size based on system load
        if cpu_percent > 80 or active_tasks_count > 50:
            batch_size = max(1, batch_size // 2)
            logger.info(f"Reduced batch size to {batch_size} due to high system load")
        
        # Agent load balancing
        agent_loads = {}
        for agent_type in agent_preferences:
            agent_tasks = redis_client.keys(f"active_tasks:*")
            load = 0
            for task_key in agent_tasks:
                if redis_client.hget(task_key, 'agent_type') == agent_type:
                    load += 1
            agent_loads[agent_type] = load
        
        # Sort agents by load (prefer less loaded agents)
        sorted_agents = sorted(agent_loads.keys(), key=lambda x: agent_loads[x])
        
        scheduled_tasks = []
        failed_to_schedule = []
        
        for i, task in enumerate(tasks):
            try:
                # Select least loaded agent
                selected_agent = sorted_agents[i % len(sorted_agents)]
                
                # Enhance task with orchestration metadata
                enhanced_task = {
                    **task,
                    'agent_type': selected_agent,
                    'orchestration_id': str(uuid.uuid4()),
                    'batch_id': orchestration_request.get('batch_id', str(uuid.uuid4())),
                    'priority': priority,
                    'scheduled_at': datetime.utcnow().isoformat()
                }
                
                # Queue the task
                if priority == 'urgent':
                    result = process_agent_task.apply_async(
                        args=[enhanced_task],
                        queue='high_priority',
                        priority=10
                    )
                elif priority == 'high':
                    result = process_agent_task.apply_async(
                        args=[enhanced_task],
                        queue='high_priority',
                        priority=7
                    )
                else:
                    result = process_agent_task.apply_async(
                        args=[enhanced_task],
                        queue='normal',
                        priority=5
                    )
                
                scheduled_tasks.append({
                    'task_id': enhanced_task.get('task_id'),
                    'agent_type': selected_agent,
                    'celery_task_id': result.task_id,
                    'queue': 'high_priority' if priority in ['urgent', 'high'] else 'normal'
                })
                
                # Update agent load tracking
                agent_loads[selected_agent] += 1
                sorted_agents = sorted(agent_loads.keys(), key=lambda x: agent_loads[x])
                
            except Exception as exc:
                logger.error(f"Failed to schedule task {task.get('task_id', 'unknown')}: {exc}")
                failed_to_schedule.append({
                    'task': task,
                    'error': str(exc)
                })
        
        orchestration_result = {
            'orchestration_id': str(uuid.uuid4()),
            'timestamp': datetime.utcnow().isoformat(),
            'total_tasks': len(tasks),
            'scheduled_count': len(scheduled_tasks),
            'failed_count': len(failed_to_schedule),
            'agent_distribution': {agent: len([t for t in scheduled_tasks if t['agent_type'] == agent]) 
                                  for agent in agent_preferences},
            'system_load': {
                'cpu_percent': cpu_percent,
                'active_tasks': active_tasks_count,
                'adjusted_batch_size': batch_size
            },
            'scheduled_tasks': scheduled_tasks,
            'failed_tasks': failed_to_schedule
        }
        
        # Store orchestration result
        redis_client.hset(f"orchestrations:{orchestration_result['orchestration_id']}", 
                         mapping=json.dumps(orchestration_result))
        redis_client.expire(f"orchestrations:{orchestration_result['orchestration_id']}", 86400)
        
        # Publish orchestration event
        publish_event('tasks_orchestrated', orchestration_result)
        
        logger.info(f"Orchestration completed: {len(scheduled_tasks)}/{len(tasks)} tasks scheduled")
        
        return orchestration_result
        
    except Exception as exc:
        logger.error(f"Task orchestration failed: {exc}")
        return {
            'error': str(exc),
            'timestamp': datetime.utcnow().isoformat(),
            'total_tasks': len(orchestration_request.get('tasks', [])),
            'scheduled_count': 0,
            'failed_count': len(orchestration_request.get('tasks', []))
        }


@celery_app.task(bind=True)
def cleanup_completed(self) -> Dict[str, Any]:
    """
    Archive completed tasks and clean up old logs
    
    Returns:
        Dictionary with cleanup statistics
    """
    try:
        # Find old completed tasks (older than 24 hours)
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        completed_keys = redis_client.keys("completed_tasks:*")
        failed_keys = redis_client.keys("task_failures:*")
        orchestration_keys = redis_client.keys("orchestrations:*")
        
        archived_completed = 0
        archived_failed = 0
        archived_orchestrations = 0
        
        # Archive old completed tasks
        for key in completed_keys:
            completed_at_str = redis_client.hget(key, 'completed_at')
            if completed_at_str:
                completed_at = datetime.fromisoformat(completed_at_str.replace('Z', '+00:00'))
                if completed_at < cutoff_time:
                    # Move to archive (could be database in production)
                    task_data = redis_client.hgetall(key)
                    redis_client.hset(f"archived_{key}", mapping=task_data)
                    redis_client.expire(f"archived_{key}", 604800)  # Keep archived for 7 days
                    redis_client.delete(key)
                    archived_completed += 1
        
        # Archive old failed tasks
        for key in failed_keys:
            failed_at_str = redis_client.hget(key, 'failed_at')
            if failed_at_str:
                failed_at = datetime.fromisoformat(failed_at_str.replace('Z', '+00:00'))
                if failed_at < cutoff_time:
                    task_data = redis_client.hgetall(key)
                    redis_client.hset(f"archived_{key}", mapping=task_data)
                    redis_client.expire(f"archived_{key}", 604800)  # Keep archived for 7 days
                    redis_client.delete(key)
                    archived_failed += 1
        
        # Clean up old orchestrations (older than 1 hour)
        orchestration_cutoff = datetime.utcnow() - timedelta(hours=1)
        for key in orchestration_keys:
            # Get orchestration timestamp from stored data
            orchestration_data = redis_client.hget(key, 'data')
            if orchestration_data:
                try:
                    data = json.loads(orchestration_data)
                    timestamp = datetime.fromisoformat(data['timestamp'].replace('Z', '+00:00'))
                    if timestamp < orchestration_cutoff:
                        redis_client.delete(key)
                        archived_orchestrations += 1
                except (json.JSONDecodeError, KeyError):
                    # Clean up malformed orchestration data
                    redis_client.delete(key)
                    archived_orchestrations += 1
        
        # Clean up metrics history (keep only last 7 days)
        week_ago = int((datetime.utcnow() - timedelta(days=7)).timestamp())
        metrics_removed = redis_client.zremrangebyscore('metrics_history', 0, week_ago)
        
        # Clean up stale active tasks (running > 2 hours, likely dead workers)
        stale_cutoff = datetime.utcnow() - timedelta(hours=2)
        active_keys = redis_client.keys("active_tasks:*")
        stale_cleaned = 0
        
        for key in active_keys:
            started_at_str = redis_client.hget(key, 'started_at')
            if started_at_str:
                started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                if started_at < stale_cutoff:
                    # Move to failed tasks
                    task_data = redis_client.hgetall(key)
                    task_id = key.split(':')[1]
                    redis_client.hset(f"task_failures:{task_id}", mapping={
                        **task_data,
                        'error': 'Task presumed failed due to worker timeout',
                        'failed_at': datetime.utcnow().isoformat(),
                        'cleanup_reason': 'stale_task_cleanup'
                    })
                    redis_client.expire(f"task_failures:{task_id}", 86400)
                    redis_client.delete(key)
                    stale_cleaned += 1
        
        cleanup_stats = {
            'timestamp': datetime.utcnow().isoformat(),
            'archived_completed': archived_completed,
            'archived_failed': archived_failed,
            'archived_orchestrations': archived_orchestrations,
            'metrics_cleaned': metrics_removed,
            'stale_tasks_cleaned': stale_cleaned,
            'cutoff_time': cutoff_time.isoformat()
        }
        
        # Store cleanup stats
        redis_client.zadd('cleanup_history', {
            json.dumps(cleanup_stats): int(datetime.utcnow().timestamp())
        })
        
        # Keep only last 30 cleanup records
        cleanup_records = redis_client.zcard('cleanup_history')
        if cleanup_records > 30:
            redis_client.zremrangebyrank('cleanup_history', 0, cleanup_records - 31)
        
        # Publish cleanup event
        publish_event('cleanup_completed', cleanup_stats)
        
        logger.info(f"Cleanup completed: {archived_completed} completed, {archived_failed} failed, "
                   f"{stale_cleaned} stale tasks cleaned")
        
        return cleanup_stats
        
    except Exception as exc:
        logger.error(f"Cleanup task failed: {exc}")
        return {
            'error': str(exc),
            'timestamp': datetime.utcnow().isoformat(),
            'archived_completed': 0,
            'archived_failed': 0
        }


# Enhanced system control tasks
@celery_app.task(bind=True)
def broadcast_pause_all(self):
    """Enhanced broadcast pause command with comprehensive logging"""
    try:
        logger.info("Broadcasting PAUSE ALL command to all agents")
        
        # Set global pause flag in Redis
        redis_client.set('system_paused', 'true', ex=3600)  # Expire in 1 hour for safety
        
        # Get active tasks for notification
        active_tasks = redis_client.keys("active_tasks:*")
        
        # Publish pause event
        publish_event('system_paused', {
            'timestamp': datetime.utcnow().isoformat(),
            'active_tasks_count': len(active_tasks),
            'reason': 'manual_pause'
        })
        
        result = {
            'status': 'all_agents_paused',
            'timestamp': datetime.utcnow().isoformat(),
            'active_tasks_affected': len(active_tasks)
        }
        
        logger.info(f"System paused, {len(active_tasks)} active tasks affected")
        return result
        
    except Exception as exc:
        logger.error(f"Failed to pause system: {exc}")
        return {'error': str(exc), 'status': 'pause_failed'}


@celery_app.task(bind=True)
def broadcast_resume_all(self):
    """Enhanced broadcast resume command with comprehensive logging"""
    try:
        logger.info("Broadcasting RESUME ALL command to all agents")
        
        # Remove global pause flag
        redis_client.delete('system_paused')
        
        # Get system status for reporting
        active_tasks = redis_client.keys("active_tasks:*")
        
        # Publish resume event
        publish_event('system_resumed', {
            'timestamp': datetime.utcnow().isoformat(),
            'active_tasks_count': len(active_tasks),
            'reason': 'manual_resume'
        })
        
        result = {
            'status': 'all_agents_resumed',
            'timestamp': datetime.utcnow().isoformat(),
            'active_tasks_count': len(active_tasks)
        }
        
        logger.info("System resumed successfully")
        return result
        
    except Exception as exc:
        logger.error(f"Failed to resume system: {exc}")
        return {'error': str(exc), 'status': 'resume_failed'}


@celery_app.task(bind=True)
def adjust_throttle(self, rate: float):
    """Enhanced throttle adjustment with validation and logging"""
    try:
        # Validate rate
        if not 0.1 <= rate <= 2.0:
            raise ValueError(f"Throttle rate must be between 0.1 and 2.0, got {rate}")
        
        logger.info(f"Adjusting throttle rate to {rate}x")
        
        # Store throttle rate in Redis
        redis_client.set('system_throttle_rate', str(rate))
        
        # Get system impact assessment
        active_tasks = redis_client.keys("active_tasks:*")
        
        # Publish throttle event
        publish_event('throttle_adjusted', {
            'timestamp': datetime.utcnow().isoformat(),
            'new_rate': rate,
            'active_tasks_affected': len(active_tasks)
        })
        
        result = {
            'throttle_rate': rate,
            'timestamp': datetime.utcnow().isoformat(),
            'active_tasks_affected': len(active_tasks),
            'status': 'throttle_applied'
        }
        
        logger.info(f"Throttle rate adjusted to {rate}, affecting {len(active_tasks)} active tasks")
        return result
        
    except Exception as exc:
        logger.error(f"Failed to adjust throttle: {exc}")
        return {'error': str(exc), 'throttle_rate': rate, 'status': 'throttle_failed'}