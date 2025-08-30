import React, { useState } from 'react';
import './ControlPanel.css';

interface ControlPanelProps {
  onRun: () => void;
  onPauseAll: () => void;
  onStopNew: () => void;
  onThrottle: (rate: number) => void;
  throttleRate: number;
}

const ControlPanel: React.FC<ControlPanelProps> = ({
  onRun,
  onPauseAll,
  onStopNew,
  onThrottle,
  throttleRate
}) => {
  const [localThrottle, setLocalThrottle] = useState(throttleRate);

  const handleThrottleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = parseFloat(e.target.value);
    setLocalThrottle(value);
    onThrottle(value);
  };

  return (
    <div className="control-panel">
      <div className="control-buttons">
        <button className="control-button run-button" onClick={onRun}>
          ▶ RUN
        </button>
        <button className="control-button pause-button" onClick={onPauseAll}>
          ⏸ PAUSE ALL
        </button>
        <button className="control-button stop-button" onClick={onStopNew}>
          ⏹ STOP NEW
        </button>
        <button className="control-button emergency-button">
          🚨 EMERGENCY
        </button>
      </div>
      
      <div className="throttle-control">
        <div className="throttle-label">
          THROTTLE: {localThrottle.toFixed(1)}x
        </div>
        <input
          type="range"
          min="0"
          max="3"
          step="0.1"
          value={localThrottle}
          onChange={handleThrottleChange}
          className="throttle-slider"
        />
        <div className="throttle-marks">
          <span>0x</span>
          <span>1x</span>
          <span>2x</span>
          <span>3x</span>
        </div>
      </div>

      <div className="system-status">
        <div className="status-indicator active"></div>
        <span>SYSTEM OPERATIONAL</span>
      </div>
    </div>
  );
};

export default ControlPanel;