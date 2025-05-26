'use client';

import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Mistake } from '../types/feedback';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface ProgressOverTimeChartProps {
  mistakes: Mistake[];
  feedbacks: {
    timestamp: string;
    mistakes: Mistake[];
  }[];
}

export default function ProgressOverTimeChart({ mistakes, feedbacks }: ProgressOverTimeChartProps) {
  // Group feedbacks by week
  const weeklyData = feedbacks.reduce((acc, feedback) => {
    if (!feedback.timestamp) return acc;
    const date = new Date(feedback.timestamp);
    if (isNaN(date.getTime())) return acc; // skip invalid dates

    const weekStart = new Date(date);
    weekStart.setDate(date.getDate() - date.getDay()); // Start of week (Sunday)
    const weekKey = weekStart.toISOString().split('T')[0];

    if (!acc[weekKey]) {
      acc[weekKey] = {
        totalMistakes: 0,
        minorMistakes: 0,
        moderateMistakes: 0,
        criticalMistakes: 0,
        messageCount: 0
      };
    }

    acc[weekKey].messageCount++;
    feedback.mistakes.forEach(mistake => {
      acc[weekKey].totalMistakes++;
      switch (mistake.severity) {
        case 'minor':
          acc[weekKey].minorMistakes++;
          break;
        case 'moderate':
          acc[weekKey].moderateMistakes++;
          break;
        case 'critical':
          acc[weekKey].criticalMistakes++;
          break;
      }
    });

    return acc;
  }, {} as Record<string, {
    totalMistakes: number;
    minorMistakes: number;
    moderateMistakes: number;
    criticalMistakes: number;
    messageCount: number;
  }>);

  // Convert to array and sort by date
  const sortedWeeks = Object.entries(weeklyData)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([week, data]) => ({
      week,
      ...data,
      // Calculate mistakes per message
      mistakesPerMessage: data.messageCount > 0 ? data.totalMistakes / data.messageCount : 0,
      minorPerMessage: data.messageCount > 0 ? data.minorMistakes / data.messageCount : 0,
      moderatePerMessage: data.messageCount > 0 ? data.moderateMistakes / data.messageCount : 0,
      criticalPerMessage: data.messageCount > 0 ? data.criticalMistakes / data.messageCount : 0,
    }));

  const data = {
    labels: sortedWeeks.map(w => {
      const date = new Date(w.week);
      return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }),
    datasets: [
      {
        label: 'Total Mistakes per Message',
        data: sortedWeeks.map(w => w.mistakesPerMessage),
        borderColor: '#FF9F40', // Orange
        backgroundColor: 'rgba(255, 159, 64, 0.1)',
        tension: 0.4,
      },
      {
        label: 'Minor Mistakes per Message',
        data: sortedWeeks.map(w => w.minorPerMessage),
        borderColor: '#FFCE56', // Yellow
        backgroundColor: 'rgba(255, 206, 86, 0.1)',
        tension: 0.4,
      },
      {
        label: 'Moderate Mistakes per Message',
        data: sortedWeeks.map(w => w.moderatePerMessage),
        borderColor: '#FF9F40', // Orange
        backgroundColor: 'rgba(255, 159, 64, 0.1)',
        tension: 0.4,
      },
      {
        label: 'Critical Mistakes per Message',
        data: sortedWeeks.map(w => w.criticalPerMessage),
        borderColor: '#FF6384', // Red
        backgroundColor: 'rgba(255, 99, 132, 0.1)',
        tension: 0.4,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          padding: 20,
          font: {
            size: 12
          }
        }
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            const label = context.dataset.label || '';
            const value = context.raw || 0;
            return `${label}: ${value.toFixed(2)}`;
          }
        }
      }
    },
    scales: {
      x: {
        grid: {
          display: false
        }
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Mistakes per Message'
        },
        ticks: {
          precision: 2
        }
      }
    }
  };

  return (
    <div className="h-full w-full">
      {sortedWeeks.length > 0 ? (
        <Line data={data} options={options} />
      ) : (
        <div className="h-full flex items-center justify-center text-gray-500">
          No progress data available
        </div>
      )}
    </div>
  );
} 