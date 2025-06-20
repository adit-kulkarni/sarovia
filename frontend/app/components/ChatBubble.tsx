'use client';

import { ChatBubbleProps, Mistake } from '../types/feedback';
import React, { useState } from 'react';
import Image from 'next/image';

export default function ChatBubble({ message, hasFeedback, onFeedbackClick, language = 'es' }: ChatBubbleProps) {
  const [translation, setTranslation] = useState<string>('');
  const [isTranslating, setIsTranslating] = useState(false);
  const [showTranslation, setShowTranslation] = useState(false);

  // Debug log to check feedback presence
  console.log('ChatBubble render:', message.id, message.feedback);

  // Only show emoji indicators for user messages with feedback
  const feedback = message.feedback;
  const isUser = message.role === 'user';

  // Check if text is in a non-English language (should be translated)
  const shouldTranslate = (text: string, lang: string): boolean => {
    // Only translate if the language is not English
    return lang !== 'en';
  };

  const translateText = async () => {
    if (translation) {
      setShowTranslation(!showTranslation);
      return;
    }

    setIsTranslating(true);
    try {
      const response = await fetch(
        `https://translate.googleapis.com/translate_a/single?client=gtx&sl=${language}&tl=en&dt=t&q=${encodeURIComponent(message.content)}`
      );
      const data = await response.json();
      
      // Google Translate returns an array of translation segments
      // We need to concatenate all segments to get the full translation
      let translatedText = '';
      if (data && data[0]) {
        for (let i = 0; i < data[0].length; i++) {
          if (data[0][i] && data[0][i][0]) {
            translatedText += data[0][i][0];
          }
        }
      }
      
      setTranslation(translatedText || 'Translation failed');
      setShowTranslation(true);
    } catch (error) {
      console.error('Translation failed:', error);
      setTranslation('Translation failed');
      setShowTranslation(true);
    } finally {
      setIsTranslating(false);
    }
  };

  // Build severity indicators
  let severityIndicators: React.ReactNode = null;
  if (isUser && feedback) {
    if (!feedback.hasMistakes) {
      severityIndicators = (
        <span className="text-green-600 text-lg mr-1">✅</span>
      );
    } else {
      // Count mistakes by severity
      const severityCounts = { minor: 0, moderate: 0, critical: 0 };
      feedback.mistakes.forEach((m: Mistake) => {
        severityCounts[m.severity as keyof typeof severityCounts]++;
      });

      // Color scheme matching Language Features chart
      const severityStyles = {
        minor: 'bg-yellow-200 text-yellow-800',     // rgba(255, 206, 86, 1) equivalent
        moderate: 'bg-orange-200 text-orange-800',  // rgba(255, 159, 64, 1) equivalent  
        critical: 'bg-red-200 text-red-800'         // rgba(255, 99, 132, 1) equivalent
      };

      severityIndicators = (
        <div className="flex space-x-1 items-center">
          {Object.entries(severityCounts).map(([severity, count]) => {
            if (count === 0) return null;
            return (
              <span
                key={severity}
                className={`inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full text-xs font-medium ${severityStyles[severity as keyof typeof severityStyles]}`}
              >
                {count}
              </span>
            );
          })}
        </div>
      );
    }
  }

  return (
    <div className={`relative max-w-xl mb-2 ${isUser ? 'ml-auto' : 'mr-auto'}`}>
      {/* Severity indicators in top-left for user messages */}
      {isUser && feedback && (
        <div className="absolute -top-3 left-2 flex z-10">
          {severityIndicators}
        </div>
      )}
      
      {/* Translation button for non-English messages */}
      {shouldTranslate(message.content, language) && (
        <div className="absolute top-1 right-1 z-10">
          <button
            onClick={translateText}
            disabled={isTranslating}
            className="hover:bg-white hover:bg-opacity-20 p-1.5 rounded-full transition-all duration-200 flex items-center justify-center"
            title={showTranslation ? "Show original" : "Translate to English"}
          >
            {isTranslating ? (
              <span className="animate-spin text-gray-600 text-sm">⟳</span>
            ) : (
              <Image 
                src="/translate_svg.svg" 
                alt="Translate" 
                width={16}
                height={16}
                className={`w-4 h-4 transition-all duration-200 ${
                  isUser 
                    ? 'filter brightness-0 invert opacity-80 hover:opacity-100' 
                    : 'filter brightness-0 opacity-60 hover:opacity-80'
                }`}
              />
            )}
          </button>
        </div>
      )}

      <div
        className={`rounded-lg px-4 py-2 shadow-md ${isUser ? 'bg-orange-500 text-white' : 'bg-gray-200 text-gray-800'} relative`}
        onClick={hasFeedback ? onFeedbackClick : undefined}
        style={{ cursor: hasFeedback ? 'pointer' : 'default' }}
      >
        <span className="block whitespace-pre-line">{message.content}</span>
        
        {/* Translation display */}
        {showTranslation && translation && (
          <div className={`mt-2 pt-2 border-t ${isUser ? 'border-orange-300' : 'border-gray-300'} text-sm opacity-80`}>
            {translation}
          </div>
        )}
      </div>
    </div>
  );
} 