'use client';

import { FeedbackPanelProps } from '../types/feedback';
import FeedbackCard from './FeedbackCard';
import { useEffect, useRef } from 'react';

export default function FeedbackPanel({ feedbacks, onFeedbackClick }: FeedbackPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new feedback arrives
  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.scrollTop = panelRef.current.scrollHeight;
    }
  }, [feedbacks]);

  return (
    <div 
      ref={panelRef}
      className="flex-1 overflow-y-auto space-y-2"
    >
      {feedbacks.length === 0 ? (
        <div className="text-center text-gray-500 py-4">
          No feedback yet
        </div>
      ) : (
        feedbacks.map((feedback) => (
          <FeedbackCard
            key={feedback.messageId}
            feedback={feedback}
            onFeedbackClick={onFeedbackClick}
          />
        ))
      )}
    </div>
  );
} 