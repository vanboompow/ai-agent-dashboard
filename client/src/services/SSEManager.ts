/**
 * Robust SSE Manager with reconnection, offline handling, and performance monitoring
 * Handles connection state management and automatic fallback strategies
 */

export interface SSEEvent {
  id?: string;
  event?: string;
  data: any;
  timestamp: string;
  retry?: number;
}

export interface SSEConnectionConfig {
  url: string;
  channels: string[];
  eventTypes?: string[];
  agentIds?: string[];
  minPriority?: number;
  compression?: boolean;
  bufferSize?: number;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatTimeout?: number;
  eventQueueSize?: number;
}

export interface ConnectionStats {
  connectionId: string;
  connectedAt: Date;
  lastHeartbeat: Date;
  reconnectAttempts: number;
  totalEvents: number;
  droppedEvents: number;
  averageLatency: number;
  connectionState: ConnectionState;
}

export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  FAILED = 'failed'
}

export enum EventType {
  AGENT_STATUS = 'agent_status',
  TASK_UPDATE = 'task_update',
  METRICS_DATA = 'metrics_data',
  SYSTEM_ALERT = 'system_alert',
  COLLABORATION = 'collaboration',
  BROADCAST = 'broadcast',
  HEARTBEAT = 'heartbeat',
  PERFORMANCE_ALERT = 'performance_alert',
  LOG_MESSAGE = 'log_message'
}

interface QueuedEvent {
  event: SSEEvent;
  timestamp: Date;
  retryCount: number;
}

type EventCallback = (event: SSEEvent) => void;
type StateChangeCallback = (state: ConnectionState, error?: string) => void;
type StatsCallback = (stats: ConnectionStats) => void;

export class SSEManager {
  private eventSource: EventSource | null = null;
  private config: Required<SSEConnectionConfig>;
  private connectionState: ConnectionState = ConnectionState.DISCONNECTED;
  private reconnectTimer: number | null = null;
  private reconnectAttempts: number = 0;
  private connectionId: string | null = null;
  private lastHeartbeat: Date = new Date();
  private heartbeatTimer: number | null = null;
  
  // Event handling
  private eventCallbacks: Map<string, EventCallback[]> = new Map();
  private stateChangeCallbacks: Set<StateChangeCallback> = new Set();
  private statsCallbacks: Set<StatsCallback> = new Set();
  
  // Offline handling
  private eventQueue: QueuedEvent[] = [];
  private isOnline: boolean = navigator.onLine;
  
  // Performance monitoring
  private stats: ConnectionStats = {
    connectionId: '',
    connectedAt: new Date(),
    lastHeartbeat: new Date(),
    reconnectAttempts: 0,
    totalEvents: 0,
    droppedEvents: 0,
    averageLatency: 0,
    connectionState: ConnectionState.DISCONNECTED
  };
  private latencyMeasurements: number[] = [];
  
  // Compression handling
  private decompressionSupported: boolean = typeof TextDecoder !== 'undefined';

  constructor(config: SSEConnectionConfig) {
    this.config = {
      channels: config.channels,
      eventTypes: config.eventTypes || [],
      agentIds: config.agentIds || [],
      minPriority: config.minPriority || 1,
      compression: config.compression || false,
      bufferSize: config.bufferSize || 50,
      reconnectInterval: config.reconnectInterval || 3000,
      maxReconnectAttempts: config.maxReconnectAttempts || 10,
      heartbeatTimeout: config.heartbeatTimeout || 60000,
      eventQueueSize: config.eventQueueSize || 1000,
      url: config.url
    };

    this.setupNetworkListeners();
    this.stats.connectionState = ConnectionState.DISCONNECTED;
  }

