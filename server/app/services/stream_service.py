"""Stream service for handling real-time events."""
import json
from typing import Dict, Any, List, AsyncGenerator
from datetime import datetime, timezone


class StreamService:
    """Service class for streaming operations."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
    
    async def publish_agent_update(self, agent_data: Dict[str, Any]) -> None:
        """Publish agent update event."""
        if self.redis_client:
            event = {
                "event_type": "agent_update",
                "data": agent_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await self.redis_client.publish("agent_updates", json.dumps(event))
    
    async def publish_task_update(self, task_data: Dict[str, Any]) -> None:
        """Publish task update event."""
        if self.redis_client:
            event = {
                "event_type": "task_update",
                "data": task_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await self.redis_client.publish("task_updates", json.dumps(event))
    
    async def publish_metrics_update(self, metrics_data: Dict[str, Any]) -> None:
        """Publish metrics update event."""
        if self.redis_client:
            event = {
                "event_type": "metrics_update",
                "data": metrics_data,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            await self.redis_client.publish("metrics_updates", json.dumps(event))
    
    async def subscribe_to_updates(self, channels: List[str]) -> None:
        """Subscribe to update channels."""
        if self.redis_client:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(*channels)
    
    async def get_stream_events(self, channels: List[str]) -> AsyncGenerator[Dict[str, Any], None]:
        """Get streaming events from subscribed channels."""
        if self.redis_client:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(*channels)
            
            while True:
                message = await pubsub.get_message()
                if message and message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        yield data
                    except json.JSONDecodeError:
                        continue