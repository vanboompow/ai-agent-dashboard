/**
 * Communication Status Panel - Show detailed real-time communication statistics
 */
import React, { useState, useEffect } from 'react';
import { observer } from 'mobx-react-lite';
import { useStore } from '../../stores/useStore';
import { CommunicationProtocol } from '../../services/CommunicationManager';
import './RealTimeFeatures.css';

const CommunicationStatusPanel: React.FC = observer(() => {
  const store = useStore();
  const [stats, setStats] = useState<any>(null);
  const [health, setHealth] = useState<any>(null);

  useEffect(() => {
    const updateStats = () => {
      setStats(store.getCommunicationStats());
      setHealth(store.getCommunicationHealth());
    };

    // Update immediately
    updateStats();

    // Update every 5 seconds
    const interval = setInterval(updateStats, 5000);

    return () => clearInterval(interval);
  }, [store]);

  const getConnectionStateColor = (state: string) => {
    switch (state) {
      case 'CONNECTED': return '#28a745';
      case 'CONNECTING': return '#ffc107';
      case 'RECONNECTING': return '#fd7e14';
      case 'FAILED': return '#dc3545';
      case 'DISCONNECTED':
      default: return '#6c757d';
    }
  };

  const formatDuration = (seconds: number) => {
    if (seconds < 60) return `${Math.round(seconds)}s`;
    if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
    return `${Math.round(seconds / 3600)}h`;
  };

  const formatBytes = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="communication-status-panel">
      <div className="panel-header">
        <h3>Communication Status</h3>
        <div className="panel-controls">
          <button 
            className="btn btn-sm btn-outline-primary"
            onClick={() => store.communicationManager?.reconnect()}
            disabled={store.connectionState === 'CONNECTING'}
            title="Force reconnection"
          >
            🔄 Reconnect
          </button>
        </div>
      </div>

      {/* Connection Overview */}
      <div className="connection-overview">
        <div className="status-item">
          <span className="status-label">State:</span>
          <span 
            className="status-value"
            style={{ color: getConnectionStateColor(store.connectionState) }}
          >
            {store.connectionState}
          </span>
        </div>
        
        <div className="status-item">
          <span className="status-label">Protocol:</span>
          <span className="status-value">
            {store.currentProtocol}
            <button 
              className="protocol-switch-btn"
              onClick={() => {
                const newProtocol = store.currentProtocol === CommunicationProtocol.SSE 
                  ? CommunicationProtocol.WEBSOCKET 
                  : CommunicationProtocol.SSE;
                store.switchCommunicationProtocol(newProtocol);
              }}
              title={`Switch to ${store.currentProtocol === CommunicationProtocol.SSE ? 'WebSocket' : 'SSE'}`}
            >
              ⇄
            </button>
          </span>
        </div>
      </div>

      {/* Health Status */}
      {health && (
        <div className="health-status">
          <div className="health-indicator">
            <span className={`health-icon ${health.healthy ? 'healthy' : 'unhealthy'}`}>
              {health.healthy ? '✅' : '❌'}
            </span>
            <span className="health-text">
              {health.healthy ? 'Healthy' : 'Issues Detected'}
            </span>
          </div>
          
          {health.issues && health.issues.length > 0 && (
            <div className="health-issues">
              <strong>Issues:</strong>
              <ul>
                {health.issues.map((issue: string, index: number) => (
                  <li key={index}>{issue}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {/* Statistics */}
      {stats && (
        <div className="stats-section">
          <h4>Statistics</h4>
          
          <div className="stats-grid">
            {stats.connectedAt && (
              <div className="stat-item">
                <span className="stat-label">Connected:</span>
                <span className="stat-value">
                  {formatDuration((Date.now() - new Date(stats.connectedAt).getTime()) / 1000)} ago
                </span>
              </div>
            )}
            
            <div className="stat-item">
              <span className="stat-label">Total Events:</span>
              <span className="stat-value">{stats.totalEvents}</span>
            </div>
            
            {stats.droppedEvents > 0 && (
              <div className="stat-item">
                <span className="stat-label">Dropped Events:</span>
                <span className="stat-value warning">{stats.droppedEvents}</span>
              </div>
            )}
            
            <div className="stat-item">
              <span className="stat-label">Protocol Switches:</span>
              <span className="stat-value">{stats.protocolSwitches}</span>
            </div>
            
            {stats.averageLatency > 0 && (
              <div className="stat-item">
                <span className="stat-label">Avg Latency:</span>
                <span className="stat-value">{Math.round(stats.averageLatency)}ms</span>
              </div>
            )}
          </div>

          {/* Protocol-specific stats */}
          {stats.sseStats && store.currentProtocol === CommunicationProtocol.SSE && (
            <div className="protocol-stats">
              <h5>SSE Details</h5>
              <div className="stats-grid">
                <div className="stat-item">
                  <span className="stat-label">Connection ID:</span>
                  <span className="stat-value">{stats.sseStats.connectionId}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Reconnect Attempts:</span>
                  <span className="stat-value">{stats.sseStats.reconnectAttempts}</span>
                </div>
              </div>
            </div>
          )}

          {stats.websocketStats && store.currentProtocol === CommunicationProtocol.WEBSOCKET && (
            <div className="protocol-stats">
              <h5>WebSocket Details</h5>
              <div className="stats-grid">
                <div className="stat-item">
                  <span className="stat-label">Connection ID:</span>
                  <span className="stat-value">{stats.websocketStats.connectionId}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Messages Sent:</span>
                  <span className="stat-value">{stats.websocketStats.messagesSent}</span>
                </div>
                <div className="stat-item">
                  <span className="stat-label">Messages Received:</span>
                  <span className="stat-value">{stats.websocketStats.messagesReceived}</span>
                </div>
                {stats.websocketStats.lastPing && (
                  <div className="stat-item">
                    <span className="stat-label">Last Ping:</span>
                    <span className="stat-value">
                      {formatDuration((Date.now() - new Date(stats.websocketStats.lastPing).getTime()) / 1000)} ago
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Event Stream Info */}
      <div className="stream-info">
        <h4>Event Stream</h4>
        <div className="stream-details">
          <div className="detail-item">
            <span className="detail-label">Channels:</span>
            <span className="detail-value">agents, tasks, metrics, alerts, collaboration</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Compression:</span>
            <span className="detail-value">Enabled for large payloads</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Buffer Size:</span>
            <span className="detail-value">50 events</span>
          </div>
          <div className="detail-item">
            <span className="detail-label">Fallback:</span>
            <span className="detail-value">SSE ⇄ WebSocket</span>
          </div>
        </div>
      </div>
    </div>
  );
});

export default CommunicationStatusPanel;