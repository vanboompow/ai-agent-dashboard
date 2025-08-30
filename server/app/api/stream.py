from fastapi import APIRouter, Request, Query, HTTPException, Depends
from sse_starlette.sse import EventSourceResponse
import asyncio
import json
import gzip
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Set
import uuid

from ..services.redis_pubsub import (
    get_redis_manager, RedisSubscriber, Event, EventType, 
    RedisConnectionManager
)
from ..services.event_aggregator import EventAggregator, create_default_aggregator

logger = logging.getLogger(__name__)
router = APIRouter()

# Global event aggregator
aggregator: Optional[EventAggregator] = None


async def get_event_aggregator() -> EventAggregator:
    """Get the global event aggregator"""
    global aggregator
    if not aggregator:
        aggregator = create_default_aggregator()
        await aggregator.start_periodic_flush()
    return aggregator


class SSEConnection:
    """Manages individual SSE connection state"""
    
    def __init__(self, connection_id: str, request: Request):
        self.connection_id = connection_id
        self.request = request
        self.subscriber: Optional[RedisSubscriber] = None
        self.subscribed_channels: Set[str] = set()
        self.event_filters: Dict[str, Any] = {}
        self.connected_at = datetime.utcnow()
        self.last_heartbeat = datetime.utcnow()
        self.compression_enabled = False
        self.max_queue_size = 1000
        self.event_queue: asyncio.Queue = asyncio.Queue(maxsize=self.max_queue_size)
    
    async def initialize(self, redis_manager: RedisConnectionManager,
                        channels: List[str], filters: Dict[str, Any]) -> None:
        """Initialize Redis subscriber for this connection"""
        self.subscriber = redis_manager.get_subscriber()
        self.event_filters = filters
        
        # Subscribe to requested channels
        await self.subscriber.subscribe_to_channels(channels)
        self.subscribed_channels.update(channels)
        
        # Add event handler to queue events for this connection
        for channel in channels:
            await self.subscriber.add_event_handler(channel, self._handle_event)
        
        logger.info(f"SSE connection {self.connection_id} initialized with channels: {channels}")
    
    async def _handle_event(self, event: Event) -> None:
        """Handle incoming event from Redis"""
        try:
            # Apply filters
            if not self._passes_filters(event):
                return
            
            # Add to queue with backpressure handling
            try:
                self.event_queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(f"Event queue full for connection {self.connection_id}, dropping oldest event")
                try:
                    self.event_queue.get_nowait()  # Remove oldest
                    self.event_queue.put_nowait(event)  # Add new
                except asyncio.QueueEmpty:
                    pass
                    
        except Exception as e:
            logger.error(f"Error handling event for connection {self.connection_id}: {e}")
    
    def _passes_filters(self, event: Event) -> bool:
        """Check if event passes connection filters"""
        if not self.event_filters:
            return True
        
        # Event type filter
        if "event_types" in self.event_filters:
            if event.type not in self.event_filters["event_types"]:
                return False
        
        # Priority filter
        if "min_priority" in self.event_filters:
            if event.priority.value < self.event_filters["min_priority"]:
                return False
        
        # Agent filter
        if "agent_ids" in self.event_filters:
            agent_id = event.data.get("agent_id")
            if agent_id and agent_id not in self.event_filters["agent_ids"]:
                return False
        
        # Custom data filters
        if "data_filters" in self.event_filters:
            for field, expected_value in self.event_filters["data_filters"].items():
                if event.data.get(field) != expected_value:
                    return False
        
        return True
    
    async def cleanup(self) -> None:
        """Cleanup connection resources"""
        if self.subscriber:
            await self.subscriber.stop_listening()
            # Subscriber will be cleaned up by connection manager
        logger.info(f"Cleaned up SSE connection {self.connection_id}")


# Global connection registry
active_connections: Dict[str, SSEConnection] = {}


