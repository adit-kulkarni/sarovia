'use client';

import { useEffect, useState, useRef } from 'react';

interface Message {
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export default function Home() {
  const [backendStatus, setBackendStatus] = useState<'disconnected' | 'connecting' | 'connected'>('disconnected');
  const [openaiStatus, setOpenaiStatus] = useState<'disconnected' | 'connected'>('disconnected');
  const [messages, setMessages] = useState<Message[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [selectedLevel, setSelectedLevel] = useState('A1');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentStreamingMessageRef = useRef<number | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const audioBufferRef = useRef<Int16Array[]>([]);
  const isPlayingRef = useRef(false);
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);

  // Scroll to bottom of messages
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Initialize AudioContext
  const initAudioContext = () => {
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
    }
  };

  // Function to stop audio playback
  const stopAudioPlayback = () => {
    if (currentSourceRef.current) {
      currentSourceRef.current.stop();
      currentSourceRef.current = null;
    }
    isPlayingRef.current = false;
    audioBufferRef.current = []; // Clear the buffer
  };

  // Function to play next chunk in buffer
  const playNextChunk = async () => {
    if (isPlayingRef.current || audioBufferRef.current.length === 0) return;

    isPlayingRef.current = true;
    const audioData = audioBufferRef.current.shift();

    if (!audioData || !audioContextRef.current) {
      isPlayingRef.current = false;
      return;
    }

    try {
      // Convert Int16Array to Float32Array
      const float32Data = new Float32Array(audioData.length);
      for (let i = 0; i < audioData.length; i++) {
        float32Data[i] = audioData[i] / 32768.0;
      }

      // Create audio buffer
      const audioBuffer = audioContextRef.current.createBuffer(1, float32Data.length, 24000);
      audioBuffer.getChannelData(0).set(float32Data);

      // Create source and play
      const source = audioContextRef.current.createBufferSource();
      currentSourceRef.current = source;
      source.buffer = audioBuffer;
      source.connect(audioContextRef.current.destination);

      // Set up the onended handler before starting
      source.onended = () => {
        currentSourceRef.current = null;
        isPlayingRef.current = false;
        // Play next chunk if available
        if (audioBufferRef.current.length > 0) {
          playNextChunk();
        }
      };

      // Start playback
      source.start();
    } catch (error) {
      console.error('Error playing audio chunk:', error);
      isPlayingRef.current = false;
      // Try to play next chunk if this one failed
      if (audioBufferRef.current.length > 0) {
        playNextChunk();
      }
    }
  };