  /**
   * Connect to SSE endpoint
   */
  async connect(): Promise<boolean> {
    if (this.connectionState === ConnectionState.CONNECTED || 
        this.connectionState === ConnectionState.CONNECTING) {
      return true;
    }

    this.updateConnectionState(ConnectionState.CONNECTING);
    
    try {
      const url = this.buildURL();
      console.log(`SSE connecting to: ${url}`);
      
      this.eventSource = new EventSource(url);
      this.setupEventSourceListeners();
      
      // Wait for connection establishment
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('Connection timeout'));
        }, 10000);

        const onOpen = () => {
          clearTimeout(timeout);
          this.eventSource?.removeEventListener('open', onOpen);
          this.eventSource?.removeEventListener('error', onError);
          resolve(true);
        };

        const onError = () => {
          clearTimeout(timeout);
          this.eventSource?.removeEventListener('open', onOpen);
          this.eventSource?.removeEventListener('error', onError);
          reject(new Error('Connection failed'));
        };

        this.eventSource?.addEventListener('open', onOpen);
        this.eventSource?.addEventListener('error', onError);
      });

    } catch (error) {
      console.error('SSE connection error:', error);
      this.handleConnectionError(error instanceof Error ? error.message : 'Unknown error');
      return false;
    }
  }

  /**
   * Disconnect from SSE endpoint
   */
  disconnect(): void {
    this.clearReconnectTimer();
    this.clearHeartbeatTimer();
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
    
    this.updateConnectionState(ConnectionState.DISCONNECTED);
    this.connectionId = null;
  }

  /**
   * Add event listener for specific event type
   */
  addEventListener(eventType: string, callback: EventCallback): void {
    if (!this.eventCallbacks.has(eventType)) {
      this.eventCallbacks.set(eventType, []);
    }
    this.eventCallbacks.get(eventType)!.push(callback);
  }

  /**
   * Remove event listener
   */
  removeEventListener(eventType: string, callback: EventCallback): void {
    const callbacks = this.eventCallbacks.get(eventType);
    if (callbacks) {
      const index = callbacks.indexOf(callback);
      if (index > -1) {
        callbacks.splice(index, 1);
      }
      if (callbacks.length === 0) {
        this.eventCallbacks.delete(eventType);
      }
    }
  }

  /**
   * Add connection state change listener
   */
  onStateChange(callback: StateChangeCallback): () => void {
    this.stateChangeCallbacks.add(callback);
    return () => this.stateChangeCallbacks.delete(callback);
  }

  /**
   * Add stats update listener
   */
  onStatsUpdate(callback: StatsCallback): () => void {
    this.statsCallbacks.add(callback);
    return () => this.statsCallbacks.delete(callback);
  }

  /**
   * Get current connection stats
   */
  getStats(): ConnectionStats {
    return { ...this.stats };
  }

  /**
   * Update configuration
   */
  updateConfig(newConfig: Partial<SSEConnectionConfig>): void {
    const wasConnected = this.connectionState === ConnectionState.CONNECTED;
    
    if (wasConnected) {
      this.disconnect();
    }

    this.config = { ...this.config, ...newConfig };

    if (wasConnected) {
      this.connect();
    }
  }

  /**
   * Manually trigger reconnection
   */
  reconnect(): void {
    this.disconnect();
    this.reconnectAttempts = 0;
    this.connect();
  }

  /**
   * Send queued events (for testing/debugging)
   */
  getQueuedEvents(): QueuedEvent[] {
    return [...this.eventQueue];
  }

  /**
   * Clear event queue
   */
  clearQueue(): void {
    this.eventQueue = [];
  }

  private buildURL(): string {
    const url = new URL(this.config.url);
    
    // Add query parameters
    url.searchParams.set('channels', this.config.channels.join(','));
    
    if (this.config.eventTypes.length > 0) {
      url.searchParams.set('event_types', this.config.eventTypes.join(','));
    }
    
    if (this.config.agentIds.length > 0) {
      url.searchParams.set('agent_ids', this.config.agentIds.join(','));
    }
    
    url.searchParams.set('min_priority', this.config.minPriority.toString());
    url.searchParams.set('compression', this.config.compression.toString());
    url.searchParams.set('buffer_size', this.config.bufferSize.toString());

    return url.toString();
  }

  private setupEventSourceListeners(): void {
    if (!this.eventSource) return;

    this.eventSource.onopen = (event) => {
      console.log('SSE connection opened');
      this.updateConnectionState(ConnectionState.CONNECTED);
      this.reconnectAttempts = 0;
      this.stats.connectedAt = new Date();
      this.startHeartbeatMonitoring();
      this.processQueuedEvents();
    };

    this.eventSource.onerror = (event) => {
      console.error('SSE connection error:', event);
      this.handleConnectionError('Connection error');
    };

    this.eventSource.onmessage = (event) => {
      this.handleMessage(event);
    };

    // Add listeners for specific event types
    for (const eventType of Object.values(EventType)) {
      this.eventSource.addEventListener(eventType, (event) => {
        this.handleMessage(event as MessageEvent);
      });
    }

    // Heartbeat listener
    this.eventSource.addEventListener('heartbeat', (event) => {
      this.handleHeartbeat(event as MessageEvent);
    });
  }

  private handleMessage(event: MessageEvent): void {
    try {
      const startTime = performance.now();
      
      let data = event.data;
      
      // Handle compression
      if (this.config.compression && this.decompressionSupported) {
        try {
          // Check if data appears to be compressed (starts with gzip header)
          if (data.length > 0 && data.charCodeAt(0) === 31 && data.charCodeAt(1) === 139) {
            // This would need a proper gzip decompression library in production
            console.warn('Compressed data received but decompression not fully implemented');
          }
        } catch (error) {
          console.warn('Decompression failed:', error);
        }
      }

      // Parse event data
      const eventData: SSEEvent = {
        id: event.lastEventId,
        event: event.type,
        data: JSON.parse(data),
        timestamp: new Date().toISOString(),
        retry: 3000
      };

      // Update stats
      this.stats.totalEvents++;
      const latency = performance.now() - startTime;
      this.updateLatencyStats(latency);

      // Emit event to callbacks
      this.emitEvent(eventData);

    } catch (error) {
      console.error('Error processing SSE message:', error);
      this.stats.droppedEvents++;
    }
  }

  private handleHeartbeat(event: MessageEvent): void {
    try {
      const heartbeatData = JSON.parse(event.data);
      
      if (heartbeatData.connection_id && !this.connectionId) {
        this.connectionId = heartbeatData.connection_id;
        this.stats.connectionId = this.connectionId;
      }

      this.lastHeartbeat = new Date();
      this.stats.lastHeartbeat = this.lastHeartbeat;
      
      // Reset heartbeat timer
      this.startHeartbeatMonitoring();

    } catch (error) {
      console.error('Error processing heartbeat:', error);
    }
  }

  private emitEvent(event: SSEEvent): void {
    // Emit to specific event type listeners
    const eventType = event.event || 'message';
    const callbacks = this.eventCallbacks.get(eventType);
    
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(event);
        } catch (error) {
          console.error(`Error in event callback for ${eventType}:`, error);
        }
      });
    }

    // Emit to general message listeners
    if (eventType !== 'message') {
      const messageCallbacks = this.eventCallbacks.get('message');
      messageCallbacks?.forEach(callback => {
        try {
          callback(event);
        } catch (error) {
          console.error('Error in message callback:', error);
        }
      });
    }
  }

  private handleConnectionError(error: string): void {
    console.error('SSE connection error:', error);
    
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    if (this.reconnectAttempts < this.config.maxReconnectAttempts) {
      this.updateConnectionState(ConnectionState.RECONNECTING, error);
      this.scheduleReconnect();
    } else {
      this.updateConnectionState(ConnectionState.FAILED, `Max reconnect attempts exceeded: ${error}`);
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    
    // Exponential backoff with jitter
    const baseDelay = this.config.reconnectInterval;
    const exponentialDelay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts), 30000);
    const jitter = Math.random() * 1000;
    const delay = exponentialDelay + jitter;

    console.log(`Scheduling reconnect attempt ${this.reconnectAttempts + 1} in ${delay}ms`);

    this.reconnectTimer = window.setTimeout(() => {
      this.reconnectAttempts++;
      this.stats.reconnectAttempts = this.reconnectAttempts;
      this.connect();
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private startHeartbeatMonitoring(): void {
    this.clearHeartbeatTimer();
    
    this.heartbeatTimer = window.setTimeout(() => {
      const timeSinceHeartbeat = Date.now() - this.lastHeartbeat.getTime();
      
      if (timeSinceHeartbeat > this.config.heartbeatTimeout) {
        console.warn('Heartbeat timeout, reconnecting...');
        this.handleConnectionError('Heartbeat timeout');
      } else {
        // Continue monitoring
        this.startHeartbeatMonitoring();
      }
    }, this.config.heartbeatTimeout);
  }

  private clearHeartbeatTimer(): void {
    if (this.heartbeatTimer) {
      clearTimeout(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private updateConnectionState(state: ConnectionState, error?: string): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.stats.connectionState = state;
      
      // Notify state change listeners
      this.stateChangeCallbacks.forEach(callback => {
        try {
          callback(state, error);
        } catch (err) {
          console.error('Error in state change callback:', err);
        }
      });

      // Update stats listeners
      this.statsCallbacks.forEach(callback => {
        try {
          callback(this.getStats());
        } catch (err) {
          console.error('Error in stats callback:', err);
        }
      });
    }
  }

  private updateLatencyStats(latency: number): void {
    this.latencyMeasurements.push(latency);
    
    // Keep only last 100 measurements
    if (this.latencyMeasurements.length > 100) {
      this.latencyMeasurements.shift();
    }

    // Calculate average latency
    const sum = this.latencyMeasurements.reduce((a, b) => a + b, 0);
    this.stats.averageLatency = sum / this.latencyMeasurements.length;
  }

  private setupNetworkListeners(): void {
    window.addEventListener('online', () => {
      console.log('Network came back online');
      this.isOnline = true;
      
      if (this.connectionState === ConnectionState.FAILED || 
          this.connectionState === ConnectionState.DISCONNECTED) {
        this.reconnect();
      }
    });

    window.addEventListener('offline', () => {
      console.log('Network went offline');
      this.isOnline = false;
      this.updateConnectionState(ConnectionState.DISCONNECTED, 'Network offline');
    });

    // Handle page visibility changes
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        // Page is hidden, may want to reduce activity
        console.log('Page hidden, SSE connection maintained');
      } else {
        // Page is visible, ensure connection is active
        console.log('Page visible, checking SSE connection');
        if (this.connectionState === ConnectionState.DISCONNECTED && this.isOnline) {
          this.connect();
        }
      }
    });
  }

  private processQueuedEvents(): void {
    if (this.eventQueue.length === 0) return;

    console.log(`Processing ${this.eventQueue.length} queued events`);

    // Process events in order
    const eventsToProcess = [...this.eventQueue];
    this.eventQueue = [];

    eventsToProcess.forEach(queuedEvent => {
      this.emitEvent(queuedEvent.event);
    });
  }

  // Cleanup method for component unmounting
  destroy(): void {
    this.disconnect();
    this.eventCallbacks.clear();
    this.stateChangeCallbacks.clear();
    this.statsCallbacks.clear();
    
    window.removeEventListener('online', this.setupNetworkListeners);
    window.removeEventListener('offline', this.setupNetworkListeners);
    document.removeEventListener('visibilitychange', this.setupNetworkListeners);
  }
}

