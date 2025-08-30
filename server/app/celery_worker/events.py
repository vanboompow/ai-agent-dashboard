"""
Event Publishing System for Real-time Updates

This module handles publishing real-time events to Redis pub/sub channels
for consumption by the dashboard frontend via Server-Sent Events (SSE).
"""

import json
import redis
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
import threading
from collections import defaultdict, deque

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Supported event types for real-time updates"""
    AGENT_STATUS = "agent_status"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_RETRY = "task_retry"
    METRICS_UPDATE = "metrics_update"
    SYSTEM_ALERT = "system_alert"
    HEARTBEAT = "heartbeat"
    SYSTEM_PAUSED = "system_paused"
    SYSTEM_RESUMED = "system_resumed"
    THROTTLE_ADJUSTED = "throttle_adjusted"
    TASKS_ORCHESTRATED = "tasks_orchestrated"
    CLEANUP_COMPLETED = "cleanup_completed"
    WORKER_ONLINE = "worker_online"
    WORKER_OFFLINE = "worker_offline"
    QUEUE_DEPTH_ALERT = "queue_depth_alert"


@dataclass
class Event:
    """Standard event structure for consistent publishing"""
    type: str
    data: Dict[str, Any]
    timestamp: str
    source: str = "celery_worker"
    priority: int = 5  # 1-10 scale, 10 = highest
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert event to JSON string"""
        return json.dumps(self.to_dict())


