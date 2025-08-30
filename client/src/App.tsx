import React, { useEffect, useState } from 'react';
import { observer } from 'mobx-react-lite';
import AgentRadar from './components/AgentRadar/AgentRadar';
import TaskQueue from './components/TaskQueue/TaskQueue';
import MetricsPanel from './components/MetricsPanel/MetricsPanel';
import ControlPanel from './components/ControlPanel/ControlPanel';
import { useStore } from './stores/useStore';

const App = observer(() => {
  const store = useStore();

  useEffect(() => {
    // Initialize SSE connection
    store.connectToStream();
    
    // Fetch initial data
    store.fetchAgents();
    store.fetchTasks();
    store.fetchMetrics();

    return () => {
      store.disconnectStream();
    };
  }, [store]);

  return (
    <div className="dashboard">
      <div className="experimental-badge">EXPERIMENTAL INTERFACE</div>
      
      {/* Left Panel - Task Queue */}
      <div className="panel">
        <div className="panel-header">MONITORING TASKS</div>
        <TaskQueue tasks={store.tasks} />
      </div>

      {/* Center - Radar View */}
      <div className="radar-container">
        <AgentRadar agents={store.agents} />
      </div>

      {/* Right Panel - Metrics and Controls */}
      <div className="panel">
        <div className="panel-header">MAIN METRICS</div>
        <MetricsPanel metrics={store.metrics} />
        
        <div className="panel-header" style={{ marginTop: '20px' }}>GLOBAL CONTROLS</div>
        <ControlPanel 
          onRun={() => store.systemRun()}
          onPauseAll={() => store.pauseAll()}
          onStopNew={() => store.stopNew()}
          onThrottle={(rate) => store.setThrottle(rate)}
          throttleRate={store.throttleRate}
        />
      </div>
    </div>
  );
});

export default App;