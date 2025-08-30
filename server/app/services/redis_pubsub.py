"""
Redis Pub/Sub service for real-time event communication
Handles message serialization, channel management, and connection pooling
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional, AsyncGenerator, List, Callable
from enum import Enum
import redis.asyncio as redis
from pydantic import BaseModel
import uuid

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    AGENT_STATUS = "agent_status"
    TASK_UPDATE = "task_update"
    METRICS_DATA = "metrics_data"
    SYSTEM_ALERT = "system_alert"
    COLLABORATION = "collaboration"
    BROADCAST = "broadcast"
    HEARTBEAT = "heartbeat"
    PERFORMANCE_ALERT = "performance_alert"
    LOG_MESSAGE = "log_message"


class EventPriority(int, Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class Event(BaseModel):
    """Base event model for all real-time events"""
    id: str
    type: EventType
    priority: EventPriority = EventPriority.NORMAL
    timestamp: datetime
    data: Dict[str, Any]
    source: Optional[str] = None
    target_clients: Optional[List[str]] = None  # Specific client targeting
    expires_at: Optional[datetime] = None


class ChannelConfig(BaseModel):
    """Configuration for Redis channels"""
    name: str
    buffer_size: int = 1000
    retention_seconds: int = 3600
    compression: bool = False


class RedisPublisher:
    """Handles publishing events to Redis channels"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.channels = {
            EventType.AGENT_STATUS: ChannelConfig(name="agents", buffer_size=500),
            EventType.TASK_UPDATE: ChannelConfig(name="tasks", buffer_size=1000),
            EventType.METRICS_DATA: ChannelConfig(name="metrics", buffer_size=200),
            EventType.SYSTEM_ALERT: ChannelConfig(name="alerts", buffer_size=100),
            EventType.COLLABORATION: ChannelConfig(name="collaboration", buffer_size=300),
            EventType.BROADCAST: ChannelConfig(name="broadcast", buffer_size=50),
            EventType.HEARTBEAT: ChannelConfig(name="heartbeat", buffer_size=10),
            EventType.PERFORMANCE_ALERT: ChannelConfig(name="performance", buffer_size=100),
            EventType.LOG_MESSAGE: ChannelConfig(name="logs", buffer_size=2000),
        }
    
    async def publish_event(self, event: Event) -> bool:
        """Publish an event to the appropriate channel"""
        try:
            channel_config = self.channels.get(event.type)
            if not channel_config:
                logger.error(f"Unknown event type: {event.type}")
                return False
            
            # Serialize event
            event_data = event.model_dump_json()
            
            # Compress if configured
            if channel_config.compression:
                import gzip
                event_data = gzip.compress(event_data.encode()).decode('latin-1')
            
            # Publish to channel
            await self.redis.publish(channel_config.name, event_data)
            
            # Store in buffer with expiration
            buffer_key = f"buffer:{channel_config.name}"
            await self.redis.lpush(buffer_key, event_data)
            await self.redis.ltrim(buffer_key, 0, channel_config.buffer_size - 1)
            await self.redis.expire(buffer_key, channel_config.retention_seconds)
            
            logger.debug(f"Published event {event.id} to channel {channel_config.name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event {event.id}: {e}")
            return False
    
    async def publish_agent_status(self, agent_id: str, status: str, 
                                  current_task: Optional[str] = None,
                                  performance_data: Optional[Dict] = None) -> bool:
        """Convenience method for agent status updates"""
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.AGENT_STATUS,
            timestamp=datetime.utcnow(),
            data={
                "agent_id": agent_id,
                "status": status,
                "current_task": current_task,
                "performance": performance_data or {}
            },
            source="agent_manager"
        )
        return await self.publish_event(event)
    
    async def publish_task_update(self, task_id: str, status: str, 
                                 progress: Optional[int] = None,
                                 agent_id: Optional[str] = None) -> bool:
        """Convenience method for task updates"""
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.TASK_UPDATE,
            timestamp=datetime.utcnow(),
            data={
                "task_id": task_id,
                "status": status,
                "progress": progress,
                "agent_id": agent_id
            },
            source="task_manager"
        )
        return await self.publish_event(event)
    
    async def publish_metrics(self, metrics_data: Dict[str, Any]) -> bool:
        """Convenience method for metrics updates"""
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.METRICS_DATA,
            timestamp=datetime.utcnow(),
            data=metrics_data,
            source="metrics_collector"
        )
        return await self.publish_event(event)
    
    async def publish_system_alert(self, message: str, level: str = "info",
                                  details: Optional[Dict] = None) -> bool:
        """Convenience method for system alerts"""
        priority = EventPriority.NORMAL
        if level == "error":
            priority = EventPriority.HIGH
        elif level == "critical":
            priority = EventPriority.CRITICAL
        
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.SYSTEM_ALERT,
            priority=priority,
            timestamp=datetime.utcnow(),
            data={
                "message": message,
                "level": level,
                "details": details or {}
            },
            source="system"
        )
        return await self.publish_event(event)
    
    async def publish_collaboration_event(self, user_id: str, action: str,
                                        target: str, data: Optional[Dict] = None) -> bool:
        """Convenience method for collaboration events"""
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.COLLABORATION,
            timestamp=datetime.utcnow(),
            data={
                "user_id": user_id,
                "action": action,  # "viewing", "editing", "left", "joined"
                "target": target,  # dashboard, agent_detail, task_detail
                "data": data or {}
            },
            source="collaboration_manager"
        )
        return await self.publish_event(event)


