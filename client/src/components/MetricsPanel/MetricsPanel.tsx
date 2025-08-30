import React from 'react';
import { Metrics } from '../../stores/RootStore';
import './MetricsPanel.css';

interface MetricsPanelProps {
  metrics: Metrics;
}

const MetricsPanel: React.FC<MetricsPanelProps> = ({ metrics }) => {
  return (
    <div className="metrics-panel">
      <div className="metrics-display">
        <div className="metric-item">
          <div className="metric-label">TOKENS PER SECOND</div>
          <div className="metric-value">{metrics.tokensPerSecond.toLocaleString()}</div>
        </div>
        <div className="metric-item">
          <div className="metric-label">SPEND PER SECOND</div>
          <div className="metric-value">${metrics.costPerSecondUSD.toFixed(2)}</div>
        </div>
        <div className="metric-item">
          <div className="metric-label">TOTAL SPEND</div>
          <div className="metric-value">${metrics.totalSpend.toFixed(2)}</div>
        </div>
        <div className="metric-item">
          <div className="metric-label">COMPLETION RATE</div>
          <div className="metric-value">{metrics.completionRate.toFixed(1)}%</div>
        </div>
      </div>
    </div>
  );
};

export default MetricsPanel;