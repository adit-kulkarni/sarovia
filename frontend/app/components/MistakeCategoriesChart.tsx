'use client';

import { Pie } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  CategoryScale,
} from 'chart.js';
import { Mistake } from '../types/feedback';

// Register ChartJS components
ChartJS.register(ArcElement, Tooltip, Legend, CategoryScale);

interface MistakeCategoriesChartProps {
  mistakes: Mistake[];
}

const categoryColors = {
  grammar: '#FF6384',
  vocabulary: '#36A2EB',
  spelling: '#FFCE56',
  punctuation: '#4BC0C0',
  syntax: '#9966FF',
  'word choice': '#FF9F40',
  'register/formality': '#C9CBCF',
  other: '#7ED321'
};

export default function MistakeCategoriesChart({ mistakes }: MistakeCategoriesChartProps) {
  // Count mistakes by category
  const categoryCounts = mistakes.reduce((acc, mistake) => {
    acc[mistake.category] = (acc[mistake.category] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  // Prepare data for the chart
  const data = {
    labels: Object.keys(categoryCounts),
    datasets: [
      {
        data: Object.values(categoryCounts),
        backgroundColor: Object.keys(categoryCounts).map(cat => categoryColors[cat as keyof typeof categoryColors] || categoryColors.other),
        borderWidth: 1,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'right' as const,
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
            const label = context.label || '';
            const value = context.raw || 0;
            const total = context.dataset.data.reduce((a: number, b: number) => a + b, 0);
            const percentage = Math.round((value / total) * 100);
            return `${label}: ${value} (${percentage}%)`;
          }
        }
      }
    }
  };

  return (
    <div className="h-full w-full">
      {Object.keys(categoryCounts).length > 0 ? (
        <Pie data={data} options={options} />
      ) : (
        <div className="h-full flex items-center justify-center text-gray-500">
          No mistake data available
        </div>
      )}
    </div>
  );
} 