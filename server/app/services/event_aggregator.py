"""
Event Aggregation Service for batching, deduplication, and priority handling
Reduces network traffic and improves performance for high-frequency events
"""
import asyncio
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Callable, Any
import heapq
from dataclasses import dataclass, field
from enum import Enum

from .redis_pubsub import Event, EventType, EventPriority

logger = logging.getLogger(__name__)


class AggregationStrategy(str, Enum):
    """Different strategies for aggregating events"""
    LATEST_ONLY = "latest_only"          # Keep only the latest event per key
    SLIDING_WINDOW = "sliding_window"     # Aggregate over time windows
    COUNT_BASED = "count_based"          # Aggregate after N events
    PRIORITY_QUEUE = "priority_queue"     # Prioritize high-priority events
    NO_AGGREGATION = "no_aggregation"    # Pass through immediately


@dataclass
class AggregationConfig:
    """Configuration for event aggregation"""
    strategy: AggregationStrategy
    window_duration: timedelta = field(default_factory=lambda: timedelta(seconds=1))
    max_batch_size: int = 50
    max_delay: timedelta = field(default_factory=lambda: timedelta(seconds=5))
    dedup_key_fields: List[str] = field(default_factory=list)
    merge_data_fields: List[str] = field(default_factory=list)


@dataclass
class PriorityEvent:
    """Wrapper for events in priority queue"""
    priority: int
    timestamp: datetime
    event: Event
    
    def __lt__(self, other):
        # Higher priority events should come first (lower number = higher priority)
        if self.priority != other.priority:
            return self.priority < other.priority
        # For same priority, older events come first
        return self.timestamp < other.timestamp


class SlidingWindow:
    """Sliding window implementation for time-based aggregation"""
    
    def __init__(self, duration: timedelta, max_size: int = 1000):
        self.duration = duration
        self.max_size = max_size
        self.events: deque = deque()
    
    def add_event(self, event: Event) -> None:
        """Add event to sliding window"""
        self.events.append((event.timestamp, event))
        
        # Remove old events outside window
        cutoff = datetime.utcnow() - self.duration
        while self.events and self.events[0][0] < cutoff:
            self.events.popleft()
        
        # Prevent unbounded growth
        if len(self.events) > self.max_size:
            self.events.popleft()
    
    def get_events(self) -> List[Event]:
        """Get all events in current window"""
        return [event for _, event in self.events]
    
    def get_aggregated_data(self) -> Dict[str, Any]:
        """Get aggregated metrics from window"""
        if not self.events:
            return {}
        
        events = self.get_events()
        
        # Common aggregations
        count = len(events)
        event_types = defaultdict(int)
        for event in events:
            event_types[event.type] += 1
        
        return {
            "count": count,
            "event_types": dict(event_types),
            "window_start": self.events[0][0] if self.events else None,
            "window_end": self.events[-1][0] if self.events else None,
        }


class EventDeduplicator:
    """Handles event deduplication based on configurable keys"""
    
    def __init__(self, key_fields: List[str], ttl: timedelta = timedelta(minutes=5)):
        self.key_fields = key_fields
        self.ttl = ttl
        self.seen_events: Dict[str, datetime] = {}
    
    def generate_key(self, event: Event) -> str:
        """Generate deduplication key from event"""
        key_parts = []
        for field in self.key_fields:
            if field in event.data:
                key_parts.append(str(event.data[field]))
            elif hasattr(event, field):
                key_parts.append(str(getattr(event, field)))
        
        return f"{event.type}:{':'.join(key_parts)}"
    
    def is_duplicate(self, event: Event) -> bool:
        """Check if event is a duplicate"""
        if not self.key_fields:
            return False
        
        key = self.generate_key(event)
        now = datetime.utcnow()
        
        # Clean up old entries
        expired_keys = [k for k, timestamp in self.seen_events.items() 
                       if now - timestamp > self.ttl]
        for k in expired_keys:
            del self.seen_events[k]
        
        if key in self.seen_events:
            return True
        
        self.seen_events[key] = now
        return False
    
    def clear(self) -> None:
        """Clear deduplication cache"""
        self.seen_events.clear()


