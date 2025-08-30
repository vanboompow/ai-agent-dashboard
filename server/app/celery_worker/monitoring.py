"""
Monitoring System for Worker Health and Metrics

This module provides comprehensive monitoring capabilities for Celery workers,
task queues, system health, and performance metrics with alerting and 
dead letter queue handling.
"""

import time
import json
import redis
import logging
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
from celery import Celery
from celery.events.state import State
from celery.events import EventReceiver
from .events import EventPublisher, SystemEventManager, publish_alert
import statistics

logger = logging.getLogger(__name__)


@dataclass
class WorkerHealth:
    """Worker health status information"""
    worker_id: str
    status: str  # online, offline, warning, critical
    last_heartbeat: str
    active_tasks: int
    processed_tasks: int
    failed_tasks: int
    avg_task_time: float
    memory_usage_mb: float
    cpu_usage_percent: float
    load_average: List[float]
    uptime_seconds: float
    alerts: List[str]


@dataclass
class QueueHealth:
    """Queue health and depth information"""
    queue_name: str
    depth: int
    processing_rate: float  # tasks per minute
    avg_wait_time: float
    oldest_task_age: float
    worker_count: int
    alerts: List[str]


@dataclass
class SystemHealth:
    """Overall system health summary"""
    status: str  # healthy, warning, critical
    timestamp: str
    total_workers: int
    active_workers: int
    total_tasks_active: int
    total_tasks_processed: int
    total_tasks_failed: int
    system_load_avg: List[float]
    memory_usage_percent: float
    cpu_usage_percent: float
    disk_usage_percent: float
    redis_status: str
    alerts: List[str]


