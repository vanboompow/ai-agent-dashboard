import '@testing-library/jest-dom';
import { configure } from '@testing-library/react';

// Configure Testing Library
configure({ testIdAttribute: 'data-testid' });

// Mock matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(), // deprecated
    removeListener: vi.fn(), // deprecated
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}));

// Mock EventSource for SSE testing
global.EventSource = vi.fn().mockImplementation(() => ({
  addEventListener: vi.fn(),
  removeEventListener: vi.fn(),
  close: vi.fn(),
  readyState: 1,
  CONNECTING: 0,
  OPEN: 1,
  CLOSED: 2,
}));

// Mock D3 for component testing
vi.mock('d3', () => ({
  select: vi.fn(() => ({
    selectAll: vi.fn(() => ({
      data: vi.fn(() => ({
        enter: vi.fn(() => ({
          append: vi.fn(() => ({
            attr: vi.fn(() => ({ attr: vi.fn() })),
            style: vi.fn(() => ({ style: vi.fn() })),
            text: vi.fn(),
            on: vi.fn(),
          })),
        })),
        exit: vi.fn(() => ({
          remove: vi.fn(),
        })),
        attr: vi.fn(() => ({ attr: vi.fn() })),
        style: vi.fn(() => ({ style: vi.fn() })),
        text: vi.fn(),
        on: vi.fn(),
      })),
    })),
    append: vi.fn(() => ({
      attr: vi.fn(() => ({ attr: vi.fn() })),
      style: vi.fn(() => ({ style: vi.fn() })),
    })),
    attr: vi.fn(() => ({ attr: vi.fn() })),
    style: vi.fn(() => ({ style: vi.fn() })),
  })),
  scaleLinear: vi.fn(() => ({
    domain: vi.fn(() => ({ range: vi.fn() })),
    range: vi.fn(() => ({ domain: vi.fn() })),
  })),
  scaleOrdinal: vi.fn(() => ({
    domain: vi.fn(() => ({ range: vi.fn() })),
    range: vi.fn(() => ({ domain: vi.fn() })),
  })),
  axisBottom: vi.fn(),
  axisLeft: vi.fn(),
}));

// Mock Chart.js
vi.mock('chart.js', () => ({
  Chart: {
    register: vi.fn(),
    getChart: vi.fn(),
  },
  CategoryScale: vi.fn(),
  LinearScale: vi.fn(),
  PointElement: vi.fn(),
  LineElement: vi.fn(),
  Title: vi.fn(),
  Tooltip: vi.fn(),
  Legend: vi.fn(),
  TimeScale: vi.fn(),
  TimeSeriesScale: vi.fn(),
}));

// Mock AG Grid
vi.mock('ag-grid-react', () => ({
  AgGridReact: vi.fn(({ children, ...props }) => 
    <div data-testid="ag-grid" {...props}>{children}</div>
  ),
}));

// Global test utilities
global.TestUtils = {
  createMockAgent: (overrides = {}) => ({
    agentId: 'test-agent-1',
    status: 'idle',
    taskCategory: 'general',
    currentTask: null,
    elapsedTime: 0,
    angle: 0,
    distance: 50,
    ...overrides,
  }),

  createMockTask: (overrides = {}) => ({
    task_id: 'test-task-1',
    description: 'Test task',
    status: 'pending',
    priority: 'medium',
    sector: 'test',
    agent_id: null,
    tps: null,
    time_elapsed: null,
    ...overrides,
  }),

  createMockMetrics: (overrides = {}) => ({
    tokensPerSecond: 100,
    costPerSecondUSD: 0.001,
    totalSpend: 5.50,
    completionRate: 85,
    ...overrides,
  }),

  // Mock event source for SSE testing
  createMockEventSource: () => {
    const listeners = new Map();
    return {
      addEventListener: vi.fn((event, callback) => {
        listeners.set(event, callback);
      }),
      removeEventListener: vi.fn((event) => {
        listeners.delete(event);
      }),
      close: vi.fn(),
      dispatchEvent: (event, data) => {
        const callback = listeners.get(event);
        if (callback) {
          callback({ data: JSON.stringify(data) });
        }
      },
      readyState: 1,
    };
  },
};

// Console error suppression for tests
const originalError = console.error;
beforeAll(() => {
  console.error = (...args) => {
    if (
      typeof args[0] === 'string' &&
      args[0].includes('Warning: ReactDOM.render is no longer supported')
    ) {
      return;
    }
    originalError.call(console, ...args);
  };
});

afterAll(() => {
  console.error = originalError;
});