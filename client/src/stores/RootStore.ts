import { makeAutoObservable, runInAction } from 'mobx';
import axios from 'axios';
import { 
  CommunicationManager, 
  createCommunicationManager,
  CommunicationProtocol,
  CommunicationState,
  UnifiedEvent
} from '../services/CommunicationManager';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface Agent {
  agentId: string;
  status: 'idle' | 'working' | 'paused' | 'error';
  taskCategory: string;
  currentTask?: string;
  elapsedTime: number;
  angle: number;
  distance: number;
}

export interface Task {
  task_id: string;
  description: string;
  status: string;
  priority: string;
  sector: string;
  agent_id?: string;
  tps?: number;
  time_elapsed?: string;
}

export interface Metrics {
  tokensPerSecond: number;
  costPerSecondUSD: number;
  totalSpend: number;
  completionRate: number;
}

export interface SystemAlert {
  id: string;
  level: 'info' | 'warning' | 'error' | 'critical';
  message: string;
  timestamp: Date;
  details?: Record<string, any>;
  dismissed?: boolean;
}

export interface CollaborationState {
  activeUsers: Map<string, {
    userId: string;
    name: string;
    currentView: string;
    lastSeen: Date;
    cursor?: { x: number; y: number };
  }>;
  broadcastMessages: Array<{
    id: string;
    message: string;
    timestamp: Date;
    type: string;
  }>;
}

export interface PerformanceAlert {
  id: string;
  metric: string;
  threshold: number;
  currentValue: number;
  severity: 'warning' | 'critical';
  timestamp: Date;
}

export class RootStore {
  agents: Agent[] = [];
  tasks: Task[] = [];
  metrics: Metrics = {
    tokensPerSecond: 0,
    costPerSecondUSD: 0,
    totalSpend: 0,
    completionRate: 0
  };
  throttleRate: number = 1.0;
  
  // Real-time features
  systemAlerts: SystemAlert[] = [];
  collaboration: CollaborationState = {
    activeUsers: new Map(),
    broadcastMessages: []
  };
  performanceAlerts: PerformanceAlert[] = [];
  
  // Communication management
  communicationManager: CommunicationManager | null = null;
  connectionState: CommunicationState = CommunicationState.DISCONNECTED;
  currentProtocol: CommunicationProtocol = CommunicationProtocol.SSE;
  
  // User session
  currentUserId: string = '';
  currentView: string = 'dashboard';

