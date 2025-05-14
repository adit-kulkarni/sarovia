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
    <main className="min-h-screen bg-gray-50">
      <div className="max-w-4xl mx-auto p-2 sm:p-4">
        <div className="bg-white rounded-lg shadow-lg overflow-hidden h-[100vh] flex flex-col">
          {/* Header */}
          <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4">
            <h1 className="text-xl sm:text-2xl font-bold">Voice Chat Demo</h1>
            <div className="flex items-center space-x-4 mt-2">
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 sm:w-3 sm:h-3 rounded-full ${
                  backendStatus === 'connected' ? 'bg-green-400' : 
                  backendStatus === 'connecting' ? 'bg-yellow-400' : 
                  'bg-red-400'
                }`} />
                <span className="text-xs sm:text-sm">Backend: {backendStatus}</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className={`w-2 h-2 sm:w-3 sm:h-3 rounded-full ${
                  openaiStatus === 'connected' ? 'bg-green-400' : 'bg-red-400'
                }`} />
                <span className="text-xs sm:text-sm">OpenAI: {openaiStatus}</span>
              </div>
            </div>
          </div>

          {/* Chat Messages */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-gray-50">
            {messages.map((message, index) => (
              <div
                key={index}
                className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[85%] sm:max-w-[75%] rounded-2xl p-3 ${
                    message.type === 'user'
                      ? 'bg-blue-500 text-white rounded-br-none'
                      : 'bg-yellow-100 text-gray-800 rounded-bl-none'
                  }`}
                >
                  <p className="text-sm sm:text-base leading-relaxed">
                    {message.content}
                    {message.isStreaming && (
                      <span className="inline-block w-2 h-4 ml-1 bg-gray-400 animate-pulse" />
                    )}
                  </p>
                  <span className="text-[10px] sm:text-xs opacity-70 mt-1 block">
                    {message.timestamp.toLocaleTimeString()}
                  </span>
                </div>
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>

          {/* Recording Controls */}
          <div className="border-t p-4 bg-white">
            <div className="flex justify-center">
              <button
                onClick={isRecording ? stopRecording : startRecording}
                className={`px-4 sm:px-6 py-2 sm:py-3 rounded-full font-semibold transition-all transform hover:scale-105 ${
                  isRecording 
                    ? 'bg-red-500 hover:bg-red-600 text-white' 
                    : 'bg-blue-500 hover:bg-blue-600 text-white'
                }`}
              >
                {isRecording ? (
                  <div className="flex items-center space-x-2">
                    <div className="w-2 h-2 sm:w-3 sm:h-3 bg-white rounded-full animate-pulse" />
                    <span className="text-sm sm:text-base">Stop Recording</span>
                  </div>
                ) : (
                  <div className="flex items-center space-x-2">
                    <svg className="w-4 h-4 sm:w-5 sm:h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
                    </svg>
                    <span className="text-sm sm:text-base">Start Recording</span>
                  </div>
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
} 