class EventBatcher:
    """
    Batches events for performance optimization while maintaining real-time responsiveness
    """
    
    def __init__(self, batch_size: int = 10, batch_timeout: float = 1.0):
        """
        Initialize event batcher
        
        Args:
            batch_size: Maximum events per batch
            batch_timeout: Maximum time to wait before flushing batch (seconds)
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.pending_events = defaultdict(list)  # type -> events
        self.last_flush = defaultdict(float)  # type -> timestamp
        self.lock = threading.Lock()
        
        # Start background flush thread
        self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self.flush_thread.start()
    
    def add_event(self, event: Event, force_immediate: bool = False) -> bool:
        """
        Add event to batch or send immediately
        
        Args:
            event: Event to add
            force_immediate: Force immediate sending (bypass batching)
            
        Returns:
            True if event was sent immediately, False if batched
        """
        with self.lock:
            event_type = event.type
            current_time = time.time()
            
            # High priority events are sent immediately
            if event.priority >= 8 or force_immediate:
                self._flush_events([event])
                return True
            
            # Add to batch
            self.pending_events[event_type].append(event)
            
            # Check if batch is full or timeout reached
            if (len(self.pending_events[event_type]) >= self.batch_size or
                current_time - self.last_flush[event_type] >= self.batch_timeout):
                
                events_to_flush = self.pending_events[event_type]
                self.pending_events[event_type] = []
                self.last_flush[event_type] = current_time
                
                self._flush_events(events_to_flush)
                return True
            
            return False
    
    def _flush_loop(self):
        """Background thread to flush expired batches"""
        while True:
            time.sleep(0.5)  # Check every 500ms
            
            with self.lock:
                current_time = time.time()
                
                for event_type in list(self.pending_events.keys()):
                    if (self.pending_events[event_type] and 
                        current_time - self.last_flush[event_type] >= self.batch_timeout):
                        
                        events_to_flush = self.pending_events[event_type]
                        self.pending_events[event_type] = []
                        self.last_flush[event_type] = current_time
                        
                        self._flush_events(events_to_flush)
    
    def _flush_events(self, events: List[Event]):
        """
        Flush events to Redis pub/sub
        
        Args:
            events: List of events to flush
        """
        if not events:
            return
        
        try:
            # Send individual events for real-time processing
            for event in events:
                EventPublisher._publish_single_event(event)
            
            # Also send as batch for analytics
            if len(events) > 1:
                batch_event = Event(
                    type="event_batch",
                    data={
                        "events": [event.to_dict() for event in events],
                        "batch_size": len(events),
                        "event_types": list(set(event.type for event in events))
                    },
                    timestamp=datetime.utcnow().isoformat(),
                    priority=1  # Low priority for batch events
                )
                EventPublisher._publish_single_event(batch_event)
                
        except Exception as exc:
            logger.error(f"Failed to flush events: {exc}")


class EventPublisher:
    """
    Main event publishing system with Redis pub/sub integration
    """
    
    # Redis connection pool for thread safety
    _redis_pool = None
    _redis_client = None
    _event_batcher = None
    
    # Event statistics
    _stats = {
        'total_published': 0,
        'failed_publishes': 0,
        'events_by_type': defaultdict(int),
        'last_publish_time': None
    }
    
    @classmethod
    def initialize(cls, redis_url: str = "redis://localhost:6379/0"):
        """
        Initialize the event publisher with Redis connection
        
        Args:
            redis_url: Redis connection URL
        """
        try:
            cls._redis_pool = redis.ConnectionPool.from_url(
                redis_url, 
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            cls._redis_client = redis.Redis(connection_pool=cls._redis_pool)
            
            # Test connection
            cls._redis_client.ping()
            
            # Initialize event batcher
            cls._event_batcher = EventBatcher(batch_size=5, batch_timeout=2.0)
            
            logger.info("Event publisher initialized successfully")
            
        except Exception as exc:
            logger.error(f"Failed to initialize event publisher: {exc}")
            raise
    
    @classmethod
    def publish_event(cls, event_type: str, data: Dict[str, Any], 
                     priority: int = 5, correlation_id: Optional[str] = None,
                     force_immediate: bool = False) -> bool:
        """
        Publish an event to the real-time system
        
        Args:
            event_type: Type of event (from EventType enum or custom string)
            data: Event payload data
            priority: Event priority (1-10, 10 = highest)
            correlation_id: Optional correlation ID for tracking
            force_immediate: Force immediate publishing (bypass batching)
            
        Returns:
            True if event was published successfully
        """
        if not cls._redis_client:
            cls.initialize()
        
        try:
            # Create event object
            event = Event(
                type=event_type,
                data=data,
                timestamp=datetime.utcnow().isoformat(),
                priority=priority,
                correlation_id=correlation_id
            )
            
            # Add to batcher or send immediately
            was_sent_immediately = cls._event_batcher.add_event(event, force_immediate)
            
            # Update statistics
            cls._stats['total_published'] += 1
            cls._stats['events_by_type'][event_type] += 1
            cls._stats['last_publish_time'] = datetime.utcnow().isoformat()
            
            logger.debug(f"Published {event_type} event (immediate: {was_sent_immediately})")
            return True
            
        except Exception as exc:
            cls._stats['failed_publishes'] += 1
            logger.error(f"Failed to publish event {event_type}: {exc}")
            return False
    
    @classmethod
    def _publish_single_event(cls, event: Event):
        """
        Publish a single event to Redis pub/sub channels
        
        Args:
            event: Event to publish
        """
        try:
            # Publish to general events channel
            cls._redis_client.publish("ai_dashboard_events", event.to_json())
            
            # Publish to specific event type channel
            cls._redis_client.publish(f"ai_dashboard_{event.type}", event.to_json())
            
            # Store recent events in Redis list for debugging/replay
            cls._redis_client.lpush("recent_events", event.to_json())
            cls._redis_client.ltrim("recent_events", 0, 1000)  # Keep last 1000 events
            
            # Store event in time-series for analytics
            timestamp = int(time.time())
            cls._redis_client.zadd("event_timeline", {event.to_json(): timestamp})
            
            # Clean old timeline entries (keep last 24 hours)
            yesterday = timestamp - (24 * 60 * 60)
            cls._redis_client.zremrangebyscore("event_timeline", 0, yesterday)
            
        except Exception as exc:
            logger.error(f"Failed to publish single event: {exc}")
            raise
    
    @classmethod
    def get_statistics(cls) -> Dict[str, Any]:
        """
        Get publishing statistics
        
        Returns:
            Dictionary with publishing statistics
        """
        return {
            **cls._stats,
            'events_by_type': dict(cls._stats['events_by_type']),
            'redis_connection_active': cls._redis_client is not None,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    @classmethod
    def get_recent_events(cls, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get recent events from Redis storage
        
        Args:
            limit: Maximum number of events to retrieve
            
        Returns:
            List of recent events
        """
        if not cls._redis_client:
            return []
        
        try:
            recent_json = cls._redis_client.lrange("recent_events", 0, limit - 1)
            return [json.loads(event_json) for event_json in recent_json]
        except Exception as exc:
            logger.error(f"Failed to get recent events: {exc}")
            return []
    
    @classmethod
    def clear_event_history(cls):
        """Clear stored event history"""
        if cls._redis_client:
            cls._redis_client.delete("recent_events")
            cls._redis_client.delete("event_timeline")
            logger.info("Event history cleared")