  constructor() {
    makeAutoObservable(this);
    
    // Generate user session
    this.currentUserId = `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    
    // Initialize communication manager
    this.initializeCommunication();
    
    // Track user view changes
    this.trackUserView();
  }

  async fetchAgents() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/agents`);
      runInAction(() => {
        this.agents = response.data;
      });
    } catch (error) {
      console.error('Failed to fetch agents:', error);
    }
  }

  async fetchTasks() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/tasks`);
      runInAction(() => {
        this.tasks = response.data;
      });
    } catch (error) {
      console.error('Failed to fetch tasks:', error);
    }
  }

  async fetchMetrics() {
    try {
      const response = await axios.get(`${API_BASE_URL}/api/system/metrics`);
      runInAction(() => {
        this.metrics = response.data;
      });
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  }

  // Initialize communication manager
  private initializeCommunication() {
    const config = {
      baseUrl: API_BASE_URL,
      channels: ['agents', 'tasks', 'metrics', 'alerts', 'collaboration', 'broadcast'],
      eventTypes: ['agent_status', 'task_update', 'metrics_data', 'system_alert', 'collaboration', 'broadcast', 'performance_alert'],
      preferredProtocol: CommunicationProtocol.SSE,
      fallbackEnabled: true,
      compression: true,
      bufferSize: 50
    };

    this.communicationManager = createCommunicationManager(config);
    
    // Set up event handlers
    this.communicationManager.addEventListener(this.handleRealtimeEvent.bind(this));
    this.communicationManager.onStateChange(this.handleConnectionStateChange.bind(this));
    this.communicationManager.onProtocolSwitch(this.handleProtocolSwitch.bind(this));
  }

  // Handle real-time events
  private handleRealtimeEvent(event: UnifiedEvent) {
    runInAction(() => {
      switch (event.type) {
        case 'agent_status':
          this.handleAgentStatusUpdate(event.data);
          break;
        case 'task_update':
          this.handleTaskUpdate(event.data);
          break;
        case 'metrics_data':
          this.handleMetricsUpdate(event.data);
          break;
        case 'system_alert':
          this.handleSystemAlert(event.data);
          break;
        case 'collaboration':
          this.handleCollaborationEvent(event.data);
          break;
        case 'broadcast':
          this.handleBroadcastMessage(event.data);
          break;
        case 'performance_alert':
          this.handlePerformanceAlert(event.data);
          break;
      }
    });
  }

  private handleAgentStatusUpdate(data: any) {
    const agent = this.agents.find(a => a.agentId === data.agent_id);
    if (agent) {
      agent.status = data.status;
      agent.currentTask = data.current_task;
      if (data.performance) {
        // Update performance data
        Object.assign(agent, data.performance);
      }
    }
  }

  private handleTaskUpdate(data: any) {
    const task = this.tasks.find(t => t.task_id === data.task_id);
    if (task) {
      task.status = data.status;
      if (data.progress !== undefined) {
        // Add progress tracking if not exists
        (task as any).progress = data.progress;
      }
      if (data.agent_id) {
        task.agent_id = data.agent_id;
      }
    }
  }

  private handleMetricsUpdate(data: any) {
    // Handle aggregated metrics data
    if (data.batch_size && data.batch_size > 1) {
      // This is aggregated data
      if (data.tokensPerSecond) {
        this.metrics.tokensPerSecond = data.tokensPerSecond.avg || data.tokensPerSecond;
      }
      if (data.costPerSecondUSD) {
        this.metrics.costPerSecondUSD = data.costPerSecondUSD.avg || data.costPerSecondUSD;
      }
    } else {
      // Regular metrics update
      this.metrics = { ...this.metrics, ...data };
    }
  }

  private handleSystemAlert(data: any) {
    const alert: SystemAlert = {
      id: data.id || `alert_${Date.now()}`,
      level: data.level,
      message: data.message,
      timestamp: new Date(data.timestamp || Date.now()),
      details: data.details,
      dismissed: false
    };
    
    this.systemAlerts.unshift(alert);
    
    // Keep only last 100 alerts
    if (this.systemAlerts.length > 100) {
      this.systemAlerts = this.systemAlerts.slice(0, 100);
    }
  }

  private handleCollaborationEvent(data: any) {
    const { user_id, action, target, data: eventData } = data;
    
    switch (action) {
      case 'joined':
      case 'viewing':
        this.collaboration.activeUsers.set(user_id, {
          userId: user_id,
          name: eventData.name || `User ${user_id.slice(-4)}`,
          currentView: target,
          lastSeen: new Date(),
          cursor: eventData.cursor
        });
        break;
      
      case 'left':
        this.collaboration.activeUsers.delete(user_id);
        break;
      
      case 'cursor_move':
        const user = this.collaboration.activeUsers.get(user_id);
        if (user) {
          user.cursor = eventData.cursor;
          user.lastSeen = new Date();
        }
        break;
    }
    
    // Clean up inactive users (not seen for 5 minutes)
    const fiveMinutesAgo = new Date(Date.now() - 5 * 60 * 1000);
    for (const [userId, user] of this.collaboration.activeUsers) {
      if (user.lastSeen < fiveMinutesAgo) {
        this.collaboration.activeUsers.delete(userId);
      }
    }
  }

  private handleBroadcastMessage(data: any) {
    const message = {
      id: data.id || `msg_${Date.now()}`,
      message: data.message,
      timestamp: new Date(data.timestamp || Date.now()),
      type: data.event_type || 'info'
    };
    
    this.collaboration.broadcastMessages.unshift(message);
    
    // Keep only last 50 messages
    if (this.collaboration.broadcastMessages.length > 50) {
      this.collaboration.broadcastMessages = this.collaboration.broadcastMessages.slice(0, 50);
    }
  }

  private handlePerformanceAlert(data: any) {
    const alert: PerformanceAlert = {
      id: data.id || `perf_${Date.now()}`,
      metric: data.metric,
      threshold: data.threshold,
      currentValue: data.currentValue,
      severity: data.severity,
      timestamp: new Date(data.timestamp || Date.now())
    };
    
    this.performanceAlerts.unshift(alert);
    
    // Keep only last 20 performance alerts
    if (this.performanceAlerts.length > 20) {
      this.performanceAlerts = this.performanceAlerts.slice(0, 20);
    }
  }

  private handleConnectionStateChange(state: CommunicationState, protocol: CommunicationProtocol, error?: string) {
    this.connectionState = state;
    this.currentProtocol = protocol;
    
    if (error) {
      console.error(`Communication ${protocol} error:`, error);
    }
  }

  private handleProtocolSwitch(from: CommunicationProtocol, to: CommunicationProtocol, reason: string) {
    console.log(`Switched from ${from} to ${to}: ${reason}`);
    
    // Add system alert for protocol switch
    this.handleSystemAlert({
      level: 'info',
      message: `Switched communication protocol from ${from} to ${to}`,
      details: { reason, timestamp: new Date().toISOString() }
    });
  }

  // Track user view changes for collaboration
  private trackUserView() {
    // This would be called when user navigates
    setInterval(() => {
      if (this.communicationManager && this.connectionState === CommunicationState.CONNECTED) {
        this.sendCollaborationEvent('viewing', this.currentView, {
          name: `User ${this.currentUserId.slice(-4)}`,
          cursor: this.getMousePosition()
        });
      }
    }, 10000); // Send heartbeat every 10 seconds
  }

  private getMousePosition(): { x: number; y: number } | undefined {
    // This would be implemented to track actual mouse position
    return undefined;
  }

  // Public methods for real-time communication
  async connectToStream() {
    if (this.communicationManager) {
      await this.communicationManager.connect();
      
      // Send initial collaboration event
      await this.sendCollaborationEvent('joined', this.currentView, {
        name: `User ${this.currentUserId.slice(-4)}`
      });
    }
  }

  disconnectStream() {
    if (this.communicationManager) {
      // Send leave event
      this.sendCollaborationEvent('left', this.currentView, {});
      
      this.communicationManager.disconnect();
    }
  }

  async sendCollaborationEvent(action: string, target: string, data: any) {
    if (this.communicationManager && this.currentProtocol === CommunicationProtocol.WEBSOCKET) {
      try {
        await this.communicationManager.sendMessage('collaboration', {
          user_id: this.currentUserId,
          action,
          target,
          data
        });
      } catch (error) {
        console.error('Failed to send collaboration event:', error);
      }
    }
  }

  async sendBroadcastMessage(message: string, type: string = 'info') {
    if (this.communicationManager && this.currentProtocol === CommunicationProtocol.WEBSOCKET) {
      try {
        await this.communicationManager.sendMessage('broadcast', {
          message,
          event_type: type,
          user_id: this.currentUserId
        });
      } catch (error) {
        console.error('Failed to send broadcast message:', error);
      }
    }
  }

  async systemRun() {
    try {
      await axios.post(`${API_BASE_URL}/api/system/run`);
    } catch (error) {
      console.error('Failed to start system:', error);
    }
  }

  async pauseAll() {
    try {
      await axios.post(`${API_BASE_URL}/api/system/pause-all`);
    } catch (error) {
      console.error('Failed to pause all:', error);
    }
  }

  async stopNew() {
    try {
      await axios.post(`${API_BASE_URL}/api/system/stop-new`);
    } catch (error) {
      console.error('Failed to stop new tasks:', error);
    }
  }

  async setThrottle(rate: number) {
    try {
      await axios.post(`${API_BASE_URL}/api/system/throttle`, { rate });
      runInAction(() => {
        this.throttleRate = rate;
      });
    } catch (error) {
      console.error('Failed to set throttle:', error);
    }
  }

  // Real-time feature management methods
  dismissAlert(alertId: string) {
    runInAction(() => {
      const alert = this.systemAlerts.find(a => a.id === alertId);
      if (alert) {
        alert.dismissed = true;
      }
    });
  }

  clearDismissedAlerts() {
    runInAction(() => {
      this.systemAlerts = this.systemAlerts.filter(a => !a.dismissed);
    });
  }

  clearAllAlerts() {
    runInAction(() => {
      this.systemAlerts = [];
    });
  }

  dismissPerformanceAlert(alertId: string) {
    runInAction(() => {
      this.performanceAlerts = this.performanceAlerts.filter(a => a.id !== alertId);
    });
  }

  clearBroadcastMessages() {
    runInAction(() => {
      this.collaboration.broadcastMessages = [];
    });
  }

  switchCommunicationProtocol(protocol: CommunicationProtocol) {
    if (this.communicationManager) {
      this.communicationManager.switchProtocol(protocol, 'User requested switch');
    }
  }

  updateCurrentView(view: string) {
    runInAction(() => {
      this.currentView = view;
    });
    
    // Send collaboration event
    this.sendCollaborationEvent('viewing', view, {
      name: `User ${this.currentUserId.slice(-4)}`,
      timestamp: new Date().toISOString()
    });
  }

  getCommunicationStats() {
    return this.communicationManager?.getStats() || null;
  }

  getCommunicationHealth() {
    return this.communicationManager?.getHealth() || { healthy: false, issues: ['Not connected'] };
  }

  // Computed getters for UI
  get unreadAlertsCount() {
    return this.systemAlerts.filter(a => !a.dismissed).length;
  }

  get criticalAlertsCount() {
    return this.systemAlerts.filter(a => !a.dismissed && a.level === 'critical').length;
  }

  get activeUsersCount() {
    return this.collaboration.activeUsers.size;
  }

  get recentBroadcastsCount() {
    const oneHourAgo = new Date(Date.now() - 60 * 60 * 1000);
    return this.collaboration.broadcastMessages.filter(m => m.timestamp > oneHourAgo).length;
  }

  get activePerformanceAlertsCount() {
    return this.performanceAlerts.filter(a => a.severity === 'critical').length;
  }

  // Cleanup method
  destroy() {
    if (this.communicationManager) {
      this.communicationManager.destroy();
      this.communicationManager = null;
    }
  }
}

export const rootStore = new RootStore();