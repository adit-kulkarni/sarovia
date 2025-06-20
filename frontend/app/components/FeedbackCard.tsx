'use client';

import { FeedbackCardProps } from '../types/feedback';
import { useState } from 'react';

const severityColors = {
  minor: 'bg-yellow-100 text-yellow-800',
  moderate: 'bg-orange-100 text-orange-800',
  critical: 'bg-red-100 text-red-800'
};

// Helper function to get first N words
const getFirstNWords = (text: string, n: number): string => {
  const words = text.trim().split(/\s+/);
  return words.slice(0, n).join(' ');
};

// Helper function to truncate long messages
const truncateMessage = (text: string, maxWords: number = 10): string => {
  const words = text.trim().split(/\s+/);
  if (words.length <= maxWords) return text;
  return words.slice(0, maxWords).join(' ') + '...';
};

export default function FeedbackCard({ feedback, onFeedbackClick }: FeedbackCardProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  if (!feedback.hasMistakes) {
    return null;
  }

  const firstThreeWords = getFirstNWords(feedback.originalMessage, 3);
  const displayMessage = truncateMessage(feedback.originalMessage);

  return (
    <div 
      className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-3 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => onFeedbackClick(feedback.messageId)}
    >
      <div className="flex justify-between items-start">
        <div>
          <h4 className="text-sm font-medium text-gray-900">
            {feedback.mistakes.length} corrections for &quot;{firstThreeWords}&quot;
          </h4>
          <p className="text-xs text-gray-500 mt-1">
            {new Date(feedback.timestamp).toLocaleTimeString()}
          </p>
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            setIsExpanded(!isExpanded);
          }}
          className="text-gray-400 hover:text-gray-600"
        >
          {isExpanded ? '▼' : '▶'}
        </button>
      </div>

      {isExpanded && (
        <div className="mt-3 space-y-3">
          <div className="text-sm text-gray-600 italic">
            &quot;{displayMessage}&quot;
          </div>
          {feedback.mistakes.map((mistake, index) => (
            <div 
              key={index}
              className={`p-2 rounded ${severityColors[mistake.severity]}`}
            >
              <p className="text-sm font-medium">{mistake.category}</p>
              <p className="text-xs mt-1">
                <span className="line-through">{mistake.error}</span> → {mistake.correction}
              </p>
              <p className="text-xs mt-1">{mistake.explanation}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
} 