class SystemEventManager:
    """
    High-level event management for system-wide events
    """
    
    @staticmethod
    def agent_started(agent_id: str, agent_type: str, capabilities: List[str]):
        """Publish agent started event"""
        EventPublisher.publish_event(
            EventType.AGENT_STATUS.value,
            {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "status": "started",
                "capabilities": capabilities,
                "started_at": datetime.utcnow().isoformat()
            },
            priority=7,
            force_immediate=True
        )
    
    @staticmethod
    def agent_stopped(agent_id: str, agent_type: str, reason: str = "normal_shutdown"):
        """Publish agent stopped event"""
        EventPublisher.publish_event(
            EventType.AGENT_STATUS.value,
            {
                "agent_id": agent_id,
                "agent_type": agent_type,
                "status": "stopped",
                "reason": reason,
                "stopped_at": datetime.utcnow().isoformat()
            },
            priority=7,
            force_immediate=True
        )
    
    @staticmethod
    def system_alert(level: str, message: str, details: Dict[str, Any] = None):
        """Publish system alert"""
        priority_map = {
            "info": 3,
            "warning": 7,
            "error": 9,
            "critical": 10
        }
        
        EventPublisher.publish_event(
            EventType.SYSTEM_ALERT.value,
            {
                "level": level,
                "message": message,
                "details": details or {},
                "alert_time": datetime.utcnow().isoformat()
            },
            priority=priority_map.get(level, 5),
            force_immediate=level in ["error", "critical"]
        )
    
    @staticmethod
    def queue_depth_warning(queue_name: str, depth: int, threshold: int):
        """Publish queue depth warning"""
        EventPublisher.publish_event(
            EventType.QUEUE_DEPTH_ALERT.value,
            {
                "queue_name": queue_name,
                "current_depth": depth,
                "threshold": threshold,
                "severity": "warning" if depth < threshold * 2 else "critical",
                "alert_time": datetime.utcnow().isoformat()
            },
            priority=8,
            force_immediate=True
        )
    
    @staticmethod
    def worker_status_change(worker_id: str, status: str, worker_info: Dict[str, Any] = None):
        """Publish worker status change"""
        event_type = EventType.WORKER_ONLINE.value if status == "online" else EventType.WORKER_OFFLINE.value
        
        EventPublisher.publish_event(
            event_type,
            {
                "worker_id": worker_id,
                "status": status,
                "worker_info": worker_info or {},
                "status_change_time": datetime.utcnow().isoformat()
            },
            priority=6,
            force_immediate=True
        )


# Convenience functions for common use cases
def publish_event(event_type: str, data: Dict[str, Any], priority: int = 5, 
                  correlation_id: Optional[str] = None, force_immediate: bool = False) -> bool:
    """
    Convenience function to publish events
    
    Args:
        event_type: Type of event
        data: Event data
        priority: Event priority (1-10)
        correlation_id: Optional correlation ID
        force_immediate: Force immediate publishing
        
    Returns:
        True if successful
    """
    return EventPublisher.publish_event(
        event_type, data, priority, correlation_id, force_immediate
    )


def publish_task_progress(task_id: str, progress: int, status: str, 
                         agent_type: str, tokens_processed: int = 0):
    """Convenience function for task progress events"""
    publish_event(
        EventType.TASK_PROGRESS.value,
        {
            "task_id": task_id,
            "progress": progress,
            "status": status,
            "agent_type": agent_type,
            "tokens_processed": tokens_processed
        },
        priority=6
    )


def publish_system_metrics(metrics: Dict[str, Any]):
    """Convenience function for system metrics events"""
    publish_event(
        EventType.METRICS_UPDATE.value,
        metrics,
        priority=4  # Lower priority for routine metrics
    )


def publish_alert(level: str, message: str, details: Dict[str, Any] = None):
    """Convenience function for system alerts"""
    SystemEventManager.system_alert(level, message, details)


# Event subscriber for testing and development
class EventSubscriber:
    """
    Event subscriber for testing and monitoring events
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        """Initialize event subscriber"""
        self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
        self.subscribers = {}
        self.is_listening = False
    
    def subscribe_to_events(self, event_types: List[str] = None, callback=None):
        """
        Subscribe to events
        
        Args:
            event_types: List of event types to subscribe to (None for all)
            callback: Function to call with received events
        """
        if event_types is None:
            channels = ["ai_dashboard_events"]
        else:
            channels = [f"ai_dashboard_{event_type}" for event_type in event_types]
        
        pubsub = self.redis_client.pubsub()
        pubsub.subscribe(*channels)
        
        self.is_listening = True
        
        try:
            for message in pubsub.listen():
                if not self.is_listening:
                    break
                
                if message['type'] == 'message':
                    try:
                        event_data = json.loads(message['data'])
                        if callback:
                            callback(event_data)
                        else:
                            print(f"Received event: {event_data['type']} - {event_data['timestamp']}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode event message: {e}")
                        
        except KeyboardInterrupt:
            logger.info("Event subscription interrupted")
        finally:
            pubsub.unsubscribe()
            pubsub.close()
    
    def stop_listening(self):
        """Stop listening for events"""
        self.is_listening = False


# Initialize event publisher on module import
try:
    EventPublisher.initialize()
except Exception as e:
    logger.warning(f"Failed to initialize event publisher on import: {e}")


if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(level=logging.INFO)
    
    # Test event publishing
    print("Testing event publishing...")
    
    # Test various event types
    publish_event("test_event", {"message": "Hello World"}, priority=5)
    publish_task_progress("task_123", 50, "Processing...", "gpt-4", 2500)
    publish_system_metrics({"cpu": 45.2, "memory": 62.1, "tasks": 15})
    publish_alert("warning", "High CPU usage detected", {"cpu_percent": 89.5})
    
    # Test system events
    SystemEventManager.agent_started("agent_001", "gpt-4", ["reasoning", "analysis"])
    SystemEventManager.queue_depth_warning("high_priority", 150, 100)
    
    # Get statistics
    stats = EventPublisher.get_statistics()
    print(f"Publisher stats: {stats}")
    
    # Get recent events
    recent = EventPublisher.get_recent_events(5)
    print(f"Recent events: {len(recent)}")
    
    print("Event publishing test completed!")