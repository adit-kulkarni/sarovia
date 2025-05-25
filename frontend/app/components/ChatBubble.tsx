'use client';

import { ChatBubbleProps, mistakeCategoryEmojis, Mistake } from '../types/feedback';
import React from 'react';

export default function ChatBubble({ message, hasFeedback, onFeedbackClick }: ChatBubbleProps) {
  // Debug log to check feedback presence
  console.log('ChatBubble render:', message.id, message.feedback);

  // Only show emoji indicators for user messages with feedback
  const feedback = message.feedback;
  const isUser = message.role === 'user';

  // Build emoji indicators
  let emojiIndicators: React.ReactNode = null;
  if (isUser && feedback) {
    if (!feedback.hasMistakes) {
      emojiIndicators = (
        <span className="text-green-600 text-lg mr-1">✅</span>
      );
    } else {
      // Count mistakes by category
      const categoryCounts: Record<string, number> = {};
      feedback.mistakes.forEach((m: Mistake) => {
        const cat = m.category;
        categoryCounts[cat] = (categoryCounts[cat] || 0) + 1;
      });
      emojiIndicators = (
        <div className="flex space-x-1 items-center">
          {Object.entries(categoryCounts).map(([cat, count]) => (
            <span key={cat} className="relative text-lg">
              {mistakeCategoryEmojis[cat] || '❓'}
              {count > 1 && (
                <span className="absolute -top-1 -right-2 bg-red-500 text-white text-xs rounded-full px-1 min-w-[16px] text-center">
                  ×{count}
                </span>
              )}
            </span>
          ))}
        </div>
      );
    }
  }

  return (
    <div className={`relative max-w-xl mb-2 ${isUser ? 'ml-auto' : 'mr-auto'}`}>
      {/* Emoji indicators in top-left for user messages */}
      {isUser && feedback && (
        <div className="absolute -top-3 left-2 flex z-10">
          {emojiIndicators}
        </div>
      )}
      <div
        className={`rounded-lg px-4 py-2 shadow-md ${isUser ? 'bg-orange-100 text-gray-900' : 'bg-white text-gray-800'} relative`}
        onClick={hasFeedback ? onFeedbackClick : undefined}
        style={{ cursor: hasFeedback ? 'pointer' : 'default' }}
      >
        <span className="block whitespace-pre-line">{message.content}</span>
      </div>
    </div>
  );
} 