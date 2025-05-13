import React from 'react';

const ConversationArea = ({ messages = [] }) => {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
      {messages.map((message, index) => (
        <div
          key={index}
          className={`flex ${
            message.speaker === 'User' ? 'justify-end' : 'justify-start'
          }`}
        >
          <div
            className={`max-w-[70%] rounded-lg p-3 ${
              message.speaker === 'User'
                ? 'bg-blue-600 text-white'
                : 'bg-white text-gray-800 shadow'
            }`}
          >
            <div className="text-xs font-semibold mb-1">
              {message.speaker}
            </div>
            <div className="text-sm">{message.text}</div>
          </div>
        </div>
      ))}
    </div>
  );
};

export default ConversationArea; 