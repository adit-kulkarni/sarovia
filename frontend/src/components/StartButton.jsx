import React from 'react';

const StartButton = ({ isRecording, onToggle }) => {
  return (
    <div className="fixed bottom-8 left-1/2 transform -translate-x-1/2">
      <button
        onClick={onToggle}
        className={`relative flex items-center justify-center w-16 h-16 rounded-full shadow-lg transition-all duration-300 ${
          isRecording
            ? 'bg-red-500 hover:bg-red-600'
            : 'bg-blue-600 hover:bg-blue-700'
        }`}
      >
        <div
          className={`absolute inset-0 rounded-full ${
            isRecording ? 'animate-ping bg-red-400 opacity-75' : ''
          }`}
        />
        <div className="relative">
          {isRecording ? (
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <rect x="6" y="6" width="12" height="12" />
            </svg>
          ) : (
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"
              />
            </svg>
          )}
        </div>
      </button>
    </div>
  );
};

export default StartButton; 