'use client';

import { Mistake } from '../types/feedback';
import { useState } from 'react';

interface CorrectionPatternsProps {
  mistakes: Mistake[];
}

interface CorrectionPattern {
  error: string;
  correction: string;
  count: number;
  examples: string[];
  category: string;
}

export default function CorrectionPatterns({ mistakes }: CorrectionPatternsProps) {
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);

  // Group mistakes by error-correction pairs
  const patterns = mistakes.reduce((acc, mistake) => {
    const key = `${mistake.error}|${mistake.correction}`;
    if (!acc[key]) {
      acc[key] = {
        error: mistake.error,
        correction: mistake.correction,
        count: 0,
        examples: [],
        category: mistake.category
      };
    }
    acc[key].count++;
    if (acc[key].examples.length < 3) {
      acc[key].examples.push(mistake.explanation);
    }
    return acc;
  }, {} as Record<string, CorrectionPattern>);

  // Convert to array and sort by frequency
  const sortedPatterns = Object.values(patterns)
    .sort((a, b) => b.count - a.count);

  // Get unique categories
  const categories = Array.from(new Set(sortedPatterns.map(p => p.category)));

  // Filter patterns by selected category
  const filteredPatterns = selectedCategory
    ? sortedPatterns.filter(p => p.category === selectedCategory)
    : sortedPatterns;

  return (
    <div className="space-y-4">
      {/* Category Filter */}
      <div className="flex flex-wrap gap-2 mb-4">
        <button
          onClick={() => setSelectedCategory(null)}
          className={`px-3 py-1 rounded-full text-sm ${
            selectedCategory === null
              ? 'bg-orange-500 text-white'
              : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
          }`}
        >
          All Categories
        </button>
        {categories.map(category => (
          <button
            key={category}
            onClick={() => setSelectedCategory(category)}
            className={`px-3 py-1 rounded-full text-sm ${
              selectedCategory === category
                ? 'bg-orange-500 text-white'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {category}
          </button>
        ))}
      </div>

      {/* Patterns List */}
      <div className="space-y-4">
        {filteredPatterns.map((pattern, index) => (
          <div
            key={index}
            className="bg-white rounded-lg border border-gray-200 p-4 hover:border-orange-200 transition-colors"
          >
            <div className="flex items-start justify-between mb-2">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-sm font-medium text-gray-500">{pattern.category}</span>
                  <span className="text-sm text-gray-400">•</span>
                  <span className="text-sm text-gray-500">{pattern.count} occurrences</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="text-red-500 line-through">{pattern.error}</div>
                  <div className="text-gray-400">→</div>
                  <div className="text-green-600 font-medium">{pattern.correction}</div>
                </div>
              </div>
            </div>
            
            {/* Examples */}
            {pattern.examples.length > 0 && (
              <div className="mt-2 space-y-1">
                {pattern.examples.map((example, i) => (
                  <div key={i} className="text-sm text-gray-600 bg-gray-50 p-2 rounded">
                    {example}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {filteredPatterns.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            No correction patterns found for this category
          </div>
        )}
      </div>
    </div>
  );
} 