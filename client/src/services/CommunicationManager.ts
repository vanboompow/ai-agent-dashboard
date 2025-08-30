/**
 * Communication Manager - Handles automatic fallback between SSE and WebSocket
 * Provides unified interface for real-time communication with reliability
 */

import { SSEManager, SSEEvent, ConnectionState as SSEConnectionState, SSEConnectionConfig } from './SSEManager';
import { WebSocketManager, WebSocketMessage, WebSocketState, WebSocketConfig } from './WebSocketManager';

export enum CommunicationProtocol {
  SSE = 'SSE',
  WEBSOCKET = 'WEBSOCKET'
}

export enum CommunicationState {
  DISCONNECTED = 'DISCONNECTED',
  CONNECTING = 'CONNECTING', 
  CONNECTED = 'CONNECTED',
  RECONNECTING = 'RECONNECTING',
  FAILED = 'FAILED'
}

export interface UnifiedEvent {
  id?: string;
  type: string;
  data: any;
  timestamp: string;
  source: 'sse' | 'websocket';
  priority?: number;
}

export interface CommunicationConfig {
  baseUrl: string;
  sseEndpoint?: string;
  wsEndpoint?: string;
  preferredProtocol?: CommunicationProtocol;
  fallbackEnabled?: boolean;
  fallbackDelay?: number;
  channels: string[];
  eventTypes?: string[];
  agentIds?: string[];
  minPriority?: number;
  compression?: boolean;
  bufferSize?: number;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  healthCheckInterval?: number;
  failureThreshold?: number;
}

export interface CommunicationStats {
  currentProtocol: CommunicationProtocol;
  connectionState: CommunicationState;
  connectedAt: Date | null;
  totalEvents: number;
  droppedEvents: number;
  protocolSwitches: number;
  averageLatency: number;
  sseStats?: any;
  websocketStats?: any;
  lastFailureReason?: string;
}

type EventHandler = (event: UnifiedEvent) => void;
type StateChangeHandler = (state: CommunicationState, protocol: CommunicationProtocol, error?: string) => void;
type ProtocolSwitchHandler = (fromProtocol: CommunicationProtocol, toProtocol: CommunicationProtocol, reason: string) => void;
type StatsHandler = (stats: CommunicationStats) => void;

interface FailureRecord {
  timestamp: Date;
  protocol: CommunicationProtocol;
  reason: string;
}

export class CommunicationManager {
  private config: Required<CommunicationConfig>;
  private currentProtocol: CommunicationProtocol;
  private connectionState: CommunicationState = CommunicationState.DISCONNECTED;
  
  // Protocol managers
  private sseManager: SSEManager | null = null;
  private wsManager: WebSocketManager | null = null;
  
  // Event handlers
  private eventHandlers: Set<EventHandler> = new Set();
  private stateChangeHandlers: Set<StateChangeHandler> = new Set();
  private protocolSwitchHandlers: Set<ProtocolSwitchHandler> = new Set();
  private statsHandlers: Set<StatsHandler> = new Set();
  
  // Failure tracking
  private failures: FailureRecord[] = [];
  private healthCheckTimer: number | null = null;
  private fallbackTimer: number | null = null;
  
  // Statistics
  private stats: CommunicationStats = {
    currentProtocol: CommunicationProtocol.SSE,
    connectionState: CommunicationState.DISCONNECTED,
    connectedAt: null,
    totalEvents: 0,
    droppedEvents: 0,
    protocolSwitches: 0,
    averageLatency: 0
  };

  constructor(config: CommunicationConfig) {
    this.config = {
      baseUrl: config.baseUrl,
      sseEndpoint: config.sseEndpoint || '/api/stream',
      wsEndpoint: config.wsEndpoint || '/api/websocket',
      preferredProtocol: config.preferredProtocol || CommunicationProtocol.SSE,
      fallbackEnabled: config.fallbackEnabled !== false,
      fallbackDelay: config.fallbackDelay || 5000,
      channels: config.channels,
      eventTypes: config.eventTypes || [],
      agentIds: config.agentIds || [],
      minPriority: config.minPriority || 1,
      compression: config.compression || false,
      bufferSize: config.bufferSize || 50,
      reconnectInterval: config.reconnectInterval || 3000,
      maxReconnectAttempts: config.maxReconnectAttempts || 10,
      healthCheckInterval: config.healthCheckInterval || 30000,
      failureThreshold: config.failureThreshold || 3
    };

    this.currentProtocol = this.config.preferredProtocol;
    this.initializeManagers();
  }

