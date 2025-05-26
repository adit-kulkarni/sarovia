'use client';

import { Bar } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import { Mistake } from '../types/feedback';

// Register ChartJS components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface SeverityAnalysisChartProps {
  mistakes: Mistake[];
  totalConversations: number;
  totalMessages: number;
}

const severityColors = {
  minor: '#FFCE56',    // Yellow
  moderate: '#FF9F40', // Orange
  critical: '#FF6384'  // Red
};

// Standard estimates for language learning conversations
const TARGET_CONVERSATION_LENGTH = 10; // minutes
const ESTIMATED_MESSAGES_PER_10MIN = 30; // Based on typical language learning conversation pace
// Note: This is slower than native speaker pace (which would be ~50-60 messages per 10 min)
// but faster than complete beginner pace (~15-20 messages per 10 min)

export default function SeverityAnalysisChart({ mistakes, totalConversations, totalMessages }: SeverityAnalysisChartProps) {
  // Debug logging
  console.log('Chart Input:', {
    totalMistakes: mistakes.length,
    totalConversations,
    totalMessages,
    mistakesByCategory: mistakes.reduce((acc, m) => {
      acc[m.category] = (acc[m.category] || 0) + 1;
      return acc;
    }, {} as Record<string, number>)
  });

  // Step 1: Calculate mistake rates per message from your actual data
  const categorySeverityCounts = mistakes.reduce((acc, mistake) => {
    if (!acc[mistake.category]) {
      acc[mistake.category] = { minor: 0, moderate: 0, critical: 0 };
    }
    acc[mistake.category][mistake.severity]++;
    return acc;
  }, {} as Record<string, Record<string, number>>);

  // Debug logging
  console.log('Category Severity Counts:', categorySeverityCounts);

  // Step 2: Calculate mistake rates per message
  // This gives us the probability of making each type of mistake in a single message
  const mistakeRates = Object.entries(categorySeverityCounts).reduce((acc, [category, counts]) => {
    acc[category] = {
      minor: counts.minor / totalMessages,    // e.g., 20 minor mistakes / 100 messages = 0.2
      moderate: counts.moderate / totalMessages,
      critical: counts.critical / totalMessages
    };
    return acc;
  }, {} as Record<string, Record<string, number>>);

  // Debug logging
  console.log('Mistake Rates:', mistakeRates);

  // Step 3: Scale to standard 10-minute conversation
  // Multiply the per-message rates by the estimated number of messages in a 10-minute conversation
  const categories = Object.keys(categorySeverityCounts);
  const data = {
    labels: categories,
    datasets: [
      {
        label: 'Minor',
        // e.g., 0.2 mistakes per message * 30 messages = 6 expected mistakes
        data: categories.map(cat => mistakeRates[cat].minor * ESTIMATED_MESSAGES_PER_10MIN),
        backgroundColor: severityColors.minor,
        stack: 'Stack 0',
      },
      {
        label: 'Moderate',
        data: categories.map(cat => mistakeRates[cat].moderate * ESTIMATED_MESSAGES_PER_10MIN),
        backgroundColor: severityColors.moderate,
        stack: 'Stack 0',
      },
      {
        label: 'Critical',
        data: categories.map(cat => mistakeRates[cat].critical * ESTIMATED_MESSAGES_PER_10MIN),
        backgroundColor: severityColors.critical,
        stack: 'Stack 0',
      },
    ],
  };

  // Debug logging
  console.log('Chart Data:', data);

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
            const total = context.dataset.data.reduce((a: number, b: number) => a + b, 0);
            const percentage = Math.round((value / total) * 100);
            const perMessageRate = (value / ESTIMATED_MESSAGES_PER_10MIN).toFixed(3);
            return [
              `${label}: ${value.toFixed(1)} expected mistakes`,
              `(${perMessageRate} per message, ${percentage}% of total)`
            ];
          },
          title: function(context: any) {
            return `${context[0].label} (per ${TARGET_CONVERSATION_LENGTH} min)`;
          }
        }
      }
    },
    scales: {
      x: {
        stacked: true,
        grid: {
          display: false
        }
      },
      y: {
        stacked: true,
        beginAtZero: true,
        title: {
          display: true,
          text: `Expected mistakes per ${TARGET_CONVERSATION_LENGTH} minutes`
        },
        ticks: {
          precision: 1
        }
      }
    }
  };

  return (
    <div className="h-full w-full">
      {Object.keys(categorySeverityCounts).length > 0 ? (
        <Bar data={data} options={options} />
      ) : (
        <div className="h-full flex items-center justify-center text-gray-500">
          No mistake data available
        </div>
      )}
    </div>
  );
} 