async def event_generator(request: Request, connection: SSEConnection,
                         redis_manager: RedisConnectionManager) -> None:
    """Generate Server-Sent Events from Redis subscriptions"""
    connection_id = connection.connection_id
    heartbeat_interval = 30  # seconds
    last_heartbeat = datetime.utcnow()
    
    try:
        # Start Redis event listener
        listener_task = asyncio.create_task(
            _redis_event_listener(connection, redis_manager)
        )
        
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                logger.info(f"Client {connection_id} disconnected")
                break
            
            now = datetime.utcnow()
            
            # Send heartbeat
            if (now - last_heartbeat).total_seconds() > heartbeat_interval:
                yield {
                    "event": "heartbeat",
                    "data": json.dumps({
                        "timestamp": now.isoformat(),
                        "connection_id": connection_id
                    })
                }
                last_heartbeat = now
                connection.last_heartbeat = now
            
            # Process queued events
            try:
                # Wait for event with timeout
                event = await asyncio.wait_for(connection.event_queue.get(), timeout=1.0)
                
                # Prepare event data
                event_data = {
                    "id": event.id,
                    "type": event.type,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data,
                    "priority": event.priority.value
                }
                
                # Apply compression if enabled and data is large
                data_json = json.dumps(event_data)
                if (connection.compression_enabled and 
                    len(data_json) > 1024):  # Compress if > 1KB
                    compressed_data = gzip.compress(data_json.encode()).decode('latin-1')
                    yield {
                        "event": event.type,
                        "data": compressed_data,
                        "id": event.id,
                        "retry": 3000
                    }
                else:
                    yield {
                        "event": event.type,
                        "data": data_json,
                        "id": event.id,
                        "retry": 3000
                    }
                
            except asyncio.TimeoutError:
                # No events in queue, continue loop for heartbeat
                continue
            except Exception as e:
                logger.error(f"Error processing event for {connection_id}: {e}")
                continue
                
    except Exception as e:
        logger.error(f"Error in event generator for {connection_id}: {e}")
    finally:
        # Cleanup
        listener_task.cancel()
        try:
            await listener_task
        except asyncio.CancelledError:
            pass
        
        await connection.cleanup()
        if connection_id in active_connections:
            del active_connections[connection_id]


async def _redis_event_listener(connection: SSEConnection, 
                               redis_manager: RedisConnectionManager) -> None:
    """Listen for Redis events and forward to connection"""
    try:
        if connection.subscriber:
            async for event in connection.subscriber.listen_for_events():
                # Event is already handled by connection._handle_event
                pass
    except Exception as e:
        logger.error(f"Redis event listener error: {e}")