class RedisSubscriber:
    """Handles subscribing to Redis channels and managing event streams"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.pubsub = None
        self.subscriptions: Dict[str, List[Callable]] = {}
        self._running = False
    
    async def subscribe_to_channels(self, channels: List[str]) -> None:
        """Subscribe to multiple channels"""
        if not self.pubsub:
            self.pubsub = self.redis.pubsub()
        
        for channel in channels:
            await self.pubsub.subscribe(channel)
            logger.info(f"Subscribed to Redis channel: {channel}")
    
    async def unsubscribe_from_channels(self, channels: List[str]) -> None:
        """Unsubscribe from channels"""
        if self.pubsub:
            for channel in channels:
                await self.pubsub.unsubscribe(channel)
                logger.info(f"Unsubscribed from Redis channel: {channel}")
    
    async def add_event_handler(self, channel: str, handler: Callable[[Event], None]) -> None:
        """Add an event handler for a specific channel"""
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
        self.subscriptions[channel].append(handler)
    
    async def remove_event_handler(self, channel: str, handler: Callable) -> None:
        """Remove an event handler"""
        if channel in self.subscriptions:
            self.subscriptions[channel].remove(handler)
    
    async def get_buffered_events(self, channel: str, limit: int = 50) -> List[Event]:
        """Get recent events from channel buffer"""
        try:
            buffer_key = f"buffer:{channel}"
            events_data = await self.redis.lrange(buffer_key, 0, limit - 1)
            
            events = []
            for event_data in events_data:
                try:
                    # Handle compressed data
                    if event_data.startswith(b'\x1f\x8b'):  # gzip header
                        import gzip
                        event_data = gzip.decompress(event_data).decode()
                    else:
                        event_data = event_data.decode() if isinstance(event_data, bytes) else event_data
                    
                    event_dict = json.loads(event_data)
                    event = Event(**event_dict)
                    events.append(event)
                except Exception as e:
                    logger.error(f"Failed to parse buffered event: {e}")
                    continue
            
            return events
            
        except Exception as e:
            logger.error(f"Failed to get buffered events for {channel}: {e}")
            return []
    
    async def listen_for_events(self) -> AsyncGenerator[Event, None]:
        """Listen for events from subscribed channels"""
        if not self.pubsub:
            raise RuntimeError("Not subscribed to any channels")
        
        self._running = True
        try:
            async for message in self.pubsub.listen():
                if not self._running:
                    break
                
                if message['type'] == 'message':
                    try:
                        # Parse event data
                        event_data = message['data']
                        if isinstance(event_data, bytes):
                            event_data = event_data.decode()
                        
                        # Handle compression
                        if event_data.startswith('\x1f\x8b'):  # gzip header
                            import gzip
                            event_data = gzip.decompress(event_data.encode('latin-1')).decode()
                        
                        event_dict = json.loads(event_data)
                        event = Event(**event_dict)
                        
                        # Call handlers for this channel
                        channel = message['channel'].decode() if isinstance(message['channel'], bytes) else message['channel']
                        if channel in self.subscriptions:
                            for handler in self.subscriptions[channel]:
                                try:
                                    await handler(event)
                                except Exception as e:
                                    logger.error(f"Event handler failed: {e}")
                        
                        yield event
                        
                    except Exception as e:
                        logger.error(f"Failed to process message: {e}")
                        continue
        
        except Exception as e:
            logger.error(f"Error in event listener: {e}")
        finally:
            self._running = False
    
    async def stop_listening(self) -> None:
        """Stop listening for events"""
        self._running = False
        if self.pubsub:
            await self.pubsub.close()
            self.pubsub = None


class RedisConnectionManager:
    """Manages Redis connection pool and provides publishers/subscribers"""
    
    def __init__(self, redis_url: str, max_connections: int = 20):
        self.redis_url = redis_url
        self.max_connections = max_connections
        self.connection_pool = None
        self.redis_client = None
    
    async def initialize(self) -> None:
        """Initialize Redis connection pool"""
        try:
            self.connection_pool = redis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                retry_on_timeout=True,
                socket_keepalive=True,
                socket_keepalive_options={}
            )
            self.redis_client = redis.Redis(connection_pool=self.connection_pool)
            
            # Test connection
            await self.redis_client.ping()
            logger.info(f"Redis connection pool initialized: {self.redis_url}")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis connection: {e}")
            raise
    
    async def close(self) -> None:
        """Close Redis connections"""
        if self.redis_client:
            await self.redis_client.close()
        if self.connection_pool:
            await self.connection_pool.disconnect()
        logger.info("Redis connections closed")
    
    def get_publisher(self) -> RedisPublisher:
        """Get a Redis publisher instance"""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        return RedisPublisher(self.redis_client)
    
    def get_subscriber(self) -> RedisSubscriber:
        """Get a Redis subscriber instance"""
        if not self.redis_client:
            raise RuntimeError("Redis not initialized")
        # Create new Redis connection for subscriber to avoid blocking
        subscriber_client = redis.Redis(connection_pool=self.connection_pool)
        return RedisSubscriber(subscriber_client)
    
    async def health_check(self) -> Dict[str, Any]:
        """Check Redis connection health"""
        try:
            if not self.redis_client:
                return {"status": "disconnected", "error": "Not initialized"}
            
            # Test basic operations
            start_time = datetime.utcnow()
            await self.redis_client.ping()
            latency = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            # Get connection info
            info = await self.redis_client.info()
            
            return {
                "status": "healthy",
                "latency_ms": round(latency, 2),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown")
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}


# Global connection manager instance
connection_manager: Optional[RedisConnectionManager] = None


async def get_redis_manager() -> RedisConnectionManager:
    """Get the global Redis connection manager"""
    global connection_manager
    if not connection_manager:
        raise RuntimeError("Redis connection manager not initialized")
    return connection_manager


async def initialize_redis(redis_url: str, max_connections: int = 20) -> RedisConnectionManager:
    """Initialize the global Redis connection manager"""
    global connection_manager
    connection_manager = RedisConnectionManager(redis_url, max_connections)
    await connection_manager.initialize()
    return connection_manager


async def cleanup_redis() -> None:
    """Cleanup Redis connections"""
    global connection_manager
    if connection_manager:
        await connection_manager.close()
        connection_manager = None