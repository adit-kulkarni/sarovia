'use client';

import React from 'react';
import { LessonProgress } from '../types/feedback';

interface LessonProgressIndicatorProps {
  progress: LessonProgress;
}

export default function LessonProgressIndicator({ 
  progress
}: LessonProgressIndicatorProps) {
  const progressPercentage = Math.min((progress.turns / progress.required) * 100, 100);

  return (
    <div className="bg-white/90 rounded-lg border border-orange-200 p-4 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
          Lesson Progress
        </h3>
        <span className="text-sm text-gray-600">
          {progress.turns}/{progress.required} turns
        </span>
      </div>
      
      {/* Progress Bar */}
      <div className="w-full bg-gray-200 rounded-full h-3 mb-4">
        <div 
          className={`h-3 rounded-full transition-all duration-300 ${
            progress.can_complete 
              ? 'bg-green-500' 
              : 'bg-orange-500'
          }`}
          style={{ width: `${progressPercentage}%` }}
        />
      </div>
      
      {/* Status Message */}
      <div className="mb-2">
        {progress.can_complete ? (
          <p className="text-sm text-green-700 font-medium">
            ✅ Minimum conversation turns completed! Use the "Complete Lesson" button below to finish.
          </p>
        ) : (
          <p className="text-sm text-gray-600">
            Continue the conversation to reach the minimum turn requirement.
            {progress.required - progress.turns} more turn{progress.required - progress.turns !== 1 ? 's' : ''} needed.
          </p>
        )}
      </div>
    </div>
  );
} 