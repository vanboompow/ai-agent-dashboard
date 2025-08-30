import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { configure } from 'mobx';
import axios from 'axios';

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

// Mock EventSource
const mockEventSource = {
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  close: vi.fn(),
  readyState: 1,
};

global.EventSource = vi.fn().mockImplementation(() => mockEventSource);

describe('RootStore', () => {
  let store: RootStore;

  beforeEach(() => {
    store = new RootStore();
    vi.clearAllMocks();
  });

  afterEach(() => {
    store.disconnectStream();
    vi.resetAllMocks();
  });

  describe('Initial State', () => {
    it('initializes with empty arrays and default values', () => {
      expect(store.agents).toEqual([]);
      expect(store.tasks).toEqual([]);
      expect(store.metrics.tokensPerSecond).toBe(0);
      expect(store.metrics.costPerSecondUSD).toBe(0);
      expect(store.metrics.totalSpend).toBe(0);
      expect(store.metrics.completionRate).toBe(0);
      expect(store.throttleRate).toBe(1.0);
      expect(store.eventSource).toBeNull();
    });
  });

  describe('fetchAgents', () => {
    it('successfully fetches agents', async () => {
      const mockAgents = [
        TestUtils.createMockAgent({ agentId: 'agent-1' }),
        TestUtils.createMockAgent({ agentId: 'agent-2' })
      ];

      mockedAxios.get.mockResolvedValueOnce({
        data: mockAgents
      });

      await store.fetchAgents();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/agents')
      );
      expect(store.agents).toEqual(mockAgents);
    });

    it('handles fetch agents error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.get.mockRejectedValueOnce(new Error('Network error'));

      await store.fetchAgents();

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch agents:',
        expect.any(Error)
      );
      expect(store.agents).toEqual([]);
      
      consoleSpy.mockRestore();
    });
  });

  describe('fetchTasks', () => {
    it('successfully fetches tasks', async () => {
      const mockTasks = [
        TestUtils.createMockTask({ task_id: 'task-1' }),
        TestUtils.createMockTask({ task_id: 'task-2' })
      ];

      mockedAxios.get.mockResolvedValueOnce({
        data: mockTasks
      });

      await store.fetchTasks();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/tasks')
      );
      expect(store.tasks).toEqual(mockTasks);
    });

    it('handles fetch tasks error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.get.mockRejectedValueOnce(new Error('API error'));

      await store.fetchTasks();

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch tasks:',
        expect.any(Error)
      );
      expect(store.tasks).toEqual([]);
      
      consoleSpy.mockRestore();
    });
  });

  describe('fetchMetrics', () => {
    it('successfully fetches metrics', async () => {
      const mockMetrics = TestUtils.createMockMetrics({
        tokensPerSecond: 150,
        costPerSecondUSD: 0.002
      });

      mockedAxios.get.mockResolvedValueOnce({
        data: mockMetrics
      });

      await store.fetchMetrics();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/system/metrics')
      );
      expect(store.metrics).toEqual(mockMetrics);
    });

    it('handles fetch metrics error gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.get.mockRejectedValueOnce(new Error('Metrics API error'));

      await store.fetchMetrics();

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to fetch metrics:',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Stream Management', () => {
    it('connects to stream successfully', () => {
      store.connectToStream();

      expect(global.EventSource).toHaveBeenCalledWith(
        expect.stringContaining('/api/stream')
      );
      expect(store.eventSource).toBeTruthy();
    });

    it('sets up event listeners for different event types', () => {
      store.connectToStream();

      expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
        'metrics',
        expect.any(Function)
      );
      expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
        'agent_update',
        expect.any(Function)
      );
      expect(mockEventSource.addEventListener).toHaveBeenCalledWith(
        'task_update',
        expect.any(Function)
      );
    });

    it('handles metrics events from stream', () => {
      store.connectToStream();
      
      // Get the metrics event handler
      const metricsHandler = mockEventSource.addEventListener.mock.calls
        .find(call => call[0] === 'metrics')[1];

      const newMetrics = { tokensPerSecond: 200, costPerSecondUSD: 0.003 };
      const event = { data: JSON.stringify({ data: newMetrics }) };
      
      metricsHandler(event);

      expect(store.metrics.tokensPerSecond).toBe(200);
      expect(store.metrics.costPerSecondUSD).toBe(0.003);
    });

    it('handles agent update events from stream', () => {
      store.agents = [
        TestUtils.createMockAgent({ agentId: 'agent-1', status: 'idle' })
      ];
      
      store.connectToStream();
      
      // Get the agent update handler
      const agentHandler = mockEventSource.addEventListener.mock.calls
        .find(call => call[0] === 'agent_update')[1];

      const update = {
        data: {
          agentId: 'agent-1',
          status: 'working',
          currentTask: 'processing data'
        }
      };
      const event = { data: JSON.stringify(update) };
      
      agentHandler(event);

      expect(store.agents[0].status).toBe('working');
      expect(store.agents[0].currentTask).toBe('processing data');
    });

    it('handles task update events from stream', () => {
      store.tasks = [
        TestUtils.createMockTask({ task_id: 'task-1', status: 'pending' })
      ];
      
      store.connectToStream();
      
      // Get the task update handler
      const taskHandler = mockEventSource.addEventListener.mock.calls
        .find(call => call[0] === 'task_update')[1];

      const update = {
        data: {
          taskId: 'task-1',
          status: 'completed'
        }
      };
      const event = { data: JSON.stringify(update) };
      
      taskHandler(event);

      expect(store.tasks[0].status).toBe('completed');
    });

    it('disconnects stream properly', () => {
      store.connectToStream();
      store.disconnectStream();

      expect(mockEventSource.close).toHaveBeenCalled();
      expect(store.eventSource).toBeNull();
    });

    it('handles disconnect when no stream exists', () => {
      expect(() => store.disconnectStream()).not.toThrow();
    });
  });

  describe('System Control Actions', () => {
    it('calls systemRun API', async () => {
      mockedAxios.post.mockResolvedValueOnce({});

      await store.systemRun();

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/system/run')
      );
    });

    it('handles systemRun error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.post.mockRejectedValueOnce(new Error('System error'));

      await store.systemRun();

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to start system:',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    it('calls pauseAll API', async () => {
      mockedAxios.post.mockResolvedValueOnce({});

      await store.pauseAll();

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/system/pause-all')
      );
    });

    it('handles pauseAll error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.post.mockRejectedValueOnce(new Error('Pause error'));

      await store.pauseAll();

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to pause all:',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });

    it('calls stopNew API', async () => {
      mockedAxios.post.mockResolvedValueOnce({});

      await store.stopNew();

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/system/stop-new')
      );
    });

    it('handles stopNew error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.post.mockRejectedValueOnce(new Error('Stop error'));

      await store.stopNew();

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to stop new tasks:',
        expect.any(Error)
      );
      
      consoleSpy.mockRestore();
    });
  });

  describe('Throttle Control', () => {
    it('sets throttle rate successfully', async () => {
      mockedAxios.post.mockResolvedValueOnce({});

      await store.setThrottle(0.75);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        expect.stringContaining('/api/system/throttle'),
        { rate: 0.75 }
      );
      expect(store.throttleRate).toBe(0.75);
    });

    it('handles setThrottle error', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      mockedAxios.post.mockRejectedValueOnce(new Error('Throttle error'));
      const originalRate = store.throttleRate;

      await store.setThrottle(0.5);

      expect(consoleSpy).toHaveBeenCalledWith(
        'Failed to set throttle:',
        expect.any(Error)
      );
      expect(store.throttleRate).toBe(originalRate); // Should not change on error
      
      consoleSpy.mockRestore();
    });

    it('validates throttle rate bounds', async () => {
      mockedAxios.post.mockResolvedValueOnce({});

      // Test valid rate
      await store.setThrottle(0.5);
      expect(store.throttleRate).toBe(0.5);

      // Test edge cases (depending on implementation)
      await store.setThrottle(0.1);
      expect(mockedAxios.post).toHaveBeenLastCalledWith(
        expect.stringContaining('/api/system/throttle'),
        { rate: 0.1 }
      );
    });
  });

  describe('Reactive Updates', () => {
    it('maintains reactivity when agents change', () => {
      const initialAgents = store.agents;
      const newAgents = [TestUtils.createMockAgent()];
      
      // Simulate store update
      store.agents = newAgents;
      
      expect(store.agents).toBe(newAgents);
      expect(store.agents).not.toBe(initialAgents);
    });

    it('maintains reactivity when tasks change', () => {
      const initialTasks = store.tasks;
      const newTasks = [TestUtils.createMockTask()];
      
      store.tasks = newTasks;
      
      expect(store.tasks).toBe(newTasks);
      expect(store.tasks).not.toBe(initialTasks);
    });

    it('maintains reactivity when metrics change', () => {
      const initialMetrics = store.metrics;
      const newMetrics = TestUtils.createMockMetrics({ tokensPerSecond: 300 });
      
      store.metrics = newMetrics;
      
      expect(store.metrics).toBe(newMetrics);
      expect(store.metrics).not.toBe(initialMetrics);
    });
  });

  describe('Error Handling', () => {
    it('continues functioning after network errors', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      
      // Simulate multiple errors
      mockedAxios.get.mockRejectedValue(new Error('Network error'));
      mockedAxios.post.mockRejectedValue(new Error('API error'));

      await store.fetchAgents();
      await store.fetchTasks();
      await store.systemRun();

      expect(consoleSpy).toHaveBeenCalledTimes(3);
      expect(store.agents).toEqual([]);
      expect(store.tasks).toEqual([]);
      
      consoleSpy.mockRestore();
    });

    it('handles malformed stream events', () => {
      store.connectToStream();
      
      const metricsHandler = mockEventSource.addEventListener.mock.calls
        .find(call => call[0] === 'metrics')[1];

      // Invalid JSON
      const invalidEvent = { data: 'invalid json' };
      
      expect(() => metricsHandler(invalidEvent)).not.toThrow();
    });
  });
});