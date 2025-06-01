'use client';

import React, { useEffect, useState, useRef } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '../../supabaseClient';
import ConversationHistory from '../components/ConversationHistory';
import { Feedback } from '../types/feedback';
import FeedbackPanel from '../components/FeedbackPanel';
import ChatBubble from '../components/ChatBubble';
import type { Message } from '../types/feedback';

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

const API_BASE = 'http://localhost:8000';

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
  const [currentHint, setCurrentHint] = useState<string | null>(null);
  const [isLoadingHint, setIsLoadingHint] = useState(false);
  const [conversation_id, setConversationId] = useState<string | null>(null);
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
  const [messageFeedbacks, setMessageFeedbacks] = useState<Record<string, string>>({});
  const [sessionReady, setSessionReady] = useState(false);
  const [conversationStarted, setConversationStarted] = useState(false);
  const [isMicPrompted, setIsMicPrompted] = useState(false);
  const [customInstructions, setCustomInstructions] = useState<string | null>(null);
  
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
        const conversationId = searchParams.get('conversation');

        setSelectedContext(context);
        setSelectedLanguage(language);
        setSelectedLevel(level);

        // If we have a conversation ID, load the existing conversation
        if (conversationId) {
          setConversationId(conversationId);
          setConversationStarted(true);
          setSessionReady(true);

          // Fetch conversation context from Supabase
          const { data: convoData, error: convoError } = await supabase
            .from('conversations')
            .select('context, language, level')
            .eq('id', conversationId)
            .single();
          if (convoError) throw convoError;
          if (convoData && convoData.context) {
            setSelectedContext(convoData.context);
          }
          if (convoData && convoData.language) {
            setSelectedLanguage(convoData.language);
          }
          if (convoData && convoData.level) {
            setSelectedLevel(convoData.level);
          }

          // Fetch messages for this conversation
          const { data: messagesData, error: messagesError } = await supabase
            .from('messages')
            .select('*')
            .eq('conversation_id', conversationId)
            .order('created_at', { ascending: true });

          if (messagesError) throw messagesError;

          // Fetch feedback for these messages
          const { data: feedbackData, error: feedbackError } = await supabase
            .from('message_feedback')
            .select('*')
            .in('message_id', messagesData.map(m => m.id));

          if (feedbackError) throw feedbackError;

          // Convert messages to the correct format
          const formattedMessages = messagesData.map(msg => {
            // Find feedback for this message
            const messageFeedback = feedbackData.find(f => f.message_id === msg.id);
            return {
              id: msg.id,
              role: msg.role,
              content: msg.content,
              timestamp: msg.created_at,
              feedback: messageFeedback ? {
                messageId: messageFeedback.message_id,
                originalMessage: messageFeedback.original_message,
                mistakes: messageFeedback.mistakes,
                hasMistakes: messageFeedback.mistakes.length > 0,
                timestamp: messageFeedback.created_at
              } : undefined
            };
          });

          setMessages(formattedMessages);

          // Process feedback
          const feedbacksList: Feedback[] = feedbackData.map(f => ({
            messageId: f.message_id,
            originalMessage: f.original_message,
            mistakes: f.mistakes,
            hasMistakes: f.mistakes.length > 0,
            timestamp: f.created_at
          }));

          setFeedbacks(feedbacksList);
          
          // Set message feedbacks
          const messageFeedbackMap: Record<string, string> = {};
          feedbacksList.forEach(f => {
            if (f.hasMistakes) {
              messageFeedbackMap[f.messageId] = f.messageId;
            }
          });
          setMessageFeedbacks(messageFeedbackMap);
        }

        setIsLoading(false);
      } catch (err) {
        setError('Failed to initialize chat');
        setIsLoading(false);
      }
    };

    initializeChat();
  }, [router, searchParams]);

  useEffect(() => {
    const fetchInstructions = async () => {
      const conversationId = searchParams.get('conversation');
      if (!conversationId) return;
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) return;
      const token = session.access_token;
      try {
        const res = await fetch(`${API_BASE}/api/conversation_instructions?conversation_id=${conversationId}&token=${token}`);
        if (res.ok) {
          const data = await res.json();
          setCustomInstructions(data.instructions);
        }
      } catch (e) {
        // Ignore, fallback to default
      }
    };
    fetchInstructions();
  }, [searchParams]);

  useEffect(() => {
    // Parse context, language, level from query params
    const context = searchParams.get('context') || 'restaurant';
    const language = searchParams.get('language') || 'en';
    const level = searchParams.get('level') || 'A1';
    setSelectedContext(context);
    setSelectedLanguage(language);
    setSelectedLevel(level);
    setConversationStarted(false);
    setSessionReady(false);
    // Simulate sending session config to backend/OpenAI
    // In real implementation, send session.update and wait for confirmation
    console.log('[Chat] Sending session config to backend/OpenAI:', { context, language, level });
    setTimeout(() => {
      setSessionReady(true);
      console.log('[Chat] Session config confirmed, sessionReady=true');
    }, 1200); // Simulate async session config
  }, [searchParams]);

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

    // Defensive: Resume AudioContext if suspended
    if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
      await audioContextRef.current.resume();
    }

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

  // Step 1: User clicks 'Start Conversation'
  const handleStartConversation = async () => {
    // Unlock audio playback on user gesture
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
    }
    if (audioContextRef.current.state === 'suspended') {
      await audioContextRef.current.resume();
    }
    console.log('[Chat] AudioContext initialized and resumed');
    setConversationStarted(true);
    // WebSocket/session setup will proceed in useEffect
  };

  // Step 2: WebSocket/session setup after conversationStarted
  useEffect(() => {
    if (!conversationStarted) return;
    let ws: WebSocket | null = null;
    let isMounted = true;
    (async function connectWS() {
      try {
        const { data } = await supabase.auth.getSession();
        const token = data?.session?.access_token;
        if (!isMounted) return;
        ws = new WebSocket(`ws://localhost:8000/ws?token=${token}`);
        ws.onopen = () => {
          console.log('[Chat] WebSocket connected');
          setIsConnected(true);
          setError(null);
          // Send initial config (init message)
          const curriculumId = searchParams.get('curriculum_id');
          const conversationId = searchParams.get('conversation');
          let initMsg: any;
          if (conversationId) {
            initMsg = {
              type: 'init',
              conversation_id: conversationId,
              curriculum_id: curriculumId
            };
          } else {
            initMsg = {
              type: 'init',
              language: selectedLanguage,
              level: selectedLevel,
              context: selectedContext,
              curriculum_id: curriculumId
            };
          }
          ws?.send(JSON.stringify(initMsg));
          console.log('[Chat] Sent init message:', initMsg);
        };
        ws.onmessage = (event) => {
          const data = JSON.parse(event.data);
          const now = new Date().toISOString();
          console.warn(`[Chat][${now}] Received event:`, data);
          if (data.type === 'conversation.created') {
            if (data.conversation && data.conversation.conversation_id) {
              if (!sessionReady) {
                setConversationId(data.conversation.conversation_id);
                setSessionReady(true);
                console.log(`[Chat][${now}] Conversation ready, conversation_id:`, data.conversation.conversation_id);
              } else {
                console.warn(`[Chat][${now}] Duplicate conversation.created event received after sessionReady was already set. Data:`, JSON.stringify(data));
              }
            } else {
              console.error(`[Chat][${now}] Malformed conversation.created event (missing conversation_id):`, JSON.stringify(data));
              if (!sessionReady) {
                setError('Conversation creation failed');
              }
            }
          } else if (data.type === 'session.created') {
            // This is OpenAI's event, just log it
            console.info(`[Chat][${now}] OpenAI session.created event received (ignored by app):`, JSON.stringify(data));
          }
          if (data.type === 'feedback.generated') {
            const feedback: Feedback = {
              messageId: data.messageId,
              originalMessage: data.feedback.originalMessage,
              mistakes: data.feedback.mistakes,
              hasMistakes: data.hasMistakes,
              timestamp: new Date().toISOString()
            };
            console.log('Received feedback for messageId:', data.messageId, feedback);
            setFeedbacks(prev => [...prev, feedback]);
            if (data.hasMistakes) {
              setMessageFeedbacks(prev => ({
                ...prev,
                [data.messageId]: data.messageId
              }));
            }
            setMessages(prevMessages => {
              const allIds = prevMessages.map(m => m.id);
              console.log('Current message ids:', allIds);
              const updated = prevMessages.map(msg => {
                if (msg.id === data.messageId && msg.role === 'user') {
                  const updatedMsg = { ...msg, feedback };
                  console.log('Attaching feedback to message:', updatedMsg);
                  return updatedMsg;
                }
                return msg;
              });
              console.log('Updated messages after feedback:', updated);
              return updated;
            });
          }
          switch (data.type) {
            case 'conversation.item.input_audio_transcription.completed': {
              if (!data.message_id) {
                // Ignore events without a valid message_id
                return;
              }
              console.log('Handler fired for message_id:', data.message_id, 'transcript:', data.transcript);
              setMessages(prev => {
                if (prev.some(msg => msg.id === data.message_id && msg.role === 'user')) {
                  return prev;
                }
                const newMsg: Message = {
                  id: data.message_id,
                  role: 'user',
                  content: data.transcript,
                  timestamp: new Date().toISOString()
                };
                console.log('Adding user message with id:', newMsg.id);
                return [...prev, newMsg];
              });
              break;
            }
            case 'response.audio_transcript.done': {
              setMessages(prev => [...prev, {
                role: 'assistant',
                content: data.transcript,
                timestamp: new Date().toISOString()
              }]);
              break;
            }
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
            default:
              // No error log for other message types
              break;
          }
        };
        ws.onclose = () => {
          setIsConnected(false);
          setError('Disconnected from server');
        };
        ws.onerror = (error) => {
          setIsConnected(false);
          setError('WebSocket connection error');
        };
        wsRef.current = ws;
      } catch (error) {
        setError('Failed to connect to server');
        setIsConnected(false);
      }
    })();
    return () => {
      isMounted = false;
      if (ws) ws.close();
    };
  }, [conversationStarted, selectedLanguage, selectedLevel, selectedContext]);

  // Step 3: User clicks 'Start Recording' for mic access
  const handleStartRecording = async () => {
    setIsMicPrompted(true);
    await startRecording();
  };

  const startRecording = async () => {
    try {
      // Ensure AudioContext is initialized and resumed on user gesture
      initAudioContext();
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      
      // Create audio source from the stream
      const source = audioContextRef.current?.createMediaStreamSource(stream);
      
      // Create a script processor to handle the audio data
      const processor = audioContextRef.current?.createScriptProcessor(1024, 1, 1);
      
      if (processor) {
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
      }

      // Connect the nodes
      if (source && processor && audioContextRef.current) {
        source.connect(processor);
        processor.connect(audioContextRef.current.destination);
      }

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

  const getHint = async () => {
    console.warn('getHint called, conversation_id:', conversation_id);
    if (!conversation_id) {
      setError('No active conversation found');
      return;
    }
    
    setIsLoadingHint(true);
    setError(null);
    
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        router.push('/login');
        return;
      }

      const url = `http://localhost:8000/api/hint?token=${session.access_token}`;
      const body = { conversation_id };
      console.log('Sending hint request:', { url, body });
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      });

      const responseData = await response.json();

      if (!response.ok) {
        throw new Error(responseData.detail || 'Failed to get hint');
      }

      console.log('Received hint response:', responseData);
      
      if (responseData.hint) {
        setCurrentHint(responseData.hint);
      } else {
        throw new Error('No hint received from server');
      }
    } catch (error) {
      console.error('Error getting hint:', error);
      setError(error instanceof Error ? error.message : 'Failed to get hint');
      setCurrentHint(null);
    } finally {
      setIsLoadingHint(false);
    }
  };

  const handleFeedbackClick = (messageId: string) => {
    // Scroll to the message with feedback
    const messageElement = document.getElementById(`message-${messageId}`);
    if (messageElement) {
      messageElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  // UI rendering logic
  if (!conversationStarted) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen">
        <div className="bg-white/80 rounded-xl shadow-lg p-8 flex flex-col items-center">
          <h2 className="text-2xl font-bold mb-2">Ready to begin?</h2>
          <p className="mb-4 text-gray-700">Your session is set up for <b>{languageNames[selectedLanguage]}</b> at level <b>{selectedLevel}</b> in the context of <b>{contextTitles[selectedContext]}</b>.</p>
          <button
            onClick={handleStartConversation}
            className="px-8 py-3 rounded-full text-white font-medium bg-orange-500 hover:bg-orange-600 transition-colors"
          >
            Start Conversation
          </button>
        </div>
      </div>
    );
  }
  if (!sessionReady) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500"></div>
        <span className="ml-4 text-orange-600 font-semibold">Setting up your session...</span>
      </div>
    );
  }
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
              <span className="font-semibold text-base text-gray-800">
                {selectedContext.startsWith('Lesson:')
                  ? selectedContext.replace('Lesson:', '').trim()
                  : contextTitles[selectedContext] || selectedContext}
              </span>
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

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4">
          <div className="max-w-6xl mx-auto space-y-4">
            {messages.map((message, index) => (
              <div
                key={index}
                id={message.id ? `message-${message.id}` : undefined}
              >
                <ChatBubble
                  message={message}
                  hasFeedback={message.id ? !!messageFeedbacks[message.id] : false}
                  onFeedbackClick={() => message.id && handleFeedbackClick(message.id)}
                />
              </div>
            ))}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* Right Panel */}
        <div className="w-80 bg-white/80 backdrop-blur-sm border-l border-orange-100 flex flex-col">
          {/* Hints Section */}
          <div className="flex-none p-4 border-b border-orange-100">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold text-gray-800">Conversation Hints</h3>
              <button
                onClick={getHint}
                disabled={isLoadingHint}
                className="px-4 py-2 rounded-lg bg-orange-500 text-white hover:bg-orange-600 transition-colors disabled:opacity-50"
              >
                {isLoadingHint ? (
                  <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white"></div>
                ) : (
                  'Get Hint'
                )}
              </button>
            </div>
            
            <div className="overflow-y-auto max-h-[200px]">
              {currentHint && (
                <div className="bg-orange-50 rounded-lg p-4 inline-block w-auto max-w-full mb-4">
                  <p className="text-gray-800">{currentHint}</p>
                </div>
              )}
              
              {!currentHint && !isLoadingHint && (
                <div className="flex items-center justify-center text-gray-500">
                  <p className="text-center">Click "Get Hint" to receive a suggestion for your next response</p>
                </div>
              )}
            </div>
          </div>

          {/* Feedback Section */}
          <div className="flex-1 overflow-y-auto">
            <div className="p-4">
              <h3 className="text-lg font-semibold text-gray-800 mb-4">Feedback</h3>
              <FeedbackPanel
                feedbacks={feedbacks}
                onFeedbackClick={handleFeedbackClick}
              />
            </div>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white/80 backdrop-blur-sm border-t border-orange-100 p-4">
        <div className="max-w-6xl mx-auto flex justify-center">
          {!isRecording ? (
            <button
              onClick={handleStartRecording}
              className="px-8 py-3 rounded-full text-white font-medium bg-orange-500 hover:bg-orange-600 transition-colors"
            >
              Start Recording
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="px-8 py-3 rounded-full text-white font-medium bg-orange-400 hover:bg-orange-500 transition-colors"
            >
              Stop Recording
            </button>
          )}
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