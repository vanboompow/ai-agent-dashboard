import React, { useRef, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions
} from 'chart.js';
import { Line } from 'react-chartjs-2';
import 'chartjs-plugin-streaming';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface LineChartProps {
  data: number[];
  timestamps: string[];
  label: string;
  color?: string;
  unit?: string;
  showPoints?: boolean;
}

const LineChart: React.FC<LineChartProps> = ({ 
  data, 
  timestamps, 
  label, 
  color = '#00ff00',
  unit = '',
  showPoints = false
}) => {
  const chartRef = useRef<ChartJS<'line', any[], any>>(null);

  const chartData = {
    labels: timestamps,
    datasets: [
      {
        label,
        data,
        borderColor: color,
        backgroundColor: `${color}20`,
        borderWidth: 2,
        fill: true,
        tension: 0.4,
        pointRadius: showPoints ? 3 : 0,
        pointHoverRadius: 6,
        pointBackgroundColor: color,
        pointBorderColor: '#000000',
        pointBorderWidth: 2,
      }
    ]
  };

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 300,
      easing: 'easeInOutQuad'
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
          label: function(context) {
            return `${context.parsed.y.toLocaleString()}${unit}`;
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
          display: false
        },
        border: {
          display: false
        }
      },
      y: {
        display: true,
        beginAtZero: true,
        grid: {
          display: true,
          color: 'rgba(0, 255, 0, 0.1)',
          drawBorder: false
        },
        ticks: {
          color: 'rgba(0, 255, 0, 0.6)',
          font: {
            family: 'JetBrains Mono',
            size: 10
          },
          callback: function(value) {
            if (typeof value === 'number') {
              return value.toLocaleString() + unit;
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
      point: {
        hitRadius: 10,
        hoverRadius: 8
      }
    }
  };

  // Add streaming animation effect
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const animate = () => {
      chart.update('none');
    };

    const interval = setInterval(animate, 1000);
    return () => clearInterval(interval);
  }, [data]);

  return (
    <div className="line-chart-container">
      <div className="chart-header">
        <h3 className="chart-title">{label}</h3>
        <div className="chart-value">
          {data[data.length - 1]?.toLocaleString() || 0}{unit}
        </div>
      </div>
      <div className="chart-wrapper">
        <Line ref={chartRef} data={chartData} options={options} />
      </div>
    </div>
  );
};

export default LineChart;