class WorkerMonitor:
    """
    Monitors individual worker health and performance
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize worker monitor
        
        Args:
            redis_client: Redis client for storing monitoring data
        """
        self.redis = redis_client
        self.worker_stats = defaultdict(dict)
        self.last_check = datetime.utcnow()
        self.alert_cooldown = defaultdict(float)  # Prevent alert spam
        
    def check_worker_health(self, worker_id: str, worker_info: Dict[str, Any]) -> WorkerHealth:
        """
        Check health of a specific worker
        
        Args:
            worker_id: Unique worker identifier
            worker_info: Worker information from Celery inspect
            
        Returns:
            WorkerHealth object with current status
        """
        now = datetime.utcnow()
        alerts = []
        
        # Extract worker statistics
        stats = worker_info.get('stats', {})
        pool = worker_info.get('pool', {})
        
        active_tasks = len(worker_info.get('active', []))
        total_processed = stats.get('total', 0)
        
        # Calculate performance metrics
        if worker_id in self.worker_stats:
            prev_stats = self.worker_stats[worker_id]
            time_delta = (now - prev_stats.get('last_update', now)).total_seconds()
            
            if time_delta > 0:
                # Calculate processing rate
                tasks_delta = total_processed - prev_stats.get('total_processed', 0)
                processing_rate = tasks_delta / (time_delta / 60.0)  # tasks per minute
            else:
                processing_rate = 0.0
        else:
            processing_rate = 0.0
        
        # Get system metrics for this worker
        try:
            # These would ideally come from the worker itself via custom commands
            memory_usage = psutil.virtual_memory().used / (1024**2)  # MB
            cpu_usage = psutil.cpu_percent()
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        except Exception:
            memory_usage = 0
            cpu_usage = 0
            load_avg = [0, 0, 0]
        
        # Determine worker status and alerts
        status = "online"
        
        # Check for high resource usage
        if cpu_usage > 90:
            status = "warning"
            alerts.append(f"High CPU usage: {cpu_usage:.1f}%")
        
        if memory_usage > 2000:  # 2GB
            status = "warning"
            alerts.append(f"High memory usage: {memory_usage:.0f}MB")
        
        # Check for stuck tasks
        if active_tasks > 10:
            status = "warning"
            alerts.append(f"Many active tasks: {active_tasks}")
        
        # Check for processing issues
        if processing_rate < 0.1 and active_tasks > 0:  # Less than 0.1 tasks/min with active tasks
            status = "warning" if status != "critical" else "critical"
            alerts.append("Low processing rate with active tasks")
        
        # Update worker statistics
        self.worker_stats[worker_id] = {
            'last_update': now,
            'total_processed': total_processed,
            'processing_rate': processing_rate,
            'status': status
        }
        
        # Calculate average task time (estimated)
        avg_task_time = 60.0 / max(processing_rate, 0.1) if processing_rate > 0 else 0.0
        
        health = WorkerHealth(
            worker_id=worker_id,
            status=status,
            last_heartbeat=now.isoformat(),
            active_tasks=active_tasks,
            processed_tasks=total_processed,
            failed_tasks=stats.get('failed', 0),
            avg_task_time=avg_task_time,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            load_average=list(load_avg),
            uptime_seconds=stats.get('clock', 0),
            alerts=alerts
        )
        
        # Store worker health in Redis
        self.redis.hset(
            f"worker_health:{worker_id}",
            mapping={
                "status": status,
                "last_check": now.isoformat(),
                "active_tasks": active_tasks,
                "alerts": json.dumps(alerts),
                "health_data": json.dumps(asdict(health))
            }
        )
        self.redis.expire(f"worker_health:{worker_id}", 300)  # 5 minutes
        
        # Publish alerts if needed
        if alerts and status in ["warning", "critical"]:
            self._publish_worker_alerts(worker_id, status, alerts)
        
        return health
    
    def _publish_worker_alerts(self, worker_id: str, status: str, alerts: List[str]):
        """Publish worker alerts with cooldown to prevent spam"""
        current_time = time.time()
        cooldown_key = f"{worker_id}_{status}"
        
        # Check cooldown (5 minutes for same alert type)
        if current_time - self.alert_cooldown[cooldown_key] > 300:
            SystemEventManager.system_alert(
                level=status,
                message=f"Worker {worker_id} health {status}",
                details={
                    "worker_id": worker_id,
                    "alerts": alerts,
                    "status": status
                }
            )
            self.alert_cooldown[cooldown_key] = current_time
    
    def get_all_worker_health(self) -> List[WorkerHealth]:
        """Get health status for all workers"""
        worker_keys = self.redis.keys("worker_health:*")
        workers = []
        
        for key in worker_keys:
            try:
                health_data = self.redis.hget(key, "health_data")
                if health_data:
                    health_dict = json.loads(health_data)
                    workers.append(WorkerHealth(**health_dict))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Failed to parse worker health data from {key}: {e}")
        
        return workers


