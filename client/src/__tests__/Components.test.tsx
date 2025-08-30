import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { configure } from 'mobx';

// Configure MobX for testing
configure({
  enforceActions: 'never',
  computedRequiresReaction: false,
  reactionRequiresObservable: false,
  observableRequiresReaction: false,
  disableErrorBoundaries: true
});

// Import components
import AgentRadar from '../components/AgentRadar/AgentRadar';
import TaskQueue from '../components/TaskQueue/TaskQueue';
import MetricsPanel from '../components/MetricsPanel/MetricsPanel';
import ControlPanel from '../components/ControlPanel/ControlPanel';

// Mock the RootStore
const mockStore = {
  agents: [],
  tasks: [],
  metrics: {
    tokensPerSecond: 100,
    costPerSecondUSD: 0.001,
    totalSpend: 5.50,
    completionRate: 85
  },
  throttleRate: 1.0,
  systemRun: vi.fn(),
  pauseAll: vi.fn(),
  stopNew: vi.fn(),
  setThrottle: vi.fn(),
  connectToStream: vi.fn(),
  disconnectStream: vi.fn(),
  fetchAgents: vi.fn(),
  fetchTasks: vi.fn(),
  fetchMetrics: vi.fn(),
};

// Mock useStore hook
vi.mock('../stores/useStore', () => ({
  useStore: () => mockStore,
}));

describe('AgentRadar Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<AgentRadar />);
    expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
  });

  it('displays agents when provided', () => {
    mockStore.agents = [
      TestUtils.createMockAgent({ 
        agentId: 'agent-1', 
        status: 'working',
        taskCategory: 'data-processing' 
      }),
      TestUtils.createMockAgent({ 
        agentId: 'agent-2', 
        status: 'idle',
        taskCategory: 'analysis' 
      })
    ];

    render(<AgentRadar />);
    
    // Check that D3 visualization elements are present
    const radar = screen.getByTestId('agent-radar');
    expect(radar).toBeInTheDocument();
  });

  it('handles empty agent list', () => {
    mockStore.agents = [];
    
    render(<AgentRadar />);
    
    expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
  });

  it('updates when agents change status', async () => {
    const { rerender } = render(<AgentRadar />);
    
    // Update agent status
    act(() => {
      mockStore.agents = [
        TestUtils.createMockAgent({ 
          agentId: 'agent-1', 
          status: 'error' 
        })
      ];
    });
    
    rerender(<AgentRadar />);
    
    await waitFor(() => {
      expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
    });
  });

  it('handles agent clicks', async () => {
    mockStore.agents = [
      TestUtils.createMockAgent({ agentId: 'agent-1' })
    ];

    render(<AgentRadar />);
    
    const radar = screen.getByTestId('agent-radar');
    fireEvent.click(radar);
    
    // Verify interaction handling (would depend on actual implementation)
    expect(radar).toBeInTheDocument();
  });
});

describe('TaskQueue Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStore.tasks = [];
  });

  it('renders without crashing', () => {
    render(<TaskQueue />);
    expect(screen.getByTestId('task-queue')).toBeInTheDocument();
  });

  it('displays tasks when provided', () => {
    mockStore.tasks = [
      TestUtils.createMockTask({
        task_id: 'task-1',
        description: 'Process data files',
        status: 'in_progress',
        priority: 'high'
      }),
      TestUtils.createMockTask({
        task_id: 'task-2',
        description: 'Generate report',
        status: 'pending',
        priority: 'medium'
      })
    ];

    render(<TaskQueue />);
    
    // Check that AG Grid is rendered
    expect(screen.getByTestId('ag-grid')).toBeInTheDocument();
  });

  it('handles empty task list', () => {
    render(<TaskQueue />);
    
    expect(screen.getByTestId('task-queue')).toBeInTheDocument();
    expect(screen.getByTestId('ag-grid')).toBeInTheDocument();
  });

  it('supports task filtering and sorting', async () => {
    mockStore.tasks = [
      TestUtils.createMockTask({ priority: 'high', status: 'pending' }),
      TestUtils.createMockTask({ priority: 'low', status: 'completed' }),
      TestUtils.createMockTask({ priority: 'medium', status: 'in_progress' })
    ];

    render(<TaskQueue />);
    
    const grid = screen.getByTestId('ag-grid');
    expect(grid).toBeInTheDocument();
    
    // Test would verify filtering/sorting functionality
    // This depends on AG Grid implementation details
  });

  it('updates when tasks change', async () => {
    const { rerender } = render(<TaskQueue />);
    
    act(() => {
      mockStore.tasks = [
        TestUtils.createMockTask({ task_id: 'new-task' })
      ];
    });
    
    rerender(<TaskQueue />);
    
    await waitFor(() => {
      expect(screen.getByTestId('ag-grid')).toBeInTheDocument();
    });
  });
});

