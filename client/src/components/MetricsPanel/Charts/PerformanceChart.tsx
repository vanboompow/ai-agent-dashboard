import React, { useRef, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import { Bar } from 'react-chartjs-2';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface AgentPerformance {
  agentId: string;
  efficiency: number; // 0-100
  tasksCompleted: number;
  avgResponseTime: number; // in ms
  errorRate: number; // 0-1
  uptime: number; // 0-1
}

interface PerformanceChartProps {
  agents: AgentPerformance[];
  metric: 'efficiency' | 'tasksCompleted' | 'avgResponseTime' | 'errorRate' | 'uptime';
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ 
  agents, 
  metric 
}) => {
  const chartRef = useRef<ChartJS<'bar', any[], any>>(null);

  const getMetricData = () => {
    switch (metric) {
      case 'efficiency':
        return agents.map(a => a.efficiency);
      case 'tasksCompleted':
        return agents.map(a => a.tasksCompleted);
      case 'avgResponseTime':
        return agents.map(a => a.avgResponseTime);
      case 'errorRate':
        return agents.map(a => a.errorRate * 100);
      case 'uptime':
        return agents.map(a => a.uptime * 100);
      default:
        return agents.map(a => a.efficiency);
    }
  };

  const getMetricConfig = () => {
    switch (metric) {
      case 'efficiency':
        return {
          label: 'Efficiency %',
          color: '#00ff00',
          unit: '%',
          max: 100
        };
      case 'tasksCompleted':
        return {
          label: 'Tasks Completed',
          color: '#00aaff',
          unit: '',
          max: Math.max(...agents.map(a => a.tasksCompleted)) * 1.1
        };
      case 'avgResponseTime':
        return {
          label: 'Avg Response Time',
          color: '#ffaa00',
          unit: 'ms',
          max: Math.max(...agents.map(a => a.avgResponseTime)) * 1.1
        };
      case 'errorRate':
        return {
          label: 'Error Rate',
          color: '#ff4400',
          unit: '%',
          max: 100
        };
      case 'uptime':
        return {
          label: 'Uptime',
          color: '#00ff88',
          unit: '%',
          max: 100
        };
      default:
        return {
          label: 'Efficiency %',
          color: '#00ff00',
          unit: '%',
          max: 100
        };
    }
  };

  const metricConfig = getMetricConfig();
  const metricData = getMetricData();

  // Color bars based on performance
  const getBarColors = () => {
    return metricData.map(value => {
      if (metric === 'avgResponseTime' || metric === 'errorRate') {
        // Lower is better
        const ratio = value / metricConfig.max;
        if (ratio < 0.3) return '#00ff00'; // Good
        if (ratio < 0.7) return '#ffaa00'; // Warning
        return '#ff4400'; // Poor
      } else {
        // Higher is better
        const ratio = value / metricConfig.max;
        if (ratio > 0.7) return '#00ff00'; // Good
        if (ratio > 0.3) return '#ffaa00'; // Warning
        return '#ff4400'; // Poor
      }
    });
  };

  const chartData = {
    labels: agents.map(a => a.agentId),
    datasets: [
      {
        label: metricConfig.label,
        data: metricData,
        backgroundColor: getBarColors().map(color => `${color}80`),
        borderColor: getBarColors(),
        borderWidth: 2,
        borderRadius: 4,
        borderSkipped: false,
      }
    ]
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 600,
      easing: 'easeInOutQuart'
    },
    interaction: {
      intersect: false,
      mode: 'index'
    },
    plugins: {
      legend: {
        display: false
      },
      tooltip: {
        enabled: true,
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: '#00ff00',
        bodyColor: '#00ff00',
        borderColor: '#00ff00',
        borderWidth: 1,
        cornerRadius: 4,
        displayColors: false,
        callbacks: {
          title: function(context) {
            return `Agent ${context[0].label}`;
          },
          label: function(context) {
            const value = context.parsed.y;
            let formattedValue = value.toFixed(metric === 'avgResponseTime' ? 0 : 1);
            
            if (metric === 'tasksCompleted') {
              formattedValue = value.toString();
            }
            
            return `${metricConfig.label}: ${formattedValue}${metricConfig.unit}`;
          },
          afterLabel: function(context) {
            const agent = agents[context.dataIndex];
            const details = [
              `Efficiency: ${agent.efficiency.toFixed(1)}%`,
              `Tasks: ${agent.tasksCompleted}`,
              `Response: ${agent.avgResponseTime.toFixed(0)}ms`,
              `Errors: ${(agent.errorRate * 100).toFixed(1)}%`,
              `Uptime: ${(agent.uptime * 100).toFixed(1)}%`
            ];
            return details;
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        grid: {
          display: false,
          drawBorder: false
        },
        ticks: {
          color: 'rgba(0, 255, 0, 0.8)',
          font: {
            family: 'JetBrains Mono',
            size: 10
          },
          maxRotation: 45
        },
        border: {
          display: false
        }
      },
      y: {
        display: true,
        beginAtZero: true,
        max: metricConfig.max,
        grid: {
          display: true,
          color: 'rgba(0, 255, 0, 0.1)',
          drawBorder: false
        },
        ticks: {
          color: 'rgba(0, 255, 0, 0.8)',
          font: {
            family: 'JetBrains Mono',
            size: 10
          },
          callback: function(value) {
            if (typeof value === 'number') {
              let formatted = value.toFixed(metric === 'avgResponseTime' ? 0 : 1);
              if (metric === 'tasksCompleted') {
                formatted = value.toString();
              }
              return formatted + metricConfig.unit;
            }
            return value;
          }
        },
        border: {
          display: false
        }
      }
    },
    elements: {
      bar: {
        borderWidth: 2
      }
    }
  };

  // Add performance indicators
  const getPerformanceStats = () => {
    if (metricData.length === 0) return { avg: 0, best: 0, worst: 0 };
    
    const avg = metricData.reduce((sum, val) => sum + val, 0) / metricData.length;
    const best = metric === 'avgResponseTime' || metric === 'errorRate' 
      ? Math.min(...metricData) 
      : Math.max(...metricData);
    const worst = metric === 'avgResponseTime' || metric === 'errorRate' 
      ? Math.max(...metricData) 
      : Math.min(...metricData);
    
    return { avg, best, worst };
  };

  const stats = getPerformanceStats();

  return (
    <div className="performance-chart-container">
      <div className="chart-header">
        <h3 className="chart-title">{metricConfig.label}</h3>
        <div className="performance-stats">
          <div className="stat-item">
            <span className="stat-label">Avg:</span>
            <span className="stat-value">
              {stats.avg.toFixed(metric === 'tasksCompleted' ? 0 : 1)}{metricConfig.unit}
            </span>
          </div>
          <div className="stat-item best">
            <span className="stat-label">Best:</span>
            <span className="stat-value">
              {stats.best.toFixed(metric === 'tasksCompleted' ? 0 : 1)}{metricConfig.unit}
            </span>
          </div>
          <div className="stat-item worst">
            <span className="stat-label">Worst:</span>
            <span className="stat-value">
              {stats.worst.toFixed(metric === 'tasksCompleted' ? 0 : 1)}{metricConfig.unit}
            </span>
          </div>
        </div>
      </div>
      <div className="chart-wrapper">
        <Bar ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
};

export default PerformanceChart;