// Factory function for creating SSE manager instances
export function createSSEManager(config: SSEConnectionConfig): SSEManager {
  return new SSEManager(config);
}

// Utility functions for event type checking
export function isAgentEvent(event: SSEEvent): boolean {
  return event.event === EventType.AGENT_STATUS;
}

export function isTaskEvent(event: SSEEvent): boolean {
  return event.event === EventType.TASK_UPDATE;
}

export function isMetricsEvent(event: SSEEvent): boolean {
  return event.event === EventType.METRICS_DATA;
}

export function isSystemAlert(event: SSEEvent): boolean {
  return event.event === EventType.SYSTEM_ALERT;
}

export function isBroadcast(event: SSEEvent): boolean {
  return event.event === EventType.BROADCAST;
}

// Performance monitoring utilities
export class SSEPerformanceMonitor {
  private static instance: SSEPerformanceMonitor;
  private managers: Map<string, SSEManager> = new Map();
  private metricsInterval: number | null = null;

  static getInstance(): SSEPerformanceMonitor {
    if (!SSEPerformanceMonitor.instance) {
      SSEPerformanceMonitor.instance = new SSEPerformanceMonitor();
    }
    return SSEPerformanceMonitor.instance;
  }

  registerManager(name: string, manager: SSEManager): void {
    this.managers.set(name, manager);
    this.startMetricsCollection();
  }

