/**
 * Performance Alerts Panel - Display real-time performance alerts
 */
import React from 'react';
import { observer } from 'mobx-react-lite';
import { useStore } from '../../stores/useStore';
import { PerformanceAlert } from '../../stores/RootStore';
import './RealTimeFeatures.css';

interface PerformanceAlertsPanelProps {
  maxVisible?: number;
}

const PerformanceAlertsPanel: React.FC<PerformanceAlertsPanelProps> = observer(({ 
  maxVisible = 10 
}) => {
  const store = useStore();
  
  const visibleAlerts = store.performanceAlerts.slice(0, maxVisible);

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'critical': return '🚨';
      case 'warning': return '⚠️';
      default: return 'ℹ️';
    }
  };

  const getSeverityClass = (severity: string) => {
    return `perf-alert alert-${severity}`;
  };

  const formatMetricValue = (value: number, metric: string) => {
    switch (metric) {
      case 'latency':
      case 'response_time':
        return `${value}ms`;
      case 'cpu_usage':
      case 'memory_usage':
      case 'completion_rate':
        return `${value}%`;
      case 'tokens_per_second':
        return `${value} TPS`;
      case 'cost_per_second':
        return `$${value.toFixed(4)}/s`;
      case 'error_rate':
        return `${value}%`;
      case 'queue_size':
        return `${value} items`;
      default:
        return value.toString();
    }
  };

  const getMetricName = (metric: string) => {
    return metric.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
  };

  const formatTimestamp = (timestamp: Date) => {
    const now = new Date();
    const diff = now.getTime() - timestamp.getTime();
    
    if (diff < 60000) { // Less than 1 minute
      return 'Just now';
    } else if (diff < 3600000) { // Less than 1 hour
      return `${Math.floor(diff / 60000)}m ago`;
    } else {
      return timestamp.toLocaleTimeString();
    }
  };

  const getThresholdDirection = (currentValue: number, threshold: number) => {
    return currentValue > threshold ? 'above' : 'below';
  };

  const calculateExceedance = (currentValue: number, threshold: number) => {
    const percentage = ((Math.abs(currentValue - threshold) / threshold) * 100);
    return percentage.toFixed(1);
  };

  return (
    <div className="performance-alerts-panel">
      <div className="panel-header">
        <h3>
          Performance Alerts
          {store.activePerformanceAlertsCount > 0 && (
            <span className="badge badge-warning">{store.activePerformanceAlertsCount} critical</span>
          )}
        </h3>
        <div className="panel-controls">
          {store.performanceAlerts.length > 0 && (
            <button 
              className="btn btn-sm btn-outline-secondary"
              onClick={() => {
                // Clear all performance alerts
                store.performanceAlerts.forEach(alert => 
                  store.dismissPerformanceAlert(alert.id)
                );
              }}
              title="Dismiss all alerts"
            >
              Dismiss All
            </button>
          )}
        </div>
      </div>

      <div className="alerts-container">
        {visibleAlerts.length === 0 ? (
          <div className="no-alerts">
            <span>📊 All performance metrics healthy</span>
          </div>
        ) : (
          visibleAlerts.map((alert: PerformanceAlert) => (
            <div key={alert.id} className={getSeverityClass(alert.severity)}>
              <div className="alert-header">
                <span className="alert-icon">{getSeverityIcon(alert.severity)}</span>
                <span className="alert-severity">{alert.severity.toUpperCase()}</span>
                <span className="alert-timestamp">{formatTimestamp(alert.timestamp)}</span>
                <button 
                  className="btn-dismiss"
                  onClick={() => store.dismissPerformanceAlert(alert.id)}
                  title="Dismiss alert"
                >
                  ✕
                </button>
              </div>
              
              <div className="alert-content">
                <div className="metric-info">
                  <h4 className="metric-name">{getMetricName(alert.metric)}</h4>
                  <div className="metric-details">
                    <div className="current-value">
                      <span className="label">Current:</span>
                      <span className={`value ${alert.severity}`}>
                        {formatMetricValue(alert.currentValue, alert.metric)}
                      </span>
                    </div>
                    <div className="threshold-value">
                      <span className="label">Threshold:</span>
                      <span className="value">
                        {formatMetricValue(alert.threshold, alert.metric)}
                      </span>
                    </div>
                  </div>
                </div>
                
                <div className="alert-summary">
                  <span className="exceedance-info">
                    {calculateExceedance(alert.currentValue, alert.threshold)}% {getThresholdDirection(alert.currentValue, alert.threshold)} threshold
                  </span>
                </div>
              </div>

              {/* Visual indicator bar */}
              <div className="metric-bar">
                <div className="bar-container">
                  <div 
                    className="threshold-marker" 
                    style={{ left: '50%' }}
                    title={`Threshold: ${formatMetricValue(alert.threshold, alert.metric)}`}
                  />
                  <div 
                    className={`current-marker ${alert.severity}`}
                    style={{ 
                      left: `${Math.min(Math.max((alert.currentValue / (alert.threshold * 2)) * 100, 0), 100)}%` 
                    }}
                    title={`Current: ${formatMetricValue(alert.currentValue, alert.metric)}`}
                  />
                </div>
              </div>
            </div>
          ))
        )}
      </div>
      
      {store.performanceAlerts.length > maxVisible && (
        <div className="more-alerts">
          +{store.performanceAlerts.length - maxVisible} more alerts
        </div>
      )}
    </div>
  );
});

export default PerformanceAlertsPanel;