  useEffect(() => {
    // Initialize WebSocket connection
    wsRef.current = new WebSocket('ws://localhost:8000/ws');

    wsRef.current.onopen = () => {
      setBackendStatus('connected');
      // Send initial level selection
      wsRef.current?.send(JSON.stringify({
        type: 'session.init',
        level: selectedLevel
      }));
      setMessages(prev => [...prev, {
        type: 'assistant' as const,
        content: 'Connected to backend WebSocket',
        timestamp: new Date()
      }]);
      initAudioContext();
    };

    wsRef.current.onclose = () => {
      setBackendStatus('disconnected');
      setMessages(prev => [...prev, {
        type: 'assistant' as const,
        content: 'Disconnected from backend WebSocket',
        timestamp: new Date()
      }]);
    };

    wsRef.current.onerror = (error) => {
      setBackendStatus('disconnected');
      setMessages(prev => [...prev, {
        type: 'assistant' as const,
        content: `WebSocket error: ${error}`,
        timestamp: new Date()
      }]);
    };

    wsRef.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      // Handle different message types
      switch (data.type) {
        case 'session.created':
          setOpenaiStatus('connected');
          break;
        case 'conversation.item.input_audio_transcription.completed':
          setMessages(prev => [...prev, {
            type: 'user' as const,
            content: data.transcript,
            timestamp: new Date()
          }]);
          break;
        case 'response.audio_transcript.delta':
          // Handle streaming transcript
          if (currentStreamingMessageRef.current === null) {
            // Start new streaming message
            setMessages(prev => {
              const newMessages = [...prev, {
                type: 'assistant' as const,
                content: data.delta,
                timestamp: new Date(),
                isStreaming: true
              }];
              currentStreamingMessageRef.current = newMessages.length - 1;
              return newMessages;
            });
          } else {
            // Update existing streaming message
            setMessages(prev => {
              const newMessages = [...prev];
              const currentMessage = newMessages[currentStreamingMessageRef.current!];
              newMessages[currentStreamingMessageRef.current!] = {
                ...currentMessage,
                content: currentMessage.content + data.delta
              };
              return newMessages;
            });
          }
          break;
        case 'response.audio_transcript.done':
          // Finalize streaming message
          if (currentStreamingMessageRef.current !== null) {
            setMessages(prev => {
              const newMessages = [...prev];
              const currentMessage = newMessages[currentStreamingMessageRef.current!];
              newMessages[currentStreamingMessageRef.current!] = {
                ...currentMessage,
                isStreaming: false
              };
              return newMessages;
            });
            currentStreamingMessageRef.current = null;
          }
          break;
        case 'input_audio_buffer.speech_started':
          // Stop AI audio playback when user starts speaking
          stopAudioPlayback();
          break;
        case 'response.audio.delta':
          // Handle audio data
          try {
            const audioData = atob(data.delta);
            const audioArray = new Int16Array(audioData.length / 2);
            for (let i = 0; i < audioData.length; i += 2) {
              audioArray[i / 2] = (audioData.charCodeAt(i) | (audioData.charCodeAt(i + 1) << 8));
            }
            audioBufferRef.current.push(audioArray);
            playNextChunk();
          } catch (error) {
            console.error('Error processing audio data:', error);
          }
          break;
        case 'error':
          setMessages(prev => [...prev, {
            type: 'assistant' as const,
            content: `Error: ${data.error.message}`,
            timestamp: new Date()
          }]);
          break;
      }
    };

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      stopAudioPlayback();
    };
  }, []);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Create AudioContext with the correct sample rate
      audioContextRef.current = new AudioContext({
        sampleRate: 24000 // OpenAI expects 24kHz
      });

      // Create audio source from the stream
      const source = audioContextRef.current.createMediaStreamSource(stream);
      
      // Create a script processor to handle the audio data
      const processor = audioContextRef.current.createScriptProcessor(1024, 1, 1);
      
      processor.onaudioprocess = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          // Get the audio data
          const inputData = e.inputBuffer.getChannelData(0);
          
          // Convert Float32Array to Int16Array
          const pcmData = new Int16Array(inputData.length);
          for (let i = 0; i < inputData.length; i++) {
            // Convert float to int16
            const s = Math.max(-1, Math.min(1, inputData[i]));
            pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
          }
          
          // Convert to base64
          const uint8Array = new Uint8Array(pcmData.buffer);
          const base64Audio = btoa(
            Array.from(uint8Array)
              .map(byte => String.fromCharCode(byte))
              .join('')
          );
          
          // Send to backend
          wsRef.current.send(JSON.stringify({
            type: 'input_audio_buffer.append',
            audio: base64Audio
          }));
        }
      };

      // Connect the nodes
      source.connect(processor);
      processor.connect(audioContextRef.current.destination);

      setIsRecording(true);
      setMessages(prev => [...prev, {
        type: 'assistant' as const,
        content: 'Started recording',
        timestamp: new Date()
      }]);
    } catch (error) {
      console.error('Error starting recording:', error);
      setMessages(prev => [...prev, {
        type: 'assistant' as const,
        content: `Error starting recording: ${error}`,
        timestamp: new Date()
      }]);
    }
  };

  const stopRecording = () => {
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setIsRecording(false);
    setMessages(prev => [...prev, {
      type: 'assistant' as const,
      content: 'Stopped recording',
      timestamp: new Date()
    }]);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-100 flex flex-col items-center justify-center">
      <div className="w-full max-w-md mx-auto flex flex-col h-[90vh] rounded-3xl shadow-xl border border-orange-100 bg-white/80 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 bg-white/90 border-b border-orange-100">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-orange-200 flex items-center justify-center text-lg font-bold text-orange-700">
              AI
            </div>
            <div>
              <h1 className="text-lg font-semibold text-gray-800">Voice Assistant</h1>
              <p className="text-sm text-gray-500">
                {backendStatus === 'connected' ? 'Connected' : 'Disconnected'}
              </p>
            </div>
          </div>
          <div className="text-sm font-medium text-orange-600">
            Level: {selectedLevel}
          </div>
        </div>

        {/* Messages Container */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                  message.type === 'user'
                    ? 'bg-orange-500 text-white rounded-br-none'
                    : 'bg-gray-100 text-gray-800 rounded-bl-none'
                }`}
              >
                <p className="text-sm">{message.content}</p>
                <span className="text-xs opacity-70 mt-1 block">
                  {message.timestamp.toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Controls */}
        <div className="p-4 border-t border-orange-100 bg-white/90">
          {backendStatus === 'connected' ? (
            <div className="flex gap-2">
              <select
                value={selectedLevel}
                onChange={(e) => setSelectedLevel(e.target.value)}
                className="py-3 px-4 rounded-xl font-medium bg-white border border-orange-200 text-gray-700 focus:outline-none focus:ring-2 focus:ring-orange-500"
              >
                <option value="A1">A1</option>
                <option value="A2">A2</option>
                <option value="B1">B1</option>
                <option value="B2">B2</option>
                <option value="C1">C1</option>
                <option value="C2">C2</option>
              </select>
              <button
                onClick={isRecording ? stopRecording : startRecording}
                className={`flex-1 py-3 px-4 rounded-xl font-medium transition-all ${
                  isRecording
                    ? 'bg-red-500 hover:bg-red-600 text-white'
                    : 'bg-orange-500 hover:bg-orange-600 text-white'
                }`}
              >
                {isRecording ? 'Stop Recording' : 'Start Recording'}
              </button>
            </div>
          ) : (
            <button
              onClick={() => {
                wsRef.current = new WebSocket('ws://localhost:8000/ws');
              }}
              className="w-full py-3 px-4 rounded-xl font-medium bg-orange-500 hover:bg-orange-600 text-white transition-all"
            >
              Start Conversation
            </button>
          )}
        </div>
      </div>
    </main>
  );
} 