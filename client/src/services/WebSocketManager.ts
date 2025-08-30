/**
 * WebSocket Manager for bidirectional real-time communication
 * Provides fallback when SSE is not available or reliable
 */

export interface WebSocketMessage {
  id?: string;
  type: string;
  data: any;
  timestamp?: string;
}

export interface WebSocketConfig {
  url: string;
  channels: string[];
  eventTypes?: string[];
  agentIds?: string[];
  minPriority?: number;
  compression?: boolean;
  bufferSize?: number;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  pingInterval?: number;
}

export interface WebSocketStats {
  connectionId: string;
  connectedAt: Date;
  messagesSent: number;
  messagesReceived: number;
  reconnectAttempts: number;
  lastPing: Date;
  averageLatency: number;
  connectionState: WebSocketState;
}

export enum WebSocketState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING',
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  FAILED = 'FAILED'
}

type MessageHandler = (message: WebSocketMessage) => void;
type StateChangeHandler = (state: WebSocketState, error?: string) => void;
type StatsHandler = (stats: WebSocketStats) => void;

interface PendingMessage {
  message: WebSocketMessage;
  timestamp: Date;
  retryCount: number;
  resolve: (value: boolean) => void;
  reject: (error: Error) => void;
}

export class WebSocketManager {
  private websocket: WebSocket | null = null;
  private config: Required<WebSocketConfig>;
  private connectionState: WebSocketState = WebSocketState.DISCONNECTED;
  private reconnectTimer: number | null = null;
  private pingTimer: number | null = null;
  private reconnectAttempts: number = 0;
  
  // Connection info
  private connectionId: string = '';
  private connectedAt: Date = new Date();
  private lastPing: Date = new Date();
  
  // Message handling
  private messageHandlers: Map<string, MessageHandler[]> = new Map();
  private stateChangeHandlers: Set<StateChangeHandler> = new Set();
  private statsHandlers: Set<StatsHandler> = new Set();
  
  // Pending messages (for offline support)
  private pendingMessages: PendingMessage[] = [];
  private messageQueue: WebSocketMessage[] = [];
  
  // Stats tracking
  private stats: WebSocketStats = {
    connectionId: '',
    connectedAt: new Date(),
    messagesSent: 0,
    messagesReceived: 0,
    reconnectAttempts: 0,
    lastPing: new Date(),
    averageLatency: 0,
    connectionState: WebSocketState.DISCONNECTED
  };
  private latencyMeasurements: number[] = [];
  
  // Compression support
  private compressionSupported: boolean = typeof TextEncoder !== 'undefined';

  constructor(config: WebSocketConfig) {
    this.config = {
      url: config.url,
      channels: config.channels,
      eventTypes: config.eventTypes || [],
      agentIds: config.agentIds || [],
      minPriority: config.minPriority || 1,
      compression: config.compression || false,
      bufferSize: config.bufferSize || 50,
      reconnectInterval: config.reconnectInterval || 3000,
      maxReconnectAttempts: config.maxReconnectAttempts || 10,
      pingInterval: config.pingInterval || 30000
    };

    this.stats.connectionState = WebSocketState.DISCONNECTED;
  }

  /**
   * Connect to WebSocket endpoint
   */
  async connect(): Promise<boolean> {
    if (this.connectionState === WebSocketState.CONNECTED || 
        this.connectionState === WebSocketState.CONNECTING) {
      return true;
    }

    this.updateConnectionState(WebSocketState.CONNECTING);
    
    try {
      const url = this.buildWebSocketURL();
      console.log(`WebSocket connecting to: ${url}`);
      
      this.websocket = new WebSocket(url);
      this.setupWebSocketListeners();
      
      // Wait for connection establishment
      return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
          reject(new Error('WebSocket connection timeout'));
        }, 10000);

        const onOpen = () => {
          clearTimeout(timeout);
          resolve(true);
        };

        const onError = (error: Event) => {
          clearTimeout(timeout);
          reject(new Error(`WebSocket connection failed: ${error}`));
        };

