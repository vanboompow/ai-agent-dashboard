export { default as LineChart } from './LineChart';
export { default as CostChart } from './CostChart';
export { default as PerformanceChart } from './PerformanceChart';

// Export types for convenience
export interface ChartDataPoint {
  timestamp: string;
  value: number;
}

export interface CostData {
  timestamp: string;
  totalSpend: number;
  costPerSecond: number;
  projected?: boolean;
}

export interface AgentPerformance {
  agentId: string;
  efficiency: number;
  tasksCompleted: number;
  avgResponseTime: number;
  errorRate: number;
  uptime: number;
}