  unregisterManager(name: string): void {
    this.managers.delete(name);
    if (this.managers.size === 0) {
      this.stopMetricsCollection();
    }
  }

  getGlobalStats(): Record<string, ConnectionStats> {
    const stats: Record<string, ConnectionStats> = {};
    this.managers.forEach((manager, name) => {
      stats[name] = manager.getStats();
    });
    return stats;
  }

  private startMetricsCollection(): void {
    if (this.metricsInterval) return;

    this.metricsInterval = window.setInterval(() => {
      const stats = this.getGlobalStats();
      
      // Log performance metrics for debugging
      console.debug('SSE Performance Stats:', {
        totalConnections: Object.keys(stats).length,
        connectedCount: Object.values(stats).filter(s => s.connectionState === ConnectionState.CONNECTED).length,
        averageLatency: Object.values(stats).reduce((sum, s) => sum + s.averageLatency, 0) / Object.keys(stats).length,
        totalEvents: Object.values(stats).reduce((sum, s) => sum + s.totalEvents, 0),
        droppedEvents: Object.values(stats).reduce((sum, s) => sum + s.droppedEvents, 0)
      });
    }, 30000); // Every 30 seconds
  }

  private stopMetricsCollection(): void {
    if (this.metricsInterval) {
      clearInterval(this.metricsInterval);
      this.metricsInterval = null;
    }
  }
}