  /**
   * Connect using preferred protocol with automatic fallback
   */
  async connect(): Promise<boolean> {
    if (this.connectionState === CommunicationState.CONNECTED ||
        this.connectionState === CommunicationState.CONNECTING) {
      return true;
    }

    this.updateConnectionState(CommunicationState.CONNECTING);
    
    // Try preferred protocol first
    const success = await this.connectWithProtocol(this.currentProtocol);
    
    if (!success && this.config.fallbackEnabled) {
      // Try fallback protocol
      const fallbackProtocol = this.currentProtocol === CommunicationProtocol.SSE 
        ? CommunicationProtocol.WEBSOCKET 
        : CommunicationProtocol.SSE;
      
      console.log(`Primary protocol ${this.currentProtocol} failed, trying fallback ${fallbackProtocol}`);
      await this.switchProtocol(fallbackProtocol, 'Primary protocol failed');
      
      return this.connectWithProtocol(this.currentProtocol);
    }
    
    return success;
  }

  /**
   * Disconnect from current protocol
   */
  disconnect(): void {
    this.clearTimers();
    
    if (this.sseManager) {
      this.sseManager.disconnect();
    }
    
    if (this.wsManager) {
      this.wsManager.disconnect();
    }
    
    this.updateConnectionState(CommunicationState.DISCONNECTED);
    this.stats.connectedAt = null;
  }

  /**
   * Send message (WebSocket only - bidirectional communication)
   */
  async sendMessage(type: string, data: any): Promise<boolean> {
    if (this.connectionState !== CommunicationState.CONNECTED) {
      throw new Error('Not connected');
    }
    
    if (this.currentProtocol === CommunicationProtocol.WEBSOCKET && this.wsManager) {
      return this.wsManager.publishEvent(type, data);
    } else {
      throw new Error('Sending messages requires WebSocket protocol');
    }
  }

  /**
   * Switch to specific protocol
   */
  async switchProtocol(protocol: CommunicationProtocol, reason: string = 'Manual switch'): Promise<boolean> {
    if (this.currentProtocol === protocol) {
      return true;
    }

    const oldProtocol = this.currentProtocol;
    
    // Disconnect from current protocol
    if (this.connectionState === CommunicationState.CONNECTED) {
      this.disconnect();
    }
    
    // Update current protocol
    this.currentProtocol = protocol;
    this.stats.currentProtocol = protocol;
    this.stats.protocolSwitches++;
    
    // Notify handlers
    this.protocolSwitchHandlers.forEach(handler => {
      try {
        handler(oldProtocol, protocol, reason);
      } catch (error) {
        console.error('Error in protocol switch handler:', error);
      }
    });
    
    // Connect with new protocol
    return this.connect();
  }

  /**
   * Add event handler
   */
  addEventListener(handler: EventHandler): () => void {
    this.eventHandlers.add(handler);
    return () => this.eventHandlers.delete(handler);
  }

  /**
   * Add state change handler
   */
  onStateChange(handler: StateChangeHandler): () => void {
    this.stateChangeHandlers.add(handler);
    return () => this.stateChangeHandlers.delete(handler);
  }

  /**
   * Add protocol switch handler
   */
  onProtocolSwitch(handler: ProtocolSwitchHandler): () => void {
    this.protocolSwitchHandlers.add(handler);
    return () => this.protocolSwitchHandlers.delete(handler);
  }

  /**
   * Add stats handler
   */
  onStatsUpdate(handler: StatsHandler): () => void {
    this.statsHandlers.add(handler);
    return () => this.statsHandlers.delete(handler);
  }

  /**
   * Get current statistics
   */
  getStats(): CommunicationStats {
    return {
      ...this.stats,
      sseStats: this.sseManager?.getStats(),
      websocketStats: this.wsManager?.getStats()
    };
  }

  /**
   * Get connection health
   */
  getHealth(): { healthy: boolean; issues: string[] } {
    const issues: string[] = [];
    
    if (this.connectionState !== CommunicationState.CONNECTED) {
      issues.push('Not connected');
    }
    
    // Check recent failures
    const recentFailures = this.failures.filter(
      f => Date.now() - f.timestamp.getTime() < 60000 // Last minute
    );
    
    if (recentFailures.length >= this.config.failureThreshold) {
      issues.push(`Too many recent failures: ${recentFailures.length}`);
    }
    
    // Check latency
    if (this.stats.averageLatency > 5000) { // 5 second latency is concerning
      issues.push(`High latency: ${this.stats.averageLatency}ms`);
    }
    
    // Check dropped events
    if (this.stats.droppedEvents > this.stats.totalEvents * 0.1) { // More than 10% dropped
      issues.push(`High drop rate: ${this.stats.droppedEvents}/${this.stats.totalEvents}`);
    }
    
    return {
      healthy: issues.length === 0,
      issues
    };
  }

