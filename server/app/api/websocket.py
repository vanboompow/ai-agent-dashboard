"""
WebSocket endpoint for real-time communication as SSE fallback
Provides bidirectional communication support and enhanced reliability
"""
import asyncio
import json
import logging
import gzip
from datetime import datetime, timedelta
from typing import Dict, Set, List, Optional, Any
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from pydantic import BaseModel

from ..services.redis_pubsub import (
    get_redis_manager, RedisSubscriber, Event, EventType, 
    RedisConnectionManager, RedisPublisher
)
from ..services.event_aggregator import EventAggregator, create_default_aggregator

logger = logging.getLogger(__name__)
router = APIRouter()

# Global event aggregator (shared with SSE)
aggregator: Optional[EventAggregator] = None


async def get_event_aggregator() -> EventAggregator:
    """Get the global event aggregator"""
    global aggregator
    if not aggregator:
        aggregator = create_default_aggregator()
        await aggregator.start_periodic_flush()
    return aggregator


class WebSocketMessage(BaseModel):
    """Base message structure for WebSocket communication"""
    id: str
    type: str
    data: Dict[str, Any]
    timestamp: datetime


class ClientMessage(BaseModel):
    """Client-to-server message structure"""
    type: str  # subscribe, unsubscribe, ping, configure
    data: Dict[str, Any]


class ServerMessage(BaseModel):
    """Server-to-client message structure"""
    type: str  # event, pong, error, status
    data: Dict[str, Any]
    id: Optional[str] = None
    timestamp: datetime