@router.get("/")
async def stream_events(
    request: Request,
    channels: str = Query("agents,tasks,metrics", description="Comma-separated list of channels"),
    event_types: Optional[str] = Query(None, description="Comma-separated list of event types to filter"),
    agent_ids: Optional[str] = Query(None, description="Comma-separated list of agent IDs to filter"),
    min_priority: int = Query(1, description="Minimum event priority (1=LOW, 2=NORMAL, 3=HIGH, 4=CRITICAL)"),
    compression: bool = Query(False, description="Enable compression for large payloads"),
    buffer_size: int = Query(50, description="Number of recent events to send on connect"),
    redis_manager: RedisConnectionManager = Depends(get_redis_manager)
):
    """Enhanced SSE endpoint for real-time dashboard updates with Redis integration"""
    
    connection_id = str(uuid.uuid4())
    
    # Parse parameters
    channel_list = [c.strip() for c in channels.split(",") if c.strip()]
    
    # Build event filters
    filters = {"min_priority": min_priority}
    
    if event_types:
        try:
            filters["event_types"] = [
                EventType(t.strip()) for t in event_types.split(",") if t.strip()
            ]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")
    
    if agent_ids:
        filters["agent_ids"] = [a.strip() for a in agent_ids.split(",") if a.strip()]
    
    # Create connection
    connection = SSEConnection(connection_id, request)
    connection.compression_enabled = compression
    connection.max_queue_size = max(100, buffer_size * 2)
    
    try:
        # Initialize connection with Redis
        await connection.initialize(redis_manager, channel_list, filters)
        
        # Register active connection
        active_connections[connection_id] = connection
        
        # Send buffered events if requested
        if buffer_size > 0:
            await _send_buffered_events(connection, redis_manager, buffer_size)
        
        # Return event stream
        return EventSourceResponse(
            event_generator(request, connection, redis_manager),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Connection-ID": connection_id
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize SSE connection: {e}")
        if connection_id in active_connections:
            del active_connections[connection_id]
        raise HTTPException(status_code=500, detail="Failed to initialize event stream")


async def _send_buffered_events(connection: SSEConnection, 
                               redis_manager: RedisConnectionManager,
                               buffer_size: int) -> None:
    """Send recent buffered events to new connection"""
    try:
        for channel in connection.subscribed_channels:
            if connection.subscriber:
                recent_events = await connection.subscriber.get_buffered_events(
                    channel, buffer_size
                )
                
                for event in recent_events[-buffer_size:]:  # Most recent first
                    if connection._passes_filters(event):
                        await connection._handle_event(event)
                        
    except Exception as e:
        logger.error(f"Error sending buffered events: {e}")


@router.get("/logs")
async def stream_logs(
    request: Request,
    levels: str = Query("INFO,WARNING,ERROR", description="Comma-separated log levels"),
    sources: Optional[str] = Query(None, description="Comma-separated log sources"),
    redis_manager: RedisConnectionManager = Depends(get_redis_manager)
):
    """Enhanced SSE endpoint for real-time log streaming"""
    
    connection_id = str(uuid.uuid4())
    
    # Parse parameters
    level_list = [l.strip().upper() for l in levels.split(",") if l.strip()]
    source_list = [s.strip() for s in sources.split(",") if sources and s.strip()] or []
    
    # Build filters for log events
    filters = {
        "event_types": [EventType.LOG_MESSAGE],
        "data_filters": {}
    }
    
    if level_list:
        filters["data_filters"]["level"] = level_list
    if source_list:
        filters["data_filters"]["source"] = source_list
    
    # Create connection for logs
    connection = SSEConnection(connection_id, request)
    
    try:
        await connection.initialize(redis_manager, ["logs"], filters)
        active_connections[connection_id] = connection
        
        return EventSourceResponse(
            event_generator(request, connection, redis_manager),
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Connection-ID": connection_id
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize log stream: {e}")
        if connection_id in active_connections:
            del active_connections[connection_id]
        raise HTTPException(status_code=500, detail="Failed to initialize log stream")


@router.get("/stats")
async def get_stream_stats():
    """Get statistics about active SSE connections"""
    now = datetime.utcnow()
    
    connection_stats = []
    for conn_id, conn in active_connections.items():
        connection_stats.append({
            "connection_id": conn_id,
            "connected_at": conn.connected_at.isoformat(),
            "last_heartbeat": conn.last_heartbeat.isoformat(),
            "uptime_seconds": (now - conn.connected_at).total_seconds(),
            "subscribed_channels": list(conn.subscribed_channels),
            "queue_size": conn.event_queue.qsize(),
            "compression_enabled": conn.compression_enabled,
            "filters": conn.event_filters
        })
    
    # Get aggregator stats
    agg = await get_event_aggregator()
    
    return {
        "active_connections": len(active_connections),
        "connections": connection_stats,
        "aggregator_stats": agg.get_stats(),
        "total_uptime_seconds": sum(
            (now - conn.connected_at).total_seconds() 
            for conn in active_connections.values()
        )
    }


@router.post("/broadcast")
async def broadcast_message(
    message: str,
    event_type: str = "broadcast",
    priority: int = 2,
    target_connections: Optional[List[str]] = None,
    redis_manager: RedisConnectionManager = Depends(get_redis_manager)
):
    """Broadcast message to all or specific SSE connections"""
    try:
        publisher = redis_manager.get_publisher()
        
        # Create broadcast event
        from ..services.redis_pubsub import Event, EventType, EventPriority
        
        event = Event(
            id=str(uuid.uuid4()),
            type=EventType.BROADCAST,
            priority=EventPriority(priority),
            timestamp=datetime.utcnow(),
            data={
                "message": message,
                "event_type": event_type,
                "target_connections": target_connections
            },
            source="api_broadcast"
        )
        
        success = await publisher.publish_event(event)
        
        return {
            "success": success,
            "message": "Broadcast sent" if success else "Failed to send broadcast",
            "event_id": event.id,
            "target_connections": len(target_connections) if target_connections else "all"
        }
        
    except Exception as e:
        logger.error(f"Broadcast failed: {e}")
        raise HTTPException(status_code=500, detail=f"Broadcast failed: {str(e)}")


# Cleanup function for app shutdown
async def cleanup_sse_connections():
    """Cleanup all active SSE connections"""
    connections_to_cleanup = list(active_connections.values())
    
    for connection in connections_to_cleanup:
        try:
            await connection.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up connection {connection.connection_id}: {e}")
    
    active_connections.clear()
    
    # Stop aggregator
    global aggregator
    if aggregator:
        await aggregator.stop_periodic_flush()
        aggregator = None
    
    logger.info("All SSE connections cleaned up")