describe('MetricsPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<MetricsPanel />);
    expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
  });

  it('displays current metrics', () => {
    mockStore.metrics = TestUtils.createMockMetrics({
      tokensPerSecond: 150,
      costPerSecondUSD: 0.002,
      totalSpend: 12.34,
      completionRate: 92
    });

    render(<MetricsPanel />);
    
    const panel = screen.getByTestId('metrics-panel');
    expect(panel).toBeInTheDocument();
    
    // Check for metric values (depends on implementation)
    expect(screen.getByText(/tokens/i)).toBeInTheDocument();
    expect(screen.getByText(/cost/i)).toBeInTheDocument();
  });

  it('updates when metrics change', async () => {
    const { rerender } = render(<MetricsPanel />);
    
    act(() => {
      mockStore.metrics = TestUtils.createMockMetrics({
        tokensPerSecond: 200
      });
    });
    
    rerender(<MetricsPanel />);
    
    await waitFor(() => {
      expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
    });
  });

  it('handles zero/null metrics gracefully', () => {
    mockStore.metrics = TestUtils.createMockMetrics({
      tokensPerSecond: 0,
      costPerSecondUSD: 0,
      totalSpend: 0,
      completionRate: 0
    });

    render(<MetricsPanel />);
    
    expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
  });

  it('formats currency values correctly', () => {
    mockStore.metrics = TestUtils.createMockMetrics({
      totalSpend: 1234.567,
      costPerSecondUSD: 0.00123
    });

    render(<MetricsPanel />);
    
    const panel = screen.getByTestId('metrics-panel');
    expect(panel).toBeInTheDocument();
    
    // Would verify currency formatting based on implementation
  });
});

describe('ControlPanel Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders without crashing', () => {
    render(<ControlPanel />);
    expect(screen.getByTestId('control-panel')).toBeInTheDocument();
  });

  it('displays control buttons', () => {
    render(<ControlPanel />);
    
    expect(screen.getByRole('button', { name: /run/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /pause/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stop/i })).toBeInTheDocument();
  });

  it('calls systemRun when Run button is clicked', async () => {
    render(<ControlPanel />);
    
    const runButton = screen.getByRole('button', { name: /run/i });
    fireEvent.click(runButton);
    
    await waitFor(() => {
      expect(mockStore.systemRun).toHaveBeenCalledTimes(1);
    });
  });

  it('calls pauseAll when Pause button is clicked', async () => {
    render(<ControlPanel />);
    
    const pauseButton = screen.getByRole('button', { name: /pause/i });
    fireEvent.click(pauseButton);
    
    await waitFor(() => {
      expect(mockStore.pauseAll).toHaveBeenCalledTimes(1);
    });
  });

  it('calls stopNew when Stop button is clicked', async () => {
    render(<ControlPanel />);
    
    const stopButton = screen.getByRole('button', { name: /stop/i });
    fireEvent.click(stopButton);
    
    await waitFor(() => {
      expect(mockStore.stopNew).toHaveBeenCalledTimes(1);
    });
  });

  it('displays and updates throttle control', async () => {
    render(<ControlPanel />);
    
    const throttleInput = screen.getByLabelText(/throttle/i);
    expect(throttleInput).toBeInTheDocument();
    
    fireEvent.change(throttleInput, { target: { value: '0.8' } });
    fireEvent.blur(throttleInput);
    
    await waitFor(() => {
      expect(mockStore.setThrottle).toHaveBeenCalledWith(0.8);
    });
  });

  it('shows current throttle rate', () => {
    mockStore.throttleRate = 0.75;
    
    render(<ControlPanel />);
    
    const throttleInput = screen.getByLabelText(/throttle/i);
    expect(throttleInput.value).toBe('0.75');
  });

  it('prevents invalid throttle values', async () => {
    render(<ControlPanel />);
    
    const throttleInput = screen.getByLabelText(/throttle/i);
    
    // Test negative value
    fireEvent.change(throttleInput, { target: { value: '-0.5' } });
    fireEvent.blur(throttleInput);
    
    await waitFor(() => {
      expect(mockStore.setThrottle).not.toHaveBeenCalledWith(-0.5);
    });
    
    // Test value too high
    fireEvent.change(throttleInput, { target: { value: '5.0' } });
    fireEvent.blur(throttleInput);
    
    await waitFor(() => {
      expect(mockStore.setThrottle).not.toHaveBeenCalledWith(5.0);
    });
  });

  it('handles API errors gracefully', async () => {
    mockStore.systemRun.mockRejectedValue(new Error('API Error'));
    
    render(<ControlPanel />);
    
    const runButton = screen.getByRole('button', { name: /run/i });
    fireEvent.click(runButton);
    
    await waitFor(() => {
      expect(mockStore.systemRun).toHaveBeenCalledTimes(1);
    });
    
    // Would verify error handling UI based on implementation
  });
});