class EventBatch:
    """Container for batched events"""
    
    def __init__(self, event_type: EventType, config: AggregationConfig):
        self.event_type = event_type
        self.config = config
        self.events: List[Event] = []
        self.created_at = datetime.utcnow()
        self.last_updated = datetime.utcnow()
    
    def add_event(self, event: Event) -> None:
        """Add event to batch"""
        self.events.append(event)
        self.last_updated = datetime.utcnow()
    
    def should_flush(self) -> bool:
        """Check if batch should be flushed"""
        now = datetime.utcnow()
        
        # Check max batch size
        if len(self.events) >= self.config.max_batch_size:
            return True
        
        # Check max delay
        if now - self.created_at >= self.config.max_delay:
            return True
        
        # Check window duration for sliding window strategy
        if (self.config.strategy == AggregationStrategy.SLIDING_WINDOW and 
            now - self.last_updated >= self.config.window_duration):
            return True
        
        return False
    
    def create_aggregated_event(self) -> Event:
        """Create single aggregated event from batch"""
        if not self.events:
            raise ValueError("Cannot create aggregated event from empty batch")
        
        if len(self.events) == 1:
            return self.events[0]
        
        # Use latest event as base
        base_event = max(self.events, key=lambda e: e.timestamp)
        
        # Aggregate data based on strategy
        aggregated_data = self._aggregate_data()
        
        return Event(
            id=f"aggregated_{base_event.id}",
            type=self.event_type,
            priority=max(e.priority for e in self.events),
            timestamp=datetime.utcnow(),
            data=aggregated_data,
            source=f"aggregator_{base_event.source}",
        )
    
    def _aggregate_data(self) -> Dict[str, Any]:
        """Aggregate data from all events in batch"""
        if len(self.events) == 1:
            return self.events[0].data
        
        aggregated = {
            "batch_size": len(self.events),
            "time_span": {
                "start": min(e.timestamp for e in self.events),
                "end": max(e.timestamp for e in self.events),
            },
            "event_ids": [e.id for e in self.events],
        }
        
        # Merge specified fields
        for field in self.config.merge_data_fields:
            values = []
            for event in self.events:
                if field in event.data:
                    values.append(event.data[field])
            
            if values:
                if isinstance(values[0], (int, float)):
                    # Numeric fields - calculate statistics
                    aggregated[field] = {
                        "sum": sum(values),
                        "avg": sum(values) / len(values),
                        "min": min(values),
                        "max": max(values),
                        "count": len(values),
                    }
                else:
                    # Non-numeric fields - keep all unique values
                    aggregated[field] = list(set(values))
        
        # Include latest data for non-merge fields
        latest_event = max(self.events, key=lambda e: e.timestamp)
        for key, value in latest_event.data.items():
            if key not in aggregated:
                aggregated[key] = value
        
        return aggregated