class QueueMonitor:
    """
    Monitors queue depth, processing rates, and queue health
    """
    
    def __init__(self, redis_client: redis.Redis, celery_app: Celery):
        """
        Initialize queue monitor
        
        Args:
            redis_client: Redis client for storing data
            celery_app: Celery application instance
        """
        self.redis = redis_client
        self.celery_app = celery_app
        self.queue_history = defaultdict(lambda: deque(maxlen=100))  # Store last 100 measurements
        
    def check_queue_health(self, queue_name: str) -> QueueHealth:
        """
        Check health of a specific queue
        
        Args:
            queue_name: Name of the queue to check
            
        Returns:
            QueueHealth object with current status
        """
        alerts = []
        now = datetime.utcnow()
        
        # Get queue inspection data
        inspect = self.celery_app.control.inspect()
        
        # Get queue lengths (this is Celery/broker specific)
        try:
            # For Redis broker, we can directly check queue length
            queue_key = f"celery:{queue_name}"  # Default Redis key format
            depth = self.redis.llen(queue_key)
        except Exception as e:
            logger.warning(f"Failed to get queue depth for {queue_name}: {e}")
            depth = 0
        
        # Get active tasks to estimate processing
        active_tasks = inspect.active()
        reserved_tasks = inspect.reserved()
        
        # Count tasks in this queue
        active_in_queue = 0
        reserved_in_queue = 0
        
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    if task.get('delivery_info', {}).get('routing_key') == queue_name:
                        active_in_queue += 1
        
        if reserved_tasks:
            for worker, tasks in reserved_tasks.items():
                for task in tasks:
                    if task.get('delivery_info', {}).get('routing_key') == queue_name:
                        reserved_in_queue += 1
        
        # Calculate processing rate
        queue_hist = self.queue_history[queue_name]
        
        if len(queue_hist) > 1:
            # Calculate rate based on depth changes
            recent_depths = [entry['depth'] for entry in list(queue_hist)[-10:]]
            if len(recent_depths) > 1:
                # Estimate processing rate (tasks processed per minute)
                time_window = 10  # Last 10 measurements
                depth_change = recent_depths[0] - recent_depths[-1]  # Decrease in depth = processed
                processing_rate = max(0, depth_change / (time_window / 6))  # Assume 10s intervals, convert to per minute
            else:
                processing_rate = 0.0
        else:
            processing_rate = 0.0
        
        # Estimate average wait time
        if processing_rate > 0:
            avg_wait_time = depth / (processing_rate / 60.0)  # minutes
        else:
            avg_wait_time = 0.0
        
        # Get oldest task age (estimated)
        oldest_task_age = avg_wait_time  # Rough estimate
        
        # Count workers assigned to this queue
        worker_count = len([w for w in active_tasks.keys() if active_tasks[w]]) if active_tasks else 0
        
        # Generate alerts based on queue health
        thresholds = {
            'high_priority': {'depth_warning': 50, 'depth_critical': 100},
            'normal': {'depth_warning': 100, 'depth_critical': 200},
            'background': {'depth_warning': 200, 'depth_critical': 500}
        }
        
        threshold = thresholds.get(queue_name, thresholds['normal'])
        
        if depth > threshold['depth_critical']:
            alerts.append(f"Critical queue depth: {depth}")
        elif depth > threshold['depth_warning']:
            alerts.append(f"High queue depth: {depth}")
        
        if avg_wait_time > 600:  # 10 minutes
            alerts.append(f"Long wait time: {avg_wait_time:.1f} minutes")
        
        if worker_count == 0 and depth > 0:
            alerts.append("No workers available for non-empty queue")
        
        # Store queue metrics
        queue_entry = {
            'timestamp': now.timestamp(),
            'depth': depth,
            'active_tasks': active_in_queue,
            'reserved_tasks': reserved_in_queue,
            'processing_rate': processing_rate,
            'wait_time': avg_wait_time
        }
        queue_hist.append(queue_entry)
        
        # Store in Redis
        self.redis.hset(
            f"queue_health:{queue_name}",
            mapping={
                "depth": depth,
                "processing_rate": processing_rate,
                "avg_wait_time": avg_wait_time,
                "worker_count": worker_count,
                "alerts": json.dumps(alerts),
                "last_check": now.isoformat()
            }
        )
        self.redis.expire(f"queue_health:{queue_name}", 300)
        
        # Publish queue alerts
        if alerts:
            SystemEventManager.queue_depth_warning(queue_name, depth, threshold['depth_warning'])
        
        return QueueHealth(
            queue_name=queue_name,
            depth=depth,
            processing_rate=processing_rate,
            avg_wait_time=avg_wait_time,
            oldest_task_age=oldest_task_age,
            worker_count=worker_count,
            alerts=alerts
        )
    
    def get_all_queue_health(self) -> List[QueueHealth]:
        """Get health status for all monitored queues"""
        queue_names = ['high_priority', 'normal', 'background']
        return [self.check_queue_health(queue) for queue in queue_names]


