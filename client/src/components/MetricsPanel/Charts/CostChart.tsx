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
import { Line } from 'react-chartjs-2';

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

interface CostData {
  timestamp: string;
  totalSpend: number;
  costPerSecond: number;
  projected?: number;
}

interface CostChartProps {
  data: CostData[];
  projectionHours?: number;
}

const CostChart: React.FC<CostChartProps> = ({ 
  data, 
  projectionHours = 24 
}) => {
  const chartRef = useRef<ChartJS<'line', any[], any>>(null);

  // Calculate projected costs
  const currentCostPerSecond = data[data.length - 1]?.costPerSecond || 0;
  const projectedCost = currentCostPerSecond * 3600 * projectionHours;
  const currentTotal = data[data.length - 1]?.totalSpend || 0;

  // Extend data with projections
  const extendedData = [...data];
  if (data.length > 0) {
    const lastTimestamp = new Date(data[data.length - 1].timestamp);
    for (let i = 1; i <= projectionHours; i++) {
      const projectedTimestamp = new Date(lastTimestamp.getTime() + i * 3600000);
      extendedData.push({
        timestamp: projectedTimestamp.toISOString(),
        totalSpend: currentTotal + (currentCostPerSecond * 3600 * i),
        costPerSecond: currentCostPerSecond,
        projected: true
      });
    }
  }

  const chartData = {
    labels: extendedData.map(d => new Date(d.timestamp).toLocaleTimeString()),
    datasets: [
      {
        label: 'Total Spend',
        data: extendedData.map(d => d.totalSpend),
        borderColor: '#00ff00',
        backgroundColor: 'rgba(0, 255, 0, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.1,
        pointRadius: 0,
        pointHoverRadius: 6,
        segment: {
          borderDash: (ctx: any) => 
            ctx.p1DataIndex >= data.length ? [5, 5] : undefined,
        }
      },
      {
        label: 'Cost/Second (x1000)',
        data: extendedData.map(d => d.costPerSecond * 1000),
        borderColor: '#ffaa00',
        backgroundColor: 'rgba(255, 170, 0, 0.1)',
        borderWidth: 1,
        fill: false,
        tension: 0.1,
        pointRadius: 0,
        pointHoverRadius: 4,
        yAxisID: 'y1',
        segment: {
          borderDash: (ctx: any) => 
            ctx.p1DataIndex >= data.length ? [3, 3] : undefined,
        }
      }
    ]
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 400,
      easing: 'easeInOutQuad'
    },
    interaction: {
      intersect: false,
      mode: 'index'
    },
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
        labels: {
          color: '#00ff00',
          font: {
            family: 'JetBrains Mono',
            size: 10
          },
          usePointStyle: true,
          padding: 15
        }
      },
      tooltip: {
        enabled: true,
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        titleColor: '#00ff00',
        bodyColor: '#00ff00',
        borderColor: '#00ff00',
        borderWidth: 1,
        cornerRadius: 4,
        displayColors: true,
        callbacks: {
          title: function(context) {
            const index = context[0].dataIndex;
            const isProjected = index >= data.length;
            return `${context[0].label}${isProjected ? ' (Projected)' : ''}`;
          },
          label: function(context) {
            const value = context.parsed.y;
            if (context.datasetIndex === 0) {
              return `Total: $${value.toFixed(2)}`;
            } else {
              return `Rate: $${(value / 1000).toFixed(4)}/s`;
            }
          }
        }
      }
    },
    scales: {
      x: {
        display: true,
        grid: {
          display: true,
          color: 'rgba(0, 255, 0, 0.1)',
          drawBorder: false
        },
        ticks: {
          color: 'rgba(0, 255, 0, 0.6)',
          font: {
            family: 'JetBrains Mono',
            size: 9
          },
          maxTicksLimit: 8
        },
        border: {
          display: false
        }
      },
      y: {
        type: 'linear',
        display: true,
        position: 'left',
        beginAtZero: true,
        grid: {
          display: true,
          color: 'rgba(0, 255, 0, 0.1)',
          drawBorder: false
        },
        ticks: {
          color: '#00ff00',
          font: {
            family: 'JetBrains Mono',
            size: 10
          },
          callback: function(value) {
            if (typeof value === 'number') {
              return '$' + value.toFixed(2);
            }
            return value;
          }
        },
        border: {
          display: false
        }
      },
      y1: {
        type: 'linear',
        display: true,
        position: 'right',
        grid: {
          drawOnChartArea: false,
        },
        ticks: {
          color: '#ffaa00',
          font: {
            family: 'JetBrains Mono',
            size: 10
          },
          callback: function(value) {
            if (typeof value === 'number') {
              return '$' + (value / 1000).toFixed(4);
            }
            return value;
          }
        },
        border: {
          display: false
        }
      }
    }
  };

  // Highlight projection section
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || data.length === 0) return;

    const ctx = chart.ctx;
    const chartArea = chart.chartArea;

    const projectionStart = (data.length / extendedData.length) * chartArea.right;

    // Add custom drawing for projection highlight
    chart.draw();
    
    ctx.save();
    ctx.fillStyle = 'rgba(255, 170, 0, 0.05)';
    ctx.fillRect(projectionStart, chartArea.top, chartArea.right - projectionStart, chartArea.bottom - chartArea.top);
    
    ctx.strokeStyle = 'rgba(255, 170, 0, 0.3)';
    ctx.setLineDash([2, 2]);
    ctx.beginPath();
    ctx.moveTo(projectionStart, chartArea.top);
    ctx.lineTo(projectionStart, chartArea.bottom);
    ctx.stroke();
    ctx.restore();
  }, [data, extendedData]);

  return (
    <div className="cost-chart-container">
      <div className="chart-header">
        <h3 className="chart-title">Cost Analysis</h3>
        <div className="cost-summary">
          <div className="cost-item">
            <span className="cost-label">Total:</span>
            <span className="cost-value">${currentTotal.toFixed(2)}</span>
          </div>
          <div className="cost-item">
            <span className="cost-label">Rate:</span>
            <span className="cost-value">${currentCostPerSecond.toFixed(4)}/s</span>
          </div>
          <div className="cost-item projection">
            <span className="cost-label">{projectionHours}h Proj:</span>
            <span className="cost-value">${(currentTotal + projectedCost).toFixed(2)}</span>
          </div>
        </div>
      </div>
      <div className="chart-wrapper">
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
};

export default CostChart;