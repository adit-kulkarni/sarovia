'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '../../supabaseClient';
import ConversationHistory from '../components/ConversationHistory';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  isStreaming?: boolean;
}

const contextTitles: { [key: string]: string } = {
  restaurant: 'Ordering at a Restaurant',
  drinks: 'Asking Someone Out for Drinks',
  introduction: 'Introducing Yourself to New People',
  market: 'Haggling at the Local Market',
  karaoke: 'On a Karaoke Night Out',
  city: 'Finding Things to Do in the City'
};

const languageNames: { [key: string]: string } = {
  en: 'English',
  it: 'Italian',
  es: 'Spanish',
  pt: 'Portuguese',
  fr: 'French',
  de: 'German',
  kn: 'Kannada'
};

export default function Chat() {
  const [isRecording, setIsRecording] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [selectedLevel, setSelectedLevel] = useState('A1');
  const [selectedContext, setSelectedContext] = useState('restaurant');
  const [isLoading, setIsLoading] = useState(true);
  const [showSidebar, setShowSidebar] = useState(true);
  
  const wsRef = useRef<WebSocket | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentStreamingMessageRef = useRef<number | null>(null);
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const isPlayingRef = useRef(false);
  const audioBufferRef = useRef<Int16Array[]>([]);

  const router = useRouter();
  const searchParams = useSearchParams();

  const languages = {
    en: 'English',
    it: 'Italian',
    es: 'Spanish',
    pt: 'Portuguese',
    fr: 'French',
    de: 'German',
    kn: 'Kannada'
  };

  const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

  const contexts = {
    restaurant: 'Restaurant',
    drinks: 'Drinks',
    introduction: 'Introduction',
    market: 'Market',
    karaoke: 'Karaoke',
    city: 'City Guide'
  };

  useEffect(() => {
    const initializeChat = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          router.push('/login');
          return;
        }

        const context = searchParams.get('context') || 'restaurant';
        const language = searchParams.get('language') || 'en';
        const level = searchParams.get('level') || 'A1';

        setSelectedContext(context);
        setSelectedLanguage(language);
        setSelectedLevel(level);
        setIsLoading(false);
      } catch (err) {
        setError('Failed to initialize chat');
        setIsLoading(false);
      }
    };

    initializeChat();
  }, [router, searchParams]);

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
    let ws: WebSocket | null = null;
    let isMounted = true;

    async function connectWS() {
      if (ws?.readyState === WebSocket.OPEN) {
        console.log('WebSocket already connected');
        return;
      }

      try {
        const { data } = await supabase.auth.getSession();
        const token = data?.session?.access_token;
        
        if (!isMounted) return; // Don't create connection if unmounted

        ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);
        wsRef.current = ws;

        if (!ws) return;
        
        ws.onopen = () => {
          if (!isMounted) return;
          setIsConnected(true);
          ws!.send(JSON.stringify({
            type: 'session.init',
            level: selectedLevel,
            context: selectedContext,
            language: selectedLanguage
          }));
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: `Connected to backend WebSocket. Starting ${languageNames[selectedLanguage]} conversation practice.`,
            timestamp: new Date().toISOString()
          }]);
          initAudioContext();
        };

        ws.onclose = () => {
          if (!isMounted) return;
          setIsConnected(false);
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: 'Disconnected from backend WebSocket',
            timestamp: new Date().toISOString()
          }]);
        };

        ws.onerror = (error) => {
          if (!isMounted) return;
          setIsConnected(false);
          setMessages(prev => [...prev, {
            role: 'assistant',
            content: `WebSocket error: ${error}`,
            timestamp: new Date().toISOString()
          }]);
        };

        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          
          switch (data.type) {
            case 'session.created':
              setIsConnected(true);
              break;
            case 'conversation.item.input_audio_transcription.completed':
              setMessages(prev => [...prev, {
                role: 'user',
                content: data.transcript,
                timestamp: new Date().toISOString()
              }]);
              break;
            case 'response.audio_transcript.delta': {
              setMessages(prev => {
                // If no streaming message, create one
                if (
                  currentStreamingMessageRef.current === null ||
                  currentStreamingMessageRef.current < 0 ||
                  currentStreamingMessageRef.current >= prev.length ||
                  !prev[currentStreamingMessageRef.current].isStreaming
                ) {
                  // Start a new streaming message
                  const newIndex = prev.length;
                  currentStreamingMessageRef.current = newIndex;
                  return [
                    ...prev,
                    {
                      role: 'assistant' as const,
                      content: data.delta,
                      timestamp: new Date().toISOString(),
                      isStreaming: true
                    }
                  ];
                } else {
                  // Append to the current streaming message
                  const idx = currentStreamingMessageRef.current;
                  const newMessages = [...prev];
                  newMessages[idx] = {
                    ...newMessages[idx],
                    content: newMessages[idx].content + data.delta
                  };
                  return newMessages;
                }
              });
              break;
            }
            case 'response.audio_transcript.done':
              setMessages(prev => {
                if (
                  currentStreamingMessageRef.current !== null &&
                  currentStreamingMessageRef.current >= 0 &&
                  currentStreamingMessageRef.current < prev.length
                ) {
                  const idx = currentStreamingMessageRef.current;
                  const newMessages = [...prev];
                  newMessages[idx] = {
                    ...newMessages[idx],
                    isStreaming: false
                  };
                  currentStreamingMessageRef.current = null;
                  return newMessages;
                }
                return prev;
              });
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
              setError(data.error.message);
              break;
          }
        };
      } catch (error) {
        console.error('Error establishing WebSocket connection:', error);
      }
    }

    connectWS();

    // Cleanup function
    return () => {
      isMounted = false;
      if (ws) {
        console.log('Cleaning up WebSocket connection');
        ws.close();
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (audioContextRef.current) {
        audioContextRef.current.close();
      }
      stopAudioPlayback();
    };
  }, [selectedContext, selectedLanguage, selectedLevel]); // Dependencies that should trigger reconnection

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
        role: 'assistant',
        content: 'Started recording',
        timestamp: new Date().toISOString()
      }]);
    } catch (error) {
      console.error('Error starting recording:', error);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: `Error starting recording: ${error}`,
        timestamp: new Date().toISOString()
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
      role: 'assistant',
      content: 'Stopped recording',
      timestamp: new Date().toISOString()
    }]);
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.refresh();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500"></div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen">
      {/* Header */}
      <div className="bg-white/80 backdrop-blur-sm border-b border-orange-100 p-4">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <div className="flex items-center space-x-6">
            <div className="flex flex-col items-start">
              <span className="text-xs text-gray-500 uppercase tracking-wide">Language</span>
              <span className="font-semibold text-base text-gray-800">{languageNames[selectedLanguage]}</span>
            </div>
            <div className="flex flex-col items-start">
              <span className="text-xs text-gray-500 uppercase tracking-wide">Context</span>
              <span className="font-semibold text-base text-gray-800">{contextTitles[selectedContext]}</span>
            </div>
            <div className="flex flex-col items-start">
              <span className="text-xs text-gray-500 uppercase tracking-wide">Level</span>
              <span className="font-semibold text-base text-gray-800">{selectedLevel}</span>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className={`h-3 w-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span className="text-sm text-gray-600">
              {isConnected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className="max-w-6xl mx-auto space-y-4">
          {messages.map((message, index) => (
            <div
              key={index}
              className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[80%] rounded-2xl px-4 py-2 ${
                  message.role === 'user'
                    ? 'bg-orange-500 text-white rounded-br-none'
                    : 'bg-gray-100 text-gray-800 rounded-bl-none'
                }`}
              >
                <p className="text-sm">{message.content}</p>
                <span className="text-xs opacity-70 mt-1 block">
                  {new Date(message.timestamp).toLocaleTimeString()}
                </span>
              </div>
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white/80 backdrop-blur-sm border-t border-orange-100 p-4">
        <div className="max-w-6xl mx-auto flex justify-center">
          <button
            onClick={isRecording ? stopRecording : startRecording}
            className="px-8 py-3 rounded-full text-white font-medium bg-orange-500 hover:bg-orange-600 transition-colors"
          >
            {isRecording ? 'Stop Recording' : 'Start Recording'}
          </button>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg">
          {error}
        </div>
      )}
    </div>
  );
} 