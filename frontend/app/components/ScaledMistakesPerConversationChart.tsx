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
import { Feedback, Mistake } from '../types/feedback';

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend
);

interface ScaledMistakesPerConversationChartProps {
  feedbacks: (Feedback & { conversation_id?: string })[];
}

const SCALING_MESSAGES = 30;

export default function ScaledMistakesPerConversationChart({ feedbacks }: ScaledMistakesPerConversationChartProps) {
  // Group feedbacks by conversation_id
  const conversations: Record<string, { mistakes: Mistake[]; messageCount: number }> = {};
  feedbacks.forEach(fb => {
    const convId = fb.conversation_id || 'unknown';
    if (!conversations[convId]) {
      conversations[convId] = { mistakes: [], messageCount: 0 };
    }
    conversations[convId].mistakes.push(...(fb.mistakes || []));
    conversations[convId].messageCount++;
  });

  // Prepare data for conversations with >3 messages
  const dataArr = Object.entries(conversations)
    .filter(([_, v]) => v.messageCount > 3)
    .map(([convId, v]) => {
      const modCritMistakes = v.mistakes.filter(m => m.severity === 'moderate' || m.severity === 'critical').length;
      const mistakesPerMessage = v.messageCount > 0 ? modCritMistakes / v.messageCount : 0;
      return {
        convId,
        scaledMistakes: mistakesPerMessage * SCALING_MESSAGES,
        messageCount: v.messageCount,
        modCritMistakes
      };
    });

  // Optionally, show only the most recent 10 conversations
  const sortedData = dataArr.slice(-10);

  const data = {
    labels: sortedData.map(d => `Conv ${d.convId.slice(-4)} (${d.messageCount} msgs)`),
    datasets: [
      {
        label: `Expected Moderate/Critical Mistakes (per ${SCALING_MESSAGES} msgs)` ,
        data: sortedData.map(d => d.scaledMistakes),
        backgroundColor: '#FF6384',
      }
    ]
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: true,
        position: 'top' as const,
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            const value = context.raw || 0;
            return `${value.toFixed(1)} expected mistakes`;
          }
        }
      },
      title: {
        display: true,
        text: `Expected Moderate/Critical Mistakes per ${SCALING_MESSAGES}-Message Conversation`
      }
    },
    scales: {
      x: {
        title: {
          display: true,
          text: 'Conversation (last 4 chars of ID, message count)'
        },
        grid: { display: false }
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Expected Mistakes'
        },
        ticks: {
          precision: 1
        }
      }
    }
  };

  return (
    <div className="h-full w-full">
      {sortedData.length > 0 ? (
        <Bar data={data} options={options} />
      ) : (
        <div className="h-full flex items-center justify-center text-gray-500">
          No conversation data available
        </div>
      )}
    </div>
  );
} 