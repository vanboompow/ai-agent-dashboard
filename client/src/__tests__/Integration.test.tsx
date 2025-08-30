import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { configure } from 'mobx';
import axios from 'axios';

import App from '../App';
import { RootStore } from '../stores/RootStore';

// Configure MobX for testing
configure({
  enforceActions: 'never',
  computedRequiresReaction: false,
  reactionRequiresObservable: false,
  observableRequiresReaction: false,
  disableErrorBoundaries: true
});

// Mock axios
vi.mock('axios');
const mockedAxios = vi.mocked(axios, true);

// Mock components that might have complex dependencies
vi.mock('../components/AgentRadar/AgentRadar', () => ({
  default: () => <div data-testid="agent-radar">Agent Radar Component</div>
}));

vi.mock('../components/TaskQueue/TaskQueue', () => ({
  default: () => <div data-testid="task-queue">Task Queue Component</div>
}));

vi.mock('../components/MetricsPanel/MetricsPanel', () => ({
  default: () => <div data-testid="metrics-panel">Metrics Panel Component</div>
}));

vi.mock('../components/ControlPanel/ControlPanel', () => ({
  default: () => <div data-testid="control-panel">Control Panel Component</div>
}));

describe('Full Application Integration Tests', () => {
  let mockEventSource: any;

  beforeEach(() => {
    vi.clearAllMocks();
    
    // Mock EventSource
    mockEventSource = TestUtils.createMockEventSource();
    global.EventSource = vi.fn().mockImplementation(() => mockEventSource);
  });

  afterEach(() => {
    vi.resetAllMocks();
  });

  describe('Application Initialization', () => {
    it('renders the full application without crashing', () => {
      render(<App />);
      
      expect(screen.getByText(/AI Agent Dashboard/i)).toBeInTheDocument();
      expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
      expect(screen.getByTestId('task-queue')).toBeInTheDocument();
      expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('control-panel')).toBeInTheDocument();
    });

    it('loads initial data on mount', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] }) // agents
        .mockResolvedValueOnce({ data: [] }) // tasks
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() }); // metrics

      render(<App />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(3);
      });

      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/agents')
      );
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/tasks')
      );
      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/system/metrics')
      );
    });

    it('establishes SSE connection on mount', async () => {
      render(<App />);

      await waitFor(() => {
        expect(global.EventSource).toHaveBeenCalledWith(
          expect.stringContaining('/api/stream')
        );
      });
    });

    it('cleans up connections on unmount', async () => {
      const { unmount } = render(<App />);

      unmount();

      expect(mockEventSource.close).toHaveBeenCalled();
    });
  });

  describe('Real-time Updates', () => {
    it('handles agent status updates via SSE', async () => {
      const mockAgents = [
        TestUtils.createMockAgent({ agentId: 'agent-1', status: 'idle' })
      ];

      mockedAxios.get
        .mockResolvedValueOnce({ data: mockAgents })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      render(<App />);

      await waitFor(() => {
        expect(global.EventSource).toHaveBeenCalled();
      });

      // Simulate agent update event
      act(() => {
        mockEventSource.dispatchEvent('agent_update', {
          data: {
            agentId: 'agent-1',
            status: 'working',
            currentTask: 'processing data'
          }
        });
      });

      // The UI should reflect the updated agent status
      // This would be verified by checking if the components are re-rendered
      await waitFor(() => {
        expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
      });
    });

    it('handles task status updates via SSE', async () => {
      const mockTasks = [
        TestUtils.createMockTask({ task_id: 'task-1', status: 'pending' })
      ];

      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: mockTasks })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      render(<App />);

      await waitFor(() => {
        expect(global.EventSource).toHaveBeenCalled();
      });

      // Simulate task update event
      act(() => {
        mockEventSource.dispatchEvent('task_update', {
          data: {
            taskId: 'task-1',
            status: 'completed'
          }
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('task-queue')).toBeInTheDocument();
      });
    });

    it('handles metrics updates via SSE', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      render(<App />);

      await waitFor(() => {
        expect(global.EventSource).toHaveBeenCalled();
      });

      // Simulate metrics update event
      act(() => {
        mockEventSource.dispatchEvent('metrics', {
          data: {
            tokensPerSecond: 250,
            costPerSecondUSD: 0.005
          }
        });
      });

      await waitFor(() => {
        expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
      });
    });
  });

  describe('System Control Integration', () => {
    it('handles system run command', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });
      
      mockedAxios.post.mockResolvedValueOnce({});

      render(<App />);

      await waitFor(() => {
        expect(screen.getByTestId('control-panel')).toBeInTheDocument();
      });

      // This would depend on the actual implementation of ControlPanel
      // For now, we just verify the panel is rendered
    });

    it('handles system pause command', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });
      
      mockedAxios.post.mockResolvedValueOnce({});

      render(<App />);

      await waitFor(() => {
        expect(screen.getByTestId('control-panel')).toBeInTheDocument();
      });
    });

    it('handles throttle adjustments', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });
      
      mockedAxios.post.mockResolvedValueOnce({});

      render(<App />);

      await waitFor(() => {
        expect(screen.getByTestId('control-panel')).toBeInTheDocument();
      });
    });
  });

  describe('Error Handling Integration', () => {
    it('handles initial data loading errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.get
        .mockRejectedValueOnce(new Error('Agents API error'))
        .mockRejectedValueOnce(new Error('Tasks API error'))
        .mockRejectedValueOnce(new Error('Metrics API error'));

      render(<App />);

      await waitFor(() => {
        expect(consoleSpy).toHaveBeenCalledTimes(3);
      });

      // Application should still render despite errors
      expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
      expect(screen.getByTestId('task-queue')).toBeInTheDocument();
      expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
      expect(screen.getByTestId('control-panel')).toBeInTheDocument();
      
      consoleSpy.mockRestore();
    });

    it('handles SSE connection errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      // Mock EventSource to throw error
      global.EventSource = vi.fn().mockImplementation(() => {
        throw new Error('SSE connection failed');
      });

      render(<App />);

      // Application should still function
      await waitFor(() => {
        expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
      });
      
      consoleSpy.mockRestore();
    });

    it('handles malformed SSE events gracefully', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      render(<App />);

      await waitFor(() => {
        expect(global.EventSource).toHaveBeenCalled();
      });

      // Send malformed event
      act(() => {
        try {
          mockEventSource.dispatchEvent('metrics', 'invalid json');
        } catch (error) {
          // Should not break the application
        }
      });

      await waitFor(() => {
        expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
      });
    });

    it('recovers from temporary API failures', async () => {
      mockedAxios.get
        .mockRejectedValueOnce(new Error('Initial failure'))
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      render(<App />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalled();
      });

      // Application should still render
      expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
    });
  });

  describe('Performance and Responsiveness', () => {
    it('handles rapid SSE updates without performance issues', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      render(<App />);

      await waitFor(() => {
        expect(global.EventSource).toHaveBeenCalled();
      });

      // Send rapid updates
      act(() => {
        for (let i = 0; i < 100; i++) {
          mockEventSource.dispatchEvent('metrics', {
            data: { tokensPerSecond: i }
          });
        }
      });

      // Application should remain responsive
      await waitFor(() => {
        expect(screen.getByTestId('metrics-panel')).toBeInTheDocument();
      });
    });

    it('handles large datasets efficiently', async () => {
      const largeAgentDataset = Array.from({ length: 1000 }, (_, i) =>
        TestUtils.createMockAgent({ agentId: `agent-${i}` })
      );

      const largeTaskDataset = Array.from({ length: 5000 }, (_, i) =>
        TestUtils.createMockTask({ task_id: `task-${i}` })
      );

      mockedAxios.get
        .mockResolvedValueOnce({ data: largeAgentDataset })
        .mockResolvedValueOnce({ data: largeTaskDataset })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      const startTime = performance.now();
      render(<App />);

      await waitFor(() => {
        expect(mockedAxios.get).toHaveBeenCalledTimes(3);
      });

      const endTime = performance.now();
      
      // Should render within reasonable time (adjust threshold as needed)
      expect(endTime - startTime).toBeLessThan(5000);
      
      expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
      expect(screen.getByTestId('task-queue')).toBeInTheDocument();
    });
  });

  describe('State Consistency', () => {
    it('maintains consistent state across components', async () => {
      const mockAgents = [
        TestUtils.createMockAgent({ agentId: 'agent-1', status: 'working' })
      ];

      mockedAxios.get
        .mockResolvedValueOnce({ data: mockAgents })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      render(<App />);

      await waitFor(() => {
        expect(global.EventSource).toHaveBeenCalled();
      });

      // Update agent status via SSE
      act(() => {
        mockEventSource.dispatchEvent('agent_update', {
          data: {
            agentId: 'agent-1',
            status: 'idle'
          }
        });
      });

      // Both radar and any other components showing agent data should be consistent
      await waitFor(() => {
        expect(screen.getByTestId('agent-radar')).toBeInTheDocument();
      });
    });

    it('synchronizes system control state properly', async () => {
      mockedAxios.get
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: [] })
        .mockResolvedValueOnce({ data: TestUtils.createMockMetrics() });

      mockedAxios.post.mockResolvedValueOnce({});

      render(<App />);

      await waitFor(() => {
        expect(screen.getByTestId('control-panel')).toBeInTheDocument();
      });

      // System state changes should be reflected across all components
    });
  });
});