class WebSocketConnection:
    """Manages individual WebSocket connection state"""
    
    def __init__(self, websocket: WebSocket, connection_id: str):
        self.websocket = websocket
        self.connection_id = connection_id
        self.subscriber: Optional[RedisSubscriber] = None
        self.subscribed_channels: Set[str] = set()
        self.event_filters: Dict[str, Any] = {}
        self.connected_at = datetime.utcnow()
        self.last_ping = datetime.utcnow()
        self.compression_enabled = False
        self.is_active = True
        
        # Stats tracking
        self.messages_sent = 0
        self.messages_received = 0
        self.errors_count = 0
        self.last_activity = datetime.utcnow()
    
    async def initialize(self, redis_manager: RedisConnectionManager,
                        channels: List[str], filters: Dict[str, Any]) -> None:
        """Initialize Redis subscriber for this connection"""
        self.subscriber = redis_manager.get_subscriber()
        self.event_filters = filters
        
        # Subscribe to requested channels
        await self.subscriber.subscribe_to_channels(channels)
        self.subscribed_channels.update(channels)
        
        # Add event handler
        for channel in channels:
            await self.subscriber.add_event_handler(channel, self._handle_redis_event)
        
        logger.info(f"WebSocket connection {self.connection_id} initialized with channels: {channels}")
    
    async def _handle_redis_event(self, event: Event) -> None:
        """Handle incoming event from Redis"""
        try:
            # Apply filters
            if not self._passes_filters(event):
                return
            
            # Convert to WebSocket message
            message = ServerMessage(
                type="event",
                data={
                    "event_type": event.type,
                    "event_id": event.id,
                    "timestamp": event.timestamp.isoformat(),
                    "priority": event.priority.value,
                    "payload": event.data,
                    "source": event.source
                },
                id=event.id,
                timestamp=datetime.utcnow()
            )
            
            await self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error handling Redis event for WebSocket {self.connection_id}: {e}")
            self.errors_count += 1
    
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
        
        return True
    
    async def send_message(self, message: ServerMessage) -> bool:
        """Send message to WebSocket client"""
        if not self.is_active:
            return False
        
        try:
            message_data = message.model_dump_json()
            
            # Apply compression if enabled and message is large
            if self.compression_enabled and len(message_data) > 1024:
                compressed_data = gzip.compress(message_data.encode())
                await self.websocket.send_bytes(compressed_data)
            else:
                await self.websocket.send_text(message_data)
            
            self.messages_sent += 1
            self.last_activity = datetime.utcnow()
            return True
            
        except Exception as e:
            logger.error(f"Error sending WebSocket message: {e}")
            self.is_active = False
            self.errors_count += 1
            return False
    
    async def send_error(self, error_message: str, error_code: str = "GENERAL_ERROR") -> None:
        """Send error message to client"""
        message = ServerMessage(
            type="error",
            data={
                "code": error_code,
                "message": error_message,
                "connection_id": self.connection_id
            },
            timestamp=datetime.utcnow()
        )
        await self.send_message(message)
    
    async def send_pong(self, ping_id: Optional[str] = None) -> None:
        """Send pong response"""
        message = ServerMessage(
            type="pong",
            data={
                "connection_id": self.connection_id,
                "ping_id": ping_id,
                "server_time": datetime.utcnow().isoformat()
            },
            timestamp=datetime.utcnow()
        )
        await self.send_message(message)
    
    async def handle_client_message(self, message: ClientMessage, 
                                   redis_manager: RedisConnectionManager) -> None:
        """Handle incoming client message"""
        self.messages_received += 1
        self.last_activity = datetime.utcnow()
        
        try:
            if message.type == "ping":
                ping_id = message.data.get("id")
                await self.send_pong(ping_id)
                self.last_ping = datetime.utcnow()
            
            elif message.type == "subscribe":
                await self._handle_subscribe(message, redis_manager)
            
            elif message.type == "unsubscribe":
                await self._handle_unsubscribe(message)
            
            elif message.type == "configure":
                await self._handle_configure(message)
            
            elif message.type == "publish":
                await self._handle_publish(message, redis_manager)
            
            else:
                await self.send_error(f"Unknown message type: {message.type}", "UNKNOWN_MESSAGE_TYPE")
                
        except Exception as e:
            logger.error(f"Error handling client message: {e}")
            await self.send_error(f"Error processing message: {str(e)}", "MESSAGE_PROCESSING_ERROR")
    
    async def _handle_subscribe(self, message: ClientMessage, 
                               redis_manager: RedisConnectionManager) -> None:
        """Handle channel subscription"""
        channels = message.data.get("channels", [])
        filters = message.data.get("filters", {})
        
        if not channels:
            await self.send_error("No channels specified for subscription", "INVALID_SUBSCRIPTION")
            return
        
        # Initialize or update subscription
        if not self.subscriber:
            await self.initialize(redis_manager, channels, filters)
        else:
            # Add new channels
            new_channels = [ch for ch in channels if ch not in self.subscribed_channels]
            if new_channels:
                await self.subscriber.subscribe_to_channels(new_channels)
                self.subscribed_channels.update(new_channels)
                
                for channel in new_channels:
                    await self.subscriber.add_event_handler(channel, self._handle_redis_event)
        
        # Update filters
        self.event_filters.update(filters)
        
        # Send confirmation
        response = ServerMessage(
            type="subscription_updated",
            data={
                "subscribed_channels": list(self.subscribed_channels),
                "filters": self.event_filters
            },
            timestamp=datetime.utcnow()
        )
        await self.send_message(response)
    
    async def _handle_unsubscribe(self, message: ClientMessage) -> None:
        """Handle channel unsubscription"""
        channels = message.data.get("channels", [])
        
        if not channels:
            await self.send_error("No channels specified for unsubscription", "INVALID_UNSUBSCRIPTION")
            return
        
        # Remove channels
        for channel in channels:
            if channel in self.subscribed_channels:
                if self.subscriber:
                    await self.subscriber.unsubscribe_from_channels([channel])
                self.subscribed_channels.discard(channel)
        
        # Send confirmation
        response = ServerMessage(
            type="subscription_updated",
            data={
                "subscribed_channels": list(self.subscribed_channels),
                "unsubscribed_from": channels
            },
            timestamp=datetime.utcnow()
        )
        await self.send_message(response)
    
    async def _handle_configure(self, message: ClientMessage) -> None:
        """Handle configuration updates"""
        config = message.data.get("config", {})
        
        if "compression" in config:
            self.compression_enabled = bool(config["compression"])
        
        if "filters" in config:
            self.event_filters.update(config["filters"])
        
        # Send confirmation
        response = ServerMessage(
            type="configuration_updated",
            data={
                "compression_enabled": self.compression_enabled,
                "filters": self.event_filters
            },
            timestamp=datetime.utcnow()
        )
        await self.send_message(response)
    
    async def _handle_publish(self, message: ClientMessage, 
                             redis_manager: RedisConnectionManager) -> None:
        """Handle client message publishing (bidirectional communication)"""
        event_data = message.data.get("event", {})
        
        if not event_data:
            await self.send_error("No event data provided for publishing", "INVALID_PUBLISH")
            return
        
        try:
            # Create Redis event from client data
            event = Event(
                id=str(uuid.uuid4()),
                type=EventType(event_data.get("type", "broadcast")),
                timestamp=datetime.utcnow(),
                data=event_data.get("data", {}),
                source=f"websocket_{self.connection_id}"
            )
            
            # Publish to Redis
            publisher = redis_manager.get_publisher()
            success = await publisher.publish_event(event)
            
            # Send confirmation
            response = ServerMessage(
                type="publish_result",
                data={
                    "success": success,
                    "event_id": event.id,
                    "message": "Event published successfully" if success else "Failed to publish event"
                },
                timestamp=datetime.utcnow()
            )
            await self.send_message(response)
            
        except ValueError as e:
            await self.send_error(f"Invalid event type: {e}", "INVALID_EVENT_TYPE")
        except Exception as e:
            logger.error(f"Error publishing client event: {e}")
            await self.send_error(f"Error publishing event: {str(e)}", "PUBLISH_ERROR")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection statistics"""
        uptime = datetime.utcnow() - self.connected_at
        return {
            "connection_id": self.connection_id,
            "connected_at": self.connected_at.isoformat(),
            "uptime_seconds": uptime.total_seconds(),
            "subscribed_channels": list(self.subscribed_channels),
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "errors_count": self.errors_count,
            "last_activity": self.last_activity.isoformat(),
            "last_ping": self.last_ping.isoformat(),
            "compression_enabled": self.compression_enabled,
            "is_active": self.is_active,
            "filters": self.event_filters
        }
    
    async def cleanup(self) -> None:
        """Cleanup connection resources"""
        self.is_active = False
        
        if self.subscriber:
            await self.subscriber.stop_listening()
        
        logger.info(f"Cleaned up WebSocket connection {self.connection_id}")


# Global connection registry
active_websocket_connections: Dict[str, WebSocketConnection] = {}


@router.websocket("/")
async def websocket_endpoint(
    websocket: WebSocket,
    channels: str = Query("agents,tasks,metrics", description="Comma-separated list of channels"),
    event_types: Optional[str] = Query(None, description="Comma-separated list of event types to filter"),
    agent_ids: Optional[str] = Query(None, description="Comma-separated list of agent IDs to filter"),
    min_priority: int = Query(1, description="Minimum event priority"),
    compression: bool = Query(False, description="Enable compression for large payloads"),
    buffer_size: int = Query(50, description="Number of recent events to send on connect"),
    redis_manager: RedisConnectionManager = Depends(get_redis_manager)
):
    """WebSocket endpoint for real-time communication"""
    
    connection_id = str(uuid.uuid4())
    await websocket.accept()
    
    # Create connection
    connection = WebSocketConnection(websocket, connection_id)
    connection.compression_enabled = compression
    
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
            await connection.send_error(f"Invalid event type: {e}", "INVALID_EVENT_TYPE")
            await websocket.close(code=1002, reason="Invalid event type")
            return
    
    if agent_ids:
        filters["agent_ids"] = [a.strip() for a in agent_ids.split(",") if a.strip()]
    
    try:
        # Initialize connection
        await connection.initialize(redis_manager, channel_list, filters)
        
        # Register active connection
        active_websocket_connections[connection_id] = connection
        
        # Send connection established message
        welcome_message = ServerMessage(
            type="connection_established",
            data={
                "connection_id": connection_id,
                "server_time": datetime.utcnow().isoformat(),
                "subscribed_channels": channel_list,
                "filters": filters,
                "compression_enabled": compression
            },
            timestamp=datetime.utcnow()
        )
        await connection.send_message(welcome_message)
        
        # Send buffered events if requested
        if buffer_size > 0:
            await _send_buffered_events_ws(connection, redis_manager, buffer_size)
        
        # Start Redis event listener
        listener_task = asyncio.create_task(
            _websocket_event_listener(connection, redis_manager)
        )
        
        # Main message handling loop
        try:
            while connection.is_active:
                # Receive message from client
                try:
                    data = await websocket.receive_text()
                    
                    # Handle compressed messages
                    if connection.compression_enabled:
                        try:
                            # Try to decompress if it looks like compressed data
                            decompressed = gzip.decompress(data.encode('latin-1')).decode()
                            data = decompressed
                        except:
                            # Not compressed, use as-is
                            pass
                    
                    # Parse client message
                    try:
                        message_data = json.loads(data)
                        client_message = ClientMessage(**message_data)
                        
                        await connection.handle_client_message(client_message, redis_manager)
                        
                    except json.JSONDecodeError:
                        await connection.send_error("Invalid JSON format", "INVALID_JSON")
                    except Exception as e:
                        await connection.send_error(f"Invalid message format: {str(e)}", "INVALID_MESSAGE_FORMAT")
                
                except WebSocketDisconnect:
                    logger.info(f"WebSocket client {connection_id} disconnected")
                    break
                except Exception as e:
                    logger.error(f"WebSocket communication error: {e}")
                    break
        
        finally:
            # Cleanup
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass
            
            await connection.cleanup()
            if connection_id in active_websocket_connections:
                del active_websocket_connections[connection_id]

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        await connection.cleanup()
        if connection_id in active_websocket_connections:
            del active_websocket_connections[connection_id]


async def _websocket_event_listener(connection: WebSocketConnection,
                                   redis_manager: RedisConnectionManager) -> None:
    """Listen for Redis events and forward to WebSocket connection"""
    try:
        if connection.subscriber:
            async for event in connection.subscriber.listen_for_events():
                if not connection.is_active:
                    break
                # Event is handled by connection._handle_redis_event
    except Exception as e:
        logger.error(f"WebSocket Redis event listener error: {e}")


async def _send_buffered_events_ws(connection: WebSocketConnection,
                                  redis_manager: RedisConnectionManager,
                                  buffer_size: int) -> None:
    """Send recent buffered events to new WebSocket connection"""
    try:
        for channel in connection.subscribed_channels:
            if connection.subscriber:
                recent_events = await connection.subscriber.get_buffered_events(
                    channel, buffer_size
                )
                
                for event in recent_events[-buffer_size:]:
                    if connection._passes_filters(event):
                        await connection._handle_redis_event(event)
                        
    except Exception as e:
        logger.error(f"Error sending buffered events to WebSocket: {e}")


@router.get("/stats")
async def get_websocket_stats():
    """Get statistics about active WebSocket connections"""
    connection_stats = []
    
    for conn_id, conn in active_websocket_connections.items():
        connection_stats.append(conn.get_stats())
    
    return {
        "active_connections": len(active_websocket_connections),
        "connections": connection_stats,
        "total_messages_sent": sum(conn.messages_sent for conn in active_websocket_connections.values()),
        "total_messages_received": sum(conn.messages_received for conn in active_websocket_connections.values()),
        "total_errors": sum(conn.errors_count for conn in active_websocket_connections.values())
    }


@router.post("/broadcast")
async def broadcast_websocket_message(
    message: str,
    event_type: str = "broadcast",
    priority: int = 2,
    target_connections: Optional[List[str]] = None,
    redis_manager: RedisConnectionManager = Depends(get_redis_manager)
):
    """Broadcast message to WebSocket connections via Redis"""
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
            source="websocket_api_broadcast"
        )
        
        success = await publisher.publish_event(event)
        
        return {
            "success": success,
            "message": "WebSocket broadcast sent" if success else "Failed to send WebSocket broadcast",
            "event_id": event.id,
            "target_connections": len(target_connections) if target_connections else "all"
        }
        
    except Exception as e:
        logger.error(f"WebSocket broadcast failed: {e}")
        raise HTTPException(status_code=500, detail=f"WebSocket broadcast failed: {str(e)}")


# Cleanup function
async def cleanup_websocket_connections():
    """Cleanup all active WebSocket connections"""
    connections_to_cleanup = list(active_websocket_connections.values())
    
    for connection in connections_to_cleanup:
        try:
            await connection.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up WebSocket connection {connection.connection_id}: {e}")
    
    active_websocket_connections.clear()
    logger.info("All WebSocket connections cleaned up")