        if (this.websocket) {
          this.websocket.addEventListener('open', onOpen, { once: true });
          this.websocket.addEventListener('error', onError, { once: true });
        }
      });

    } catch (error) {
      console.error('WebSocket connection error:', error);
      this.handleConnectionError(error instanceof Error ? error.message : 'Unknown error');
      return false;
    }
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    this.clearReconnectTimer();
    this.clearPingTimer();
    
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    
    this.updateConnectionState(WebSocketState.DISCONNECTED);
    this.connectionId = '';
  }

  /**
   * Send message to server
   */
  async sendMessage(message: WebSocketMessage): Promise<boolean> {
    return new Promise((resolve, reject) => {
      if (this.connectionState !== WebSocketState.CONNECTED) {
        // Queue message for later sending
        const pendingMessage: PendingMessage = {
          message,
          timestamp: new Date(),
          retryCount: 0,
          resolve,
          reject
        };
        this.pendingMessages.push(pendingMessage);
        
        // Try to connect if not connecting
        if (this.connectionState === WebSocketState.DISCONNECTED) {
          this.connect();
        }
        return;
      }

      try {
        const messageJson = JSON.stringify(message);
        
        if (this.websocket) {
          // Apply compression if enabled and supported
          if (this.config.compression && this.compressionSupported && messageJson.length > 1024) {
            const encoder = new TextEncoder();
            const data = encoder.encode(messageJson);
            // In a real implementation, you'd use a compression library here
            this.websocket.send(data);
          } else {
            this.websocket.send(messageJson);
          }
          
          this.stats.messagesSent++;
          resolve(true);
        } else {
          reject(new Error('WebSocket not connected'));
        }
      } catch (error) {
        console.error('Error sending WebSocket message:', error);
        reject(error);
      }
    });
  }

  /**
   * Subscribe to channels
   */
  async subscribe(channels: string[], filters: any = {}): Promise<boolean> {
    const message: WebSocketMessage = {
      type: 'subscribe',
      data: {
        channels,
        filters: {
          ...filters,
          event_types: this.config.eventTypes,
          agent_ids: this.config.agentIds,
          min_priority: this.config.minPriority
        }
      }
    };

    return this.sendMessage(message);
  }

  /**
   * Unsubscribe from channels
   */
  async unsubscribe(channels: string[]): Promise<boolean> {
    const message: WebSocketMessage = {
      type: 'unsubscribe',
      data: { channels }
    };

    return this.sendMessage(message);
  }

  /**
   * Update configuration
   */
  async configure(config: any): Promise<boolean> {
    const message: WebSocketMessage = {
      type: 'configure',
      data: { config }
    };

    // Update local config
    Object.assign(this.config, config);
    
    return this.sendMessage(message);
  }

  /**
   * Publish event to server
   */
  async publishEvent(eventType: string, data: any): Promise<boolean> {
    const message: WebSocketMessage = {
      type: 'publish',
      data: {
        event: {
          type: eventType,
          data: data
        }
      }
    };

    return this.sendMessage(message);
  }

  /**
   * Send ping to server
   */
  async ping(): Promise<number> {
    const startTime = performance.now();
    const pingId = Date.now().toString();
    
    const message: WebSocketMessage = {
      type: 'ping',
      data: { id: pingId }
    };

    return new Promise((resolve, reject) => {
      // Set up pong listener
      const pongHandler = (msg: WebSocketMessage) => {
        if (msg.type === 'pong' && msg.data.ping_id === pingId) {
          const latency = performance.now() - startTime;
          this.updateLatencyStats(latency);
          this.removeMessageHandler('pong', pongHandler);
          resolve(latency);
        }
      };

      this.addMessageHandler('pong', pongHandler);

      // Send ping
      this.sendMessage(message).catch(reject);

      // Timeout after 5 seconds
      setTimeout(() => {
        this.removeMessageHandler('pong', pongHandler);
        reject(new Error('Ping timeout'));
      }, 5000);
    });
  }

  /**
   * Add message handler
   */
  addMessageHandler(messageType: string, handler: MessageHandler): void {
    if (!this.messageHandlers.has(messageType)) {
      this.messageHandlers.set(messageType, []);
    }
    this.messageHandlers.get(messageType)!.push(handler);
  }

  /**
   * Remove message handler
   */
  removeMessageHandler(messageType: string, handler: MessageHandler): void {
    const handlers = this.messageHandlers.get(messageType);
    if (handlers) {
      const index = handlers.indexOf(handler);
      if (index > -1) {
        handlers.splice(index, 1);
      }
      if (handlers.length === 0) {
        this.messageHandlers.delete(messageType);
      }
    }
  }

  /**
   * Add state change handler
   */
  onStateChange(handler: StateChangeHandler): () => void {
    this.stateChangeHandlers.add(handler);
    return () => this.stateChangeHandlers.delete(handler);
  }

  /**
   * Add stats handler
   */
  onStatsUpdate(handler: StatsHandler): () => void {
    this.statsHandlers.add(handler);
    return () => this.statsHandlers.delete(handler);
  }

  /**
   * Get current stats
   */
  getStats(): WebSocketStats {
    return { ...this.stats };
  }

  /**
   * Reconnect manually
   */
  reconnect(): void {
    this.disconnect();
    this.reconnectAttempts = 0;
    this.connect();
  }

  private buildWebSocketURL(): string {
    const url = new URL(this.config.url);
    
    // Convert HTTP(S) to WS(S)
    if (url.protocol === 'http:') {
      url.protocol = 'ws:';
    } else if (url.protocol === 'https:') {
      url.protocol = 'wss:';
    }
    
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

  private setupWebSocketListeners(): void {
    if (!this.websocket) return;

    this.websocket.onopen = (event) => {
      console.log('WebSocket connection opened');
      this.updateConnectionState(WebSocketState.CONNECTED);
      this.reconnectAttempts = 0;
      this.connectedAt = new Date();
      this.stats.connectedAt = this.connectedAt;
      this.startPingMonitoring();
      this.processPendingMessages();
    };

    this.websocket.onclose = (event) => {
      console.log('WebSocket connection closed:', event.code, event.reason);
      this.handleConnectionClosed(event.code, event.reason);
    };

    this.websocket.onerror = (event) => {
      console.error('WebSocket error:', event);
      this.handleConnectionError('WebSocket error');
    };

    this.websocket.onmessage = (event) => {
      this.handleMessage(event);
    };
  }

  private handleMessage(event: MessageEvent): void {
    try {
      let data = event.data;
      
      // Handle compressed messages
      if (this.config.compression && data instanceof ArrayBuffer) {
        // Decompress if needed (would need compression library)
        const decoder = new TextDecoder();
        data = decoder.decode(data);
      }

      const message: WebSocketMessage = JSON.parse(data);
      this.stats.messagesReceived++;
      
      // Handle specific message types
      this.handleSpecificMessage(message);
      
      // Emit to handlers
      this.emitMessage(message);

    } catch (error) {
      console.error('Error processing WebSocket message:', error);
    }
  }

  private handleSpecificMessage(message: WebSocketMessage): void {
    switch (message.type) {
      case 'connection_established':
        this.connectionId = message.data.connection_id;
        this.stats.connectionId = this.connectionId;
        console.log(`WebSocket connection established: ${this.connectionId}`);
        break;

      case 'pong':
        this.lastPing = new Date();
        this.stats.lastPing = this.lastPing;
        break;

      case 'error':
        console.error('WebSocket server error:', message.data);
        break;

      case 'subscription_updated':
        console.log('Subscription updated:', message.data);
        break;

      case 'configuration_updated':
        console.log('Configuration updated:', message.data);
        break;

      case 'publish_result':
        console.log('Publish result:', message.data);
        break;

      case 'event':
        // Regular event message - will be handled by registered handlers
        break;

      default:
        console.log('Unknown message type:', message.type);
    }
  }

  private emitMessage(message: WebSocketMessage): void {
    // Emit to specific message type handlers
    const handlers = this.messageHandlers.get(message.type);
    if (handlers) {
      handlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error(`Error in WebSocket handler for ${message.type}:`, error);
        }
      });
    }

    // Emit to general message handlers
    const generalHandlers = this.messageHandlers.get('message');
    if (generalHandlers && message.type !== 'message') {
      generalHandlers.forEach(handler => {
        try {
          handler(message);
        } catch (error) {
          console.error('Error in general WebSocket handler:', error);
        }
      });
    }
  }

  private handleConnectionClosed(code: number, reason: string): void {
    this.clearPingTimer();
    
    if (code === 1000) {
      // Normal closure
      this.updateConnectionState(WebSocketState.DISCONNECTED);
    } else {
      // Abnormal closure, try to reconnect
      this.handleConnectionError(`Connection closed: ${code} ${reason}`);
    }
  }

  private handleConnectionError(error: string): void {
    console.error('WebSocket error:', error);
    
    this.websocket = null;
    
    if (this.reconnectAttempts < this.config.maxReconnectAttempts) {
      this.updateConnectionState(WebSocketState.RECONNECTING, error);
      this.scheduleReconnect();
    } else {
      this.updateConnectionState(WebSocketState.FAILED, `Max reconnect attempts exceeded: ${error}`);
    }
  }

  private scheduleReconnect(): void {
    this.clearReconnectTimer();
    
    // Exponential backoff with jitter
    const baseDelay = this.config.reconnectInterval;
    const exponentialDelay = Math.min(baseDelay * Math.pow(2, this.reconnectAttempts), 30000);
    const jitter = Math.random() * 1000;
    const delay = exponentialDelay + jitter;

    console.log(`Scheduling WebSocket reconnect attempt ${this.reconnectAttempts + 1} in ${delay}ms`);

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

  private startPingMonitoring(): void {
    this.clearPingTimer();
    
    this.pingTimer = window.setInterval(async () => {
      try {
        await this.ping();
      } catch (error) {
        console.warn('Ping failed:', error);
        // Could trigger reconnection if multiple pings fail
      }
    }, this.config.pingInterval);
  }

  private clearPingTimer(): void {
    if (this.pingTimer) {
      clearInterval(this.pingTimer);
      this.pingTimer = null;
    }
  }

  private updateConnectionState(state: WebSocketState, error?: string): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.stats.connectionState = state;
      
      // Notify handlers
      this.stateChangeHandlers.forEach(handler => {
        try {
          handler(state, error);
        } catch (err) {
          console.error('Error in state change handler:', err);
        }
      });

      this.statsHandlers.forEach(handler => {
        try {
          handler(this.getStats());
        } catch (err) {
          console.error('Error in stats handler:', err);
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

  private async processPendingMessages(): Promise<void> {
    const messagesToProcess = [...this.pendingMessages];
    this.pendingMessages = [];

    for (const pendingMessage of messagesToProcess) {
      try {
        const success = await this.sendMessage(pendingMessage.message);
        pendingMessage.resolve(success);
      } catch (error) {
        pendingMessage.reject(error instanceof Error ? error : new Error('Unknown error'));
      }
    }
  }

  // Cleanup method
  destroy(): void {
    this.disconnect();
    this.messageHandlers.clear();
    this.stateChangeHandlers.clear();
    this.statsHandlers.clear();
    this.pendingMessages = [];
    this.messageQueue = [];
  }
}

// Factory function
export function createWebSocketManager(config: WebSocketConfig): WebSocketManager {
  return new WebSocketManager(config);
}

// Utility functions
export function isEventMessage(message: WebSocketMessage): boolean {
  return message.type === 'event';
}

export function isErrorMessage(message: WebSocketMessage): boolean {
  return message.type === 'error';
}

export function isStatusMessage(message: WebSocketMessage): boolean {
  return ['connection_established', 'subscription_updated', 'configuration_updated', 'publish_result'].includes(message.type);
}