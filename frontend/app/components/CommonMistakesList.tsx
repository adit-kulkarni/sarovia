'use client';

import { Mistake } from '../types/feedback';

interface CommonMistakesListProps {
  mistakes: Mistake[];
}

interface MistakeType {
  category: string;
  type: string;
  count: number;
  examples: {
    error: string;
    correction: string;
    explanation: string;
  }[];
}

export default function CommonMistakesList({ mistakes }: CommonMistakesListProps) {
  // Group mistakes by category and type
  const mistakeTypes = mistakes.reduce((acc, mistake) => {
    const key = `${mistake.category}:${mistake.type}`;
    if (!acc[key]) {
      acc[key] = {
        category: mistake.category,
        type: mistake.type,
        count: 0,
        examples: []
      };
    }
    acc[key].count++;
    
    // Keep up to 2 unique examples
    if (acc[key].examples.length < 2 && 
        !acc[key].examples.some(ex => ex.error === mistake.error)) {
      acc[key].examples.push({
        error: mistake.error,
        correction: mistake.correction,
        explanation: mistake.explanation
      });
    }
    
    return acc;
  }, {} as Record<string, MistakeType>);

  // Convert to array and sort by frequency
  const sortedMistakes = Object.values(mistakeTypes)
    .sort((a, b) => b.count - a.count)
    .slice(0, 5); // Top 5 most common mistakes

  if (sortedMistakes.length === 0) {
    return (
      <div className="text-center text-gray-500 py-4">
        No mistake data available
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {sortedMistakes.map((mistake, index) => (
        <div key={index} className="bg-orange-50 rounded-lg p-4">
          <div className="flex justify-between items-start mb-2">
            <div>
              <h4 className="font-medium text-gray-900 capitalize">
                {mistake.type.replace(/_/g, ' ')}
              </h4>
              <p className="text-sm text-gray-600 capitalize">
                {mistake.category.replace(/_/g, ' ')}
              </p>
            </div>
            <span className="bg-orange-100 text-orange-800 px-2 py-1 rounded-full text-sm font-medium">
              {mistake.count} {mistake.count === 1 ? 'time' : 'times'}
            </span>
          </div>
          
          <div className="space-y-2 mt-3">
            {mistake.examples.map((example, exIndex) => (
              <div key={exIndex} className="text-sm">
                <div className="flex items-start space-x-2">
                  <span className="text-red-500">✗</span>
                  <span className="text-gray-600">{example.error}</span>
                </div>
                <div className="flex items-start space-x-2">
                  <span className="text-green-500">✓</span>
                  <span className="text-gray-800">{example.correction}</span>
                </div>
                <p className="text-gray-500 mt-1 ml-6 text-xs">
                  {example.explanation}
                </p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
} 