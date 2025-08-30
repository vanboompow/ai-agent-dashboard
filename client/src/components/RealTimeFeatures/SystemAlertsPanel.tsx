/**
 * System Alerts Panel - Display real-time system alerts with management
 */
import React from 'react';
import { observer } from 'mobx-react-lite';
import { useStore } from '../../stores/useStore';
import { SystemAlert } from '../../stores/RootStore';
import './RealTimeFeatures.css';

interface SystemAlertsPanelProps {
  maxVisible?: number;
  showDismissed?: boolean;
}

const SystemAlertsPanel: React.FC<SystemAlertsPanelProps> = observer(({ 
  maxVisible = 10, 
  showDismissed = false 
}) => {
  const store = useStore();
  
  const visibleAlerts = store.systemAlerts
    .filter(alert => showDismissed || !alert.dismissed)
    .slice(0, maxVisible);

  const getAlertIcon = (level: string) => {
    switch (level) {
      case 'critical': return '🚨';
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'info': 
      default: return 'ℹ️';
    }
  };

  const getAlertClass = (level: string) => {
    return `alert alert-${level}`;
  };

  const formatTimestamp = (timestamp: Date) => {
    const now = new Date();
    const diff = now.getTime() - timestamp.getTime();
    
    if (diff < 60000) { // Less than 1 minute
      return 'Just now';
    } else if (diff < 3600000) { // Less than 1 hour
      return `${Math.floor(diff / 60000)}m ago`;
    } else if (diff < 86400000) { // Less than 1 day
      return `${Math.floor(diff / 3600000)}h ago`;
    } else {
      return timestamp.toLocaleDateString();
    }
  };

  return (
    <div className="system-alerts-panel">
      <div className="panel-header">
        <h3>
          System Alerts 
          {store.unreadAlertsCount > 0 && (
            <span className="badge badge-danger">{store.unreadAlertsCount}</span>
          )}
        </h3>
        <div className="panel-controls">
          {store.systemAlerts.some(a => a.dismissed) && (
            <button 
              className="btn btn-sm btn-outline-secondary"
              onClick={() => store.clearDismissedAlerts()}
              title="Clear dismissed alerts"
            >
              Clear Dismissed
            </button>
          )}
          {store.systemAlerts.length > 0 && (
            <button 
              className="btn btn-sm btn-outline-danger"
              onClick={() => store.clearAllAlerts()}
              title="Clear all alerts"
            >
              Clear All
            </button>
          )}
        </div>
      </div>

      <div className="alerts-container">
        {visibleAlerts.length === 0 ? (
          <div className="no-alerts">
            <span>✅ No active alerts</span>
          </div>
        ) : (
          visibleAlerts.map((alert: SystemAlert) => (
            <div 
              key={alert.id} 
              className={`${getAlertClass(alert.level)} ${alert.dismissed ? 'dismissed' : ''}`}
            >
              <div className="alert-header">
                <span className="alert-icon">{getAlertIcon(alert.level)}</span>
                <span className="alert-level">{alert.level.toUpperCase()}</span>
                <span className="alert-timestamp">{formatTimestamp(alert.timestamp)}</span>
                {!alert.dismissed && (
                  <button 
                    className="btn-dismiss"
                    onClick={() => store.dismissAlert(alert.id)}
                    title="Dismiss alert"
                  >
                    ✕
                  </button>
                )}
              </div>
              
              <div className="alert-message">
                {alert.message}
              </div>
              
              {alert.details && Object.keys(alert.details).length > 0 && (
                <div className="alert-details">
                  <details>
                    <summary>Details</summary>
                    <pre>{JSON.stringify(alert.details, null, 2)}</pre>
                  </details>
                </div>
              )}
            </div>
          ))
        )}
      </div>
      
      {store.systemAlerts.length > maxVisible && (
        <div className="more-alerts">
          +{store.systemAlerts.length - maxVisible} more alerts
        </div>
      )}
    </div>
  );
});

export default SystemAlertsPanel;