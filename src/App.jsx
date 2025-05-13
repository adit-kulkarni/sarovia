import React, { useState } from 'react';
import Header from './components/Header';
import ConversationArea from './components/ConversationArea';
import StartButton from './components/StartButton';

function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [messages, setMessages] = useState([
    {
      speaker: 'AI',
      text: 'Hello! I\'m your AI assistant. How can I help you today?'
    },
    {
      speaker: 'User',
      text: 'Hi! Can you tell me about yourself?'
    },
    {
      speaker: 'AI',
      text: 'I\'m an AI assistant powered by OpenAI\'s real-time API. I can help you with various tasks and engage in natural conversations.'
    }
  ]);

  const handleToggleRecording = () => {
    setIsRecording(!isRecording);
    // TODO: Implement WebSocket connection and audio handling
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <Header />
      <main className="flex-1 overflow-hidden">
        <ConversationArea messages={messages} />
      </main>
      <StartButton isRecording={isRecording} onToggle={handleToggleRecording} />
    </div>
  );
}

export default App; 