  /**
   * Force reconnection
   */
  reconnect(): void {
    this.disconnect();
    this.connect();
  }

  /**
   * Update configuration
   */
  updateConfig(newConfig: Partial<CommunicationConfig>): void {
    const wasConnected = this.connectionState === CommunicationState.CONNECTED;
    
    if (wasConnected) {
      this.disconnect();
    }
    
    Object.assign(this.config, newConfig);
    
    // Reinitialize managers with new config
    this.initializeManagers();
    
    if (wasConnected) {
      this.connect();
    }
  }

  private async connectWithProtocol(protocol: CommunicationProtocol): Promise<boolean> {
    try {
      let success = false;
      
      if (protocol === CommunicationProtocol.SSE && this.sseManager) {
        success = await this.sseManager.connect();
      } else if (protocol === CommunicationProtocol.WEBSOCKET && this.wsManager) {
        success = await this.wsManager.connect();
      }
      
      if (success) {
        this.updateConnectionState(CommunicationState.CONNECTED);
        this.stats.connectedAt = new Date();
        this.startHealthChecking();
      } else {
        this.recordFailure(protocol, 'Connection failed');
        this.updateConnectionState(CommunicationState.FAILED);
      }
      
      return success;
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      console.error(`${protocol} connection error:`, errorMessage);
      this.recordFailure(protocol, errorMessage);
      this.updateConnectionState(CommunicationState.FAILED, errorMessage);
      return false;
    }
  }

  private initializeManagers(): void {
    // Initialize SSE Manager
    const sseConfig: SSEConnectionConfig = {
      url: `${this.config.baseUrl}${this.config.sseEndpoint}`,
      channels: this.config.channels,
      eventTypes: this.config.eventTypes,
      agentIds: this.config.agentIds,
      minPriority: this.config.minPriority,
      compression: this.config.compression,
      bufferSize: this.config.bufferSize,
      reconnectInterval: this.config.reconnectInterval,
      maxReconnectAttempts: this.config.maxReconnectAttempts
    };
    
    this.sseManager = new SSEManager(sseConfig);
    this.setupSSEHandlers();
    
    // Initialize WebSocket Manager
    const wsConfig: WebSocketConfig = {
      url: `${this.config.baseUrl}${this.config.wsEndpoint}`,
      channels: this.config.channels,
      eventTypes: this.config.eventTypes,
      agentIds: this.config.agentIds,
      minPriority: this.config.minPriority,
      compression: this.config.compression,
      bufferSize: this.config.bufferSize,
      reconnectInterval: this.config.reconnectInterval,
      maxReconnectAttempts: this.config.maxReconnectAttempts
    };
    
    this.wsManager = new WebSocketManager(wsConfig);
    this.setupWebSocketHandlers();
  }

  private setupSSEHandlers(): void {
    if (!this.sseManager) return;
    
    // Event handlers
    this.sseManager.addEventListener('message', (event: SSEEvent) => {
      if (this.currentProtocol === CommunicationProtocol.SSE) {
        this.handleUnifiedEvent({
          id: event.id,
          type: event.event || 'message',
          data: event.data,
          timestamp: event.timestamp,
          source: 'sse'
        });
      }
    });
    
    // State change handler
    this.sseManager.onStateChange((state, error) => {
      if (this.currentProtocol === CommunicationProtocol.SSE) {
        const mappedState = this.mapSSEState(state);
        this.updateConnectionState(mappedState, error);
        
        // Handle failures
        if (state === SSEConnectionState.FAILED && this.config.fallbackEnabled) {
          this.scheduleProtocolFallback('SSE connection failed');
        }
      }
    });
  }

  private setupWebSocketHandlers(): void {
    if (!this.wsManager) return;
    
    // Event handlers
    this.wsManager.addMessageHandler('event', (message: WebSocketMessage) => {
      if (this.currentProtocol === CommunicationProtocol.WEBSOCKET) {
        this.handleUnifiedEvent({
          id: message.id,
          type: message.data.event_type || 'event',
          data: message.data.payload || message.data,
          timestamp: message.timestamp || new Date().toISOString(),
          source: 'websocket',
          priority: message.data.priority
        });
      }
    });
    
    // State change handler
    this.wsManager.onStateChange((state, error) => {
      if (this.currentProtocol === CommunicationProtocol.WEBSOCKET) {
        const mappedState = this.mapWebSocketState(state);
        this.updateConnectionState(mappedState, error);
        
        // Handle failures
        if (state === WebSocketState.FAILED && this.config.fallbackEnabled) {
          this.scheduleProtocolFallback('WebSocket connection failed');
        }
      }
    });
  }