class EventAggregator:
    """Main event aggregation service"""
    
    def __init__(self):
        self.batches: Dict[EventType, EventBatch] = {}
        self.sliding_windows: Dict[EventType, SlidingWindow] = {}
        self.priority_queue: List[PriorityEvent] = []
        self.deduplicators: Dict[EventType, EventDeduplicator] = {}
        self.configs: Dict[EventType, AggregationConfig] = {}
        self.output_handlers: List[Callable[[Event], None]] = []
        self._running = False
        self._flush_task = None
    
    def configure_event_type(self, event_type: EventType, config: AggregationConfig) -> None:
        """Configure aggregation for specific event type"""
        self.configs[event_type] = config
        
        # Initialize deduplicator if needed
        if config.dedup_key_fields:
            self.deduplicators[event_type] = EventDeduplicator(
                config.dedup_key_fields,
                ttl=config.max_delay * 2  # Keep dedup cache longer than max delay
            )
        
        # Initialize sliding window if needed
        if config.strategy == AggregationStrategy.SLIDING_WINDOW:
            self.sliding_windows[event_type] = SlidingWindow(
                config.window_duration,
                config.max_batch_size * 2
            )
        
        logger.info(f"Configured aggregation for {event_type}: {config.strategy}")
    
    def add_output_handler(self, handler: Callable[[Event], None]) -> None:
        """Add handler for processed events"""
        self.output_handlers.append(handler)
    
    def remove_output_handler(self, handler: Callable) -> None:
        """Remove event handler"""
        if handler in self.output_handlers:
            self.output_handlers.remove(handler)
    
    async def process_event(self, event: Event) -> None:
        """Process incoming event through aggregation pipeline"""
        try:
            config = self.configs.get(event.type)
            if not config:
                # No aggregation configured - pass through
                await self._output_event(event)
                return
            
            # Check for duplicates
            deduplicator = self.deduplicators.get(event.type)
            if deduplicator and deduplicator.is_duplicate(event):
                logger.debug(f"Dropping duplicate event: {event.id}")
                return
            
            # Handle different aggregation strategies
            if config.strategy == AggregationStrategy.NO_AGGREGATION:
                await self._output_event(event)
            
            elif config.strategy == AggregationStrategy.LATEST_ONLY:
                await self._handle_latest_only(event, config)
            
            elif config.strategy == AggregationStrategy.SLIDING_WINDOW:
                await self._handle_sliding_window(event, config)
            
            elif config.strategy == AggregationStrategy.COUNT_BASED:
                await self._handle_count_based(event, config)
            
            elif config.strategy == AggregationStrategy.PRIORITY_QUEUE:
                await self._handle_priority_queue(event, config)
            
        except Exception as e:
            logger.error(f"Error processing event {event.id}: {e}")
            # Fall back to direct output
            await self._output_event(event)
    
    async def _handle_latest_only(self, event: Event, config: AggregationConfig) -> None:
        """Handle latest-only aggregation strategy"""
        # Simply replace any existing batch with single event
        batch = EventBatch(event.type, config)
        batch.add_event(event)
        self.batches[event.type] = batch
        
        # Check if should flush immediately
        if batch.should_flush():
            await self._flush_batch(event.type)
    
    async def _handle_sliding_window(self, event: Event, config: AggregationConfig) -> None:
        """Handle sliding window aggregation strategy"""
        window = self.sliding_windows[event.type]
        window.add_event(event)
        
        # Get or create batch
        if event.type not in self.batches:
            self.batches[event.type] = EventBatch(event.type, config)
        
        batch = self.batches[event.type]
        batch.add_event(event)
        
        if batch.should_flush():
            await self._flush_batch(event.type)
    
    async def _handle_count_based(self, event: Event, config: AggregationConfig) -> None:
        """Handle count-based aggregation strategy"""
        # Get or create batch
        if event.type not in self.batches:
            self.batches[event.type] = EventBatch(event.type, config)
        
        batch = self.batches[event.type]
        batch.add_event(event)
        
        if batch.should_flush():
            await self._flush_batch(event.type)
    
    async def _handle_priority_queue(self, event: Event, config: AggregationConfig) -> None:
        """Handle priority queue aggregation strategy"""
        priority_event = PriorityEvent(
            priority=event.priority.value,
            timestamp=event.timestamp,
            event=event
        )
        heapq.heappush(self.priority_queue, priority_event)
        
        # Flush high priority events immediately
        if event.priority >= EventPriority.HIGH:
            await self._output_event(event)
            return
        
        # Batch lower priority events
        if event.type not in self.batches:
            self.batches[event.type] = EventBatch(event.type, config)
        
        batch = self.batches[event.type]
        batch.add_event(event)
        
        if batch.should_flush():
            await self._flush_batch(event.type)
    
    async def _flush_batch(self, event_type: EventType) -> None:
        """Flush batch and output aggregated event"""
        batch = self.batches.pop(event_type, None)
        if not batch or not batch.events:
            return
        
        try:
            aggregated_event = batch.create_aggregated_event()
            await self._output_event(aggregated_event)
            
            logger.debug(f"Flushed batch for {event_type}: {len(batch.events)} events")
            
        except Exception as e:
            logger.error(f"Error flushing batch for {event_type}: {e}")
            # Fall back to outputting individual events
            for event in batch.events:
                await self._output_event(event)
    
    async def _output_event(self, event: Event) -> None:
        """Output processed event to handlers"""
        for handler in self.output_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Output handler failed: {e}")
    
    async def start_periodic_flush(self, interval: float = 1.0) -> None:
        """Start periodic batch flushing"""
        self._running = True
        self._flush_task = asyncio.create_task(self._periodic_flush_loop(interval))
        logger.info(f"Started periodic flush with {interval}s interval")
    
    async def stop_periodic_flush(self) -> None:
        """Stop periodic batch flushing"""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
            self._flush_task = None
        
        # Flush any remaining batches
        await self.flush_all_batches()
        logger.info("Stopped periodic flush")
    
    async def _periodic_flush_loop(self, interval: float) -> None:
        """Periodic flush loop"""
        while self._running:
            try:
                await asyncio.sleep(interval)
                await self._check_and_flush_expired_batches()
                await self._flush_priority_queue()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic flush loop: {e}")
    
    async def _check_and_flush_expired_batches(self) -> None:
        """Check and flush expired batches"""
        expired_types = []
        for event_type, batch in self.batches.items():
            if batch.should_flush():
                expired_types.append(event_type)
        
        for event_type in expired_types:
            await self._flush_batch(event_type)
    
    async def _flush_priority_queue(self) -> None:
        """Flush accumulated events from priority queue"""
        events_to_flush = []
        
        # Get events that should be flushed (older than max_delay)
        cutoff = datetime.utcnow() - timedelta(seconds=1)  # 1 second delay for priority queue
        
        while self.priority_queue:
            priority_event = self.priority_queue[0]
            if priority_event.timestamp < cutoff:
                heapq.heappop(self.priority_queue)
                events_to_flush.append(priority_event.event)
            else:
                break
        
        # Output accumulated events
        for event in events_to_flush:
            await self._output_event(event)
    
    async def flush_all_batches(self) -> None:
        """Flush all pending batches"""
        event_types = list(self.batches.keys())
        for event_type in event_types:
            await self._flush_batch(event_type)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregator statistics"""
        return {
            "pending_batches": len(self.batches),
            "priority_queue_size": len(self.priority_queue),
            "configured_types": list(self.configs.keys()),
            "batch_sizes": {str(k): len(v.events) for k, v in self.batches.items()},
            "running": self._running,
        }


# Default aggregation configurations
DEFAULT_AGGREGATION_CONFIGS = {
    EventType.AGENT_STATUS: AggregationConfig(
        strategy=AggregationStrategy.LATEST_ONLY,
        max_delay=timedelta(seconds=2),
        dedup_key_fields=["agent_id"]
    ),
    EventType.TASK_UPDATE: AggregationConfig(
        strategy=AggregationStrategy.COUNT_BASED,
        max_batch_size=20,
        max_delay=timedelta(seconds=3),
        dedup_key_fields=["task_id"]
    ),
    EventType.METRICS_DATA: AggregationConfig(
        strategy=AggregationStrategy.SLIDING_WINDOW,
        window_duration=timedelta(seconds=5),
        max_batch_size=10,
        max_delay=timedelta(seconds=5),
        merge_data_fields=["tokensPerSecond", "costPerSecondUSD"]
    ),
    EventType.SYSTEM_ALERT: AggregationConfig(
        strategy=AggregationStrategy.PRIORITY_QUEUE,
        max_delay=timedelta(seconds=1),
        max_batch_size=5
    ),
    EventType.COLLABORATION: AggregationConfig(
        strategy=AggregationStrategy.LATEST_ONLY,
        max_delay=timedelta(seconds=1),
        dedup_key_fields=["user_id", "target"]
    ),
    EventType.BROADCAST: AggregationConfig(
        strategy=AggregationStrategy.NO_AGGREGATION
    ),
    EventType.HEARTBEAT: AggregationConfig(
        strategy=AggregationStrategy.LATEST_ONLY,
        max_delay=timedelta(seconds=10),
        dedup_key_fields=["source"]
    ),
    EventType.PERFORMANCE_ALERT: AggregationConfig(
        strategy=AggregationStrategy.PRIORITY_QUEUE,
        max_delay=timedelta(seconds=2),
        max_batch_size=3
    ),
    EventType.LOG_MESSAGE: AggregationConfig(
        strategy=AggregationStrategy.COUNT_BASED,
        max_batch_size=50,
        max_delay=timedelta(seconds=10)
    ),
}


def create_default_aggregator() -> EventAggregator:
    """Create event aggregator with default configurations"""
    aggregator = EventAggregator()
    
    for event_type, config in DEFAULT_AGGREGATION_CONFIGS.items():
        aggregator.configure_event_type(event_type, config)
    
    return aggregator