class DeadLetterQueueHandler:
    """
    Handles dead letter queue processing and retry logic
    """
    
    def __init__(self, redis_client: redis.Redis):
        """
        Initialize dead letter queue handler
        
        Args:
            redis_client: Redis client for DLQ storage
        """
        self.redis = redis_client
        
    def add_to_dlq(self, task_id: str, task_data: Dict[str, Any], 
                   error: str, retry_count: int):
        """
        Add failed task to dead letter queue
        
        Args:
            task_id: Failed task ID
            task_data: Original task data
            error: Error message
            retry_count: Number of retries attempted
        """
        dlq_entry = {
            'task_id': task_id,
            'task_data': json.dumps(task_data),
            'error': error,
            'retry_count': retry_count,
            'failed_at': datetime.utcnow().isoformat(),
            'status': 'dead'
        }
        
        # Add to DLQ with score as timestamp for ordering
        self.redis.zadd('dead_letter_queue', {
            json.dumps(dlq_entry): int(time.time())
        })
        
        # Publish DLQ event
        publish_alert(
            "warning",
            f"Task {task_id} moved to dead letter queue",
            {
                "task_id": task_id,
                "error": error,
                "retry_count": retry_count
            }
        )
        
        logger.warning(f"Task {task_id} added to DLQ after {retry_count} retries: {error}")
    
    def process_dlq(self, max_age_hours: int = 24) -> Dict[str, Any]:
        """
        Process dead letter queue, retry eligible tasks
        
        Args:
            max_age_hours: Maximum age of tasks to consider for retry
            
        Returns:
            Dictionary with processing results
        """
        cutoff_time = int(time.time()) - (max_age_hours * 3600)
        
        # Get DLQ entries within time window
        dlq_entries = self.redis.zrangebyscore('dead_letter_queue', cutoff_time, '+inf', withscores=True)
        
        requeued = 0
        permanently_failed = 0
        
        for entry_json, timestamp in dlq_entries:
            try:
                entry = json.loads(entry_json)
                
                # Decide whether to retry based on error type and retry count
                if self._should_retry_task(entry):
                    # Remove from DLQ and requeue
                    self.redis.zrem('dead_letter_queue', entry_json)
                    self._requeue_task(entry)
                    requeued += 1
                elif entry['retry_count'] > 5:  # Max retries exceeded
                    # Move to permanent failure
                    self._mark_permanently_failed(entry)
                    self.redis.zrem('dead_letter_queue', entry_json)
                    permanently_failed += 1
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.error(f"Failed to process DLQ entry: {e}")
        
        results = {
            'processed_entries': len(dlq_entries),
            'requeued': requeued,
            'permanently_failed': permanently_failed,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if requeued > 0 or permanently_failed > 0:
            publish_alert(
                "info",
                f"DLQ processed: {requeued} requeued, {permanently_failed} permanently failed",
                results
            )
        
        return results
    
    def _should_retry_task(self, dlq_entry: Dict[str, Any]) -> bool:
        """Determine if a DLQ task should be retried"""
        error = dlq_entry['error'].lower()
        retry_count = dlq_entry['retry_count']
        
        # Don't retry if too many attempts
        if retry_count > 3:
            return False
        
        # Retry for transient errors
        transient_errors = [
            'timeout', 'connection', 'network', 'rate limit', 
            'overload', 'busy', 'unavailable'
        ]
        
        return any(keyword in error for keyword in transient_errors)
    
    def _requeue_task(self, dlq_entry: Dict[str, Any]):
        """Requeue a task from DLQ"""
        try:
            task_data = json.loads(dlq_entry['task_data'])
            
            # Add retry metadata
            task_data['_retry_info'] = {
                'retry_count': dlq_entry['retry_count'] + 1,
                'previous_error': dlq_entry['error'],
                'dlq_requeue_time': datetime.utcnow().isoformat()
            }
            
            # Requeue with lower priority
            from .tasks import process_agent_task
            process_agent_task.apply_async(
                args=[task_data],
                queue='normal',
                priority=2  # Lower priority for retries
            )
            
            logger.info(f"Requeued task {dlq_entry['task_id']} from DLQ")
            
        except Exception as e:
            logger.error(f"Failed to requeue task {dlq_entry['task_id']}: {e}")
    
    def _mark_permanently_failed(self, dlq_entry: Dict[str, Any]):
        """Mark task as permanently failed"""
        permanent_failure = {
            **dlq_entry,
            'status': 'permanently_failed',
            'marked_permanent_at': datetime.utcnow().isoformat()
        }
        
        # Store in permanent failures set
        self.redis.hset(
            f"permanent_failures:{dlq_entry['task_id']}",
            mapping=permanent_failure
        )
        self.redis.expire(f"permanent_failures:{dlq_entry['task_id']}", 604800)  # 7 days
        
    def get_dlq_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics"""
        dlq_count = self.redis.zcard('dead_letter_queue')
        permanent_failures = len(self.redis.keys('permanent_failures:*'))
        
        # Get age distribution
        now = int(time.time())
        last_hour = self.redis.zcount('dead_letter_queue', now - 3600, '+inf')
        last_day = self.redis.zcount('dead_letter_queue', now - 86400, '+inf')
        
        return {
            'total_dlq_entries': dlq_count,
            'permanent_failures': permanent_failures,
            'entries_last_hour': last_hour,
            'entries_last_day': last_day,
            'timestamp': datetime.utcnow().isoformat()
        }


class SystemHealthMonitor:
    """
    Overall system health monitoring and alerting
    """
    
    def __init__(self, redis_client: redis.Redis, celery_app: Celery):
        """
        Initialize system health monitor
        
        Args:
            redis_client: Redis client
            celery_app: Celery application
        """
        self.redis = redis_client
        self.celery_app = celery_app
        self.worker_monitor = WorkerMonitor(redis_client)
        self.queue_monitor = QueueMonitor(redis_client, celery_app)
        self.dlq_handler = DeadLetterQueueHandler(redis_client)
        
    def get_system_health(self) -> SystemHealth:
        """Get comprehensive system health status"""
        now = datetime.utcnow()
        alerts = []
        
        # Get worker health
        worker_health = self.worker_monitor.get_all_worker_health()
        active_workers = len([w for w in worker_health if w.status == "online"])
        total_workers = len(worker_health)
        
        # Get queue health
        queue_health = self.queue_monitor.get_all_queue_health()
        
        # Get system metrics
        try:
            memory = psutil.virtual_memory()
            cpu_percent = psutil.cpu_percent()
            disk = psutil.disk_usage('/')
            load_avg = psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        except Exception:
            memory = type('obj', (object,), {'percent': 0})
            cpu_percent = 0
            disk = type('obj', (object,), {'percent': 0})
            load_avg = [0, 0, 0]
        
        # Check Redis status
        try:
            self.redis.ping()
            redis_status = "connected"
        except Exception:
            redis_status = "disconnected"
            alerts.append("Redis connection failed")
        
        # Get task statistics
        active_tasks = self.redis.keys("active_tasks:*")
        completed_tasks = self.redis.keys("completed_tasks:*")
        failed_tasks = self.redis.keys("task_failures:*")
        
        total_active = len(active_tasks)
        total_processed = len(completed_tasks)
        total_failed = len(failed_tasks)
        
        # Determine overall system status
        status = "healthy"
        
        # Check critical conditions
        if redis_status == "disconnected":
            status = "critical"
            alerts.append("Redis connection failed")
        
        if active_workers == 0:
            status = "critical"
            alerts.append("No active workers")
        
        if cpu_percent > 95:
            status = "critical" if status != "critical" else "critical"
            alerts.append(f"Critical CPU usage: {cpu_percent}%")
        elif cpu_percent > 80:
            status = "warning" if status == "healthy" else status
            alerts.append(f"High CPU usage: {cpu_percent}%")
        
        if memory.percent > 95:
            status = "critical" if status != "critical" else "critical"
            alerts.append(f"Critical memory usage: {memory.percent}%")
        elif memory.percent > 80:
            status = "warning" if status == "healthy" else status
            alerts.append(f"High memory usage: {memory.percent}%")
        
        if disk.percent > 90:
            status = "warning" if status == "healthy" else status
            alerts.append(f"High disk usage: {disk.percent}%")
        
        # Check queue health
        for queue in queue_health:
            if queue.alerts:
                status = "warning" if status == "healthy" else status
                alerts.extend([f"Queue {queue.queue_name}: {alert}" for alert in queue.alerts])
        
        # Check worker health
        critical_workers = [w for w in worker_health if w.status == "critical"]
        warning_workers = [w for w in worker_health if w.status == "warning"]
        
        if critical_workers:
            status = "critical" if status != "critical" else "critical"
            alerts.append(f"{len(critical_workers)} workers in critical state")
        
        if warning_workers and status == "healthy":
            status = "warning"
            alerts.append(f"{len(warning_workers)} workers in warning state")
        
        health = SystemHealth(
            status=status,
            timestamp=now.isoformat(),
            total_workers=total_workers,
            active_workers=active_workers,
            total_tasks_active=total_active,
            total_tasks_processed=total_processed,
            total_tasks_failed=total_failed,
            system_load_avg=list(load_avg),
            memory_usage_percent=memory.percent,
            cpu_usage_percent=cpu_percent,
            disk_usage_percent=disk.percent,
            redis_status=redis_status,
            alerts=alerts
        )
        
        # Store system health
        self.redis.hset(
            "system_health",
            mapping={
                "status": status,
                "timestamp": now.isoformat(),
                "health_data": json.dumps(asdict(health))
            }
        )
        self.redis.expire("system_health", 300)
        
        # Publish health update
        EventPublisher.publish_event(
            "system_health_update",
            asdict(health),
            priority=7 if status in ["warning", "critical"] else 4
        )
        
        # Publish critical alerts
        if status == "critical":
            SystemEventManager.system_alert(
                "critical",
                "System health critical",
                {"alerts": alerts, "status": status}
            )
        
        return health
    
    def start_monitoring(self, interval: int = 30):
        """
        Start continuous monitoring
        
        Args:
            interval: Monitoring interval in seconds
        """
        def monitoring_loop():
            while True:
                try:
                    self.get_system_health()
                    self.dlq_handler.process_dlq()
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"Monitoring error: {e}")
                    time.sleep(interval)
        
        thread = threading.Thread(target=monitoring_loop, daemon=True)
        thread.start()
        logger.info(f"Started system monitoring with {interval}s interval")


# Convenience function to initialize monitoring
def initialize_monitoring(redis_url: str = "redis://localhost:6379/0", 
                         celery_app: Optional[Celery] = None) -> SystemHealthMonitor:
    """
    Initialize monitoring system
    
    Args:
        redis_url: Redis connection URL
        celery_app: Celery application instance
        
    Returns:
        SystemHealthMonitor instance
    """
    redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
    
    if celery_app is None:
        from .celery_app import celery_app
    
    monitor = SystemHealthMonitor(redis_client, celery_app)
    return monitor


if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(level=logging.INFO)
    
    # Initialize monitoring
    monitor = initialize_monitoring()
    
    # Get current health
    health = monitor.get_system_health()
    print(f"System status: {health.status}")
    print(f"Active workers: {health.active_workers}/{health.total_workers}")
    print(f"Active tasks: {health.total_tasks_active}")
    print(f"Alerts: {health.alerts}")
    
    # Check individual components
    queues = monitor.queue_monitor.get_all_queue_health()
    for queue in queues:
        print(f"Queue {queue.queue_name}: depth={queue.depth}, rate={queue.processing_rate:.1f}/min")
    
    # DLQ stats
    dlq_stats = monitor.dlq_handler.get_dlq_stats()
    print(f"DLQ entries: {dlq_stats['total_dlq_entries']}")
    
    print("Monitoring test completed!")