  private handleUnifiedEvent(event: UnifiedEvent): void {
    this.stats.totalEvents++;
    
    // Emit to all event handlers
    this.eventHandlers.forEach(handler => {
      try {
        handler(event);
      } catch (error) {
        console.error('Error in unified event handler:', error);
        this.stats.droppedEvents++;
      }
    });
  }

  private updateConnectionState(state: CommunicationState, error?: string): void {
    if (this.connectionState !== state) {
      this.connectionState = state;
      this.stats.connectionState = state;
      
      if (error) {
        this.stats.lastFailureReason = error;
      }
      
      // Notify handlers
      this.stateChangeHandlers.forEach(handler => {
        try {
          handler(state, this.currentProtocol, error);
        } catch (err) {
          console.error('Error in state change handler:', err);
        }
      });
      
      this.notifyStatsHandlers();
    }
  }

  private recordFailure(protocol: CommunicationProtocol, reason: string): void {
    this.failures.push({
      timestamp: new Date(),
      protocol,
      reason
    });
    
    // Keep only recent failures (last hour)
    const cutoff = new Date(Date.now() - 3600000);
    this.failures = this.failures.filter(f => f.timestamp > cutoff);
  }

  private scheduleProtocolFallback(reason: string): void {
    if (this.fallbackTimer) return; // Already scheduled
    
    const fallbackProtocol = this.currentProtocol === CommunicationProtocol.SSE 
      ? CommunicationProtocol.WEBSOCKET 
      : CommunicationProtocol.SSE;
    
    console.log(`Scheduling fallback to ${fallbackProtocol} in ${this.config.fallbackDelay}ms: ${reason}`);
    
    this.fallbackTimer = window.setTimeout(async () => {
      this.fallbackTimer = null;
      await this.switchProtocol(fallbackProtocol, reason);
    }, this.config.fallbackDelay);
  }

  private startHealthChecking(): void {
    if (this.healthCheckTimer) return;
    
    this.healthCheckTimer = window.setInterval(() => {
      this.performHealthCheck();
    }, this.config.healthCheckInterval);
  }

  private performHealthCheck(): void {
    const health = this.getHealth();
    
    if (!health.healthy) {
      console.warn('Communication health check failed:', health.issues);
      
      // Consider protocol switch if there are persistent issues
      if (this.config.fallbackEnabled && health.issues.some(issue => 
        issue.includes('failures') || issue.includes('latency') || issue.includes('drop rate')
      )) {
        this.scheduleProtocolFallback('Health check failed');
      }
    }
    
    this.notifyStatsHandlers();
  }

  private clearTimers(): void {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }
    
    if (this.fallbackTimer) {
      clearTimeout(this.fallbackTimer);
      this.fallbackTimer = null;
    }
  }

  private mapSSEState(sseState: SSEConnectionState): CommunicationState {
    switch (sseState) {
      case SSEConnectionState.DISCONNECTED:
        return CommunicationState.DISCONNECTED;
      case SSEConnectionState.CONNECTING:
        return CommunicationState.CONNECTING;
      case SSEConnectionState.CONNECTED:
        return CommunicationState.CONNECTED;
      case SSEConnectionState.RECONNECTING:
        return CommunicationState.RECONNECTING;
      case SSEConnectionState.FAILED:
        return CommunicationState.FAILED;
      default:
        return CommunicationState.DISCONNECTED;
    }
  }

  private mapWebSocketState(wsState: WebSocketState): CommunicationState {
    switch (wsState) {
      case WebSocketState.DISCONNECTED:
        return CommunicationState.DISCONNECTED;
      case WebSocketState.CONNECTING:
        return CommunicationState.CONNECTING;
      case WebSocketState.CONNECTED:
        return CommunicationState.CONNECTED;
      case WebSocketState.RECONNECTING:
        return CommunicationState.RECONNECTING;
      case WebSocketState.FAILED:
        return CommunicationState.FAILED;
      default:
        return CommunicationState.DISCONNECTED;
    }
  }

  private notifyStatsHandlers(): void {
    const stats = this.getStats();
    this.statsHandlers.forEach(handler => {
      try {
        handler(stats);
      } catch (error) {
        console.error('Error in stats handler:', error);
      }
    });
  }

  // Cleanup
  destroy(): void {
    this.disconnect();
    this.clearTimers();
    
    if (this.sseManager) {
      this.sseManager.destroy();
      this.sseManager = null;
    }
    
    if (this.wsManager) {
      this.wsManager.destroy();
      this.wsManager = null;
    }
    
    this.eventHandlers.clear();
    this.stateChangeHandlers.clear();
    this.protocolSwitchHandlers.clear();
    this.statsHandlers.clear();
  }
}

// Factory function
export function createCommunicationManager(config: CommunicationConfig): CommunicationManager {
  return new CommunicationManager(config);
}