import React, { useState, useEffect } from 'react';
import Header from './components/Header';
import ConversationArea from './components/ConversationArea';
import StartButton from './components/StartButton';
import { audioService } from './services/audioService';

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

  useEffect(() => {
    // Connect to WebSocket server when component mounts
    audioService.connect();

    // Listen for new transcripts
    const handleNewTranscript = (event) => {
      const { speaker, text } = event.detail;
      setMessages(prev => [...prev, { speaker, text }]);
    };

    window.addEventListener('newTranscript', handleNewTranscript);

    // Cleanup on unmount
    return () => {
      window.removeEventListener('newTranscript', handleNewTranscript);
      audioService.disconnect();
    };
  }, []);

  const handleToggleRecording = async () => {
    try {
      if (!isRecording) {
        console.log('Starting recording...');
        await audioService.startRecording((audioData) => {
          console.log('Sending audio data to server:', audioData);
          if (audioService.socket) {
            audioService.socket.emit('audio', audioData);
          }
        });
      } else {
        console.log('Stopping recording...');
        audioService.stopRecording();
      }
      setIsRecording(!isRecording);
    } catch (error) {
      console.error('Error toggling recording:', error);
      // Handle error (e.g., show error message to user)
    }
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
