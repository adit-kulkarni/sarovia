'use client';

import React, { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '../../supabaseClient';
import ConversationHistory from '../components/ConversationHistory';
import { Feedback, LessonProgress, LessonProgressEvent } from '../types/feedback';
import FeedbackPanel from '../components/FeedbackPanel';
import ChatBubble from '../components/ChatBubble';

import LessonSummaryModal from '../components/LessonSummaryModal';
import { VADSettings } from '../components/VADSettingsModal';
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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

function ChatComponent() {
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
  
  // Add state for personalized context titles
  const [contextTitleCache, setContextTitleCache] = useState<{ [key: string]: string }>({});
  
  // Function to get display context title
  const getDisplayContextTitle = (contextId: string): string => {
    // Try classic contexts first
    if (contextTitles[contextId]) {
      return contextTitles[contextId];
    }
    
    // Try personalized context cache
    if (contextTitleCache[contextId]) {
      return contextTitleCache[contextId];
    }
    
    // Fallback to context ID
    return contextId;
  };

  // Function to load personalized context titles
  const loadPersonalizedContextTitles = async (token: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/personalized_contexts?token=${token}`);
      if (response.ok) {
        const data = await response.json();
        const titleCache: { [key: string]: string } = {};
        
        data.contexts.forEach((context: any) => {
          titleCache[context.id] = context.title;
        });
        
        setContextTitleCache(titleCache);
      }
    } catch (error) {
      console.error('Error loading personalized context titles:', error);
    }
  };

  // Debug state changes
  useEffect(() => {
    console.log('[Chat] State change - conversationStarted:', conversationStarted);
  }, [conversationStarted]);
  
  useEffect(() => {
    console.log('[Chat] State change - sessionReady:', sessionReady);
  }, [sessionReady]);

  const [customInstructions, setCustomInstructions] = useState<string | null>(null);
  const [lessonProgress, setLessonProgress] = useState<LessonProgress | null>(null);
  const [isCompletingLesson, setIsCompletingLesson] = useState(false);
  const [isLessonConversation, setIsLessonConversation] = useState(false);
  
  // Conversation completion states (for non-lesson conversations)
  const [isCompletingConversation, setIsCompletingConversation] = useState(false);
  const [conversationSummaryData, setConversationSummaryData] = useState<any>(null);
  const [showConversationSummary, setShowConversationSummary] = useState(false);
  
  // Lesson Summary Modal States
  const [showLessonSummary, setShowLessonSummary] = useState(false);
  const [lessonSummaryData, setLessonSummaryData] = useState<any>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  
  // Token state for API calls
  const [token, setToken] = useState<string | null>(null);
  
  // VAD Settings States
  const [vadSettings, setVadSettings] = useState<VADSettings>({ type: 'semantic', eagerness: 'low' });

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
        
        // Set token for API calls
        setToken(session.access_token);
        
        // Load personalized context titles
        await loadPersonalizedContextTitles(session.access_token);

        const context = searchParams.get('context') || 'restaurant';
        const language = searchParams.get('language') || 'en';
        const level = searchParams.get('level') || 'A1';
        const conversationId = searchParams.get('conversation');
        const lessonId = searchParams.get('lesson_id');
        const customLessonId = searchParams.get('custom_lesson_id');

        setSelectedContext(context);
        setSelectedLanguage(language);
        setSelectedLevel(level);
        
        // Check if this is a lesson conversation
        if (lessonId || customLessonId || context.startsWith('Lesson:') || context.startsWith('Custom Lesson:')) {
          setIsLessonConversation(true);
          console.log('[Lesson Detection] This is a lesson conversation:', {
            lessonId,
            customLessonId,
            context,
            isLessonConversation: true
          });
        } else {
          console.log('[Lesson Detection] This is NOT a lesson conversation:', {
            lessonId,
            customLessonId,
            context,
            isLessonConversation: false
          });
        }

        // If we have a conversation ID, load the existing conversation
        if (conversationId) {
          setConversationId(conversationId);
          setSessionReady(true);

          // Fetch conversation context from Supabase
          const { data: convoData, error: convoError } = await supabase
            .from('conversations')
            .select('context, language, level')
            .eq('id', conversationId)
            .single();
          if (convoError) throw convoError;
          
          console.log('[Conversation Loading] Loaded conversation data:', convoData);
          
          if (convoData && convoData.context) {
            setSelectedContext(convoData.context);
            console.log('[Conversation Loading] Set context from DB:', convoData.context);
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
          
          // If this is a lesson conversation, fetch current progress
          if (lessonId || customLessonId || convoData?.context?.startsWith('Lesson:') || convoData?.context?.startsWith('Custom Lesson:')) {
            // Update lesson conversation state if loading from database context
            if (convoData?.context?.startsWith('Lesson:') || convoData?.context?.startsWith('Custom Lesson:')) {
              setIsLessonConversation(true);
              console.log('[Lesson Detection] Updated to lesson conversation from DB context:', convoData.context);
            }
            
            console.log('[Progress Init] Fetching lesson progress for existing conversation');
            try {
              const { data: { session } } = await supabase.auth.getSession();
              if (session?.access_token) {
                const curriculumId = searchParams.get('curriculum_id');
                let progressUrl = '';
                
                if (lessonId) {
                  progressUrl = `${API_BASE}/api/lessons/${lessonId}/progress?curriculum_id=${curriculumId}&token=${session.access_token}`;
                } else if (customLessonId) {
                  progressUrl = `${API_BASE}/api/custom_lessons/${customLessonId}/progress?curriculum_id=${curriculumId}&token=${session.access_token}`;
                }
                
                if (progressUrl) {
                  const progressResponse = await fetch(progressUrl);
                  if (progressResponse.ok) {
                    const progressData = await progressResponse.json();
                    console.log('[Progress Init] Loaded existing progress:', progressData);
                    
                    if (progressData && progressData.status !== 'not_started') {
                      const lessonProgressData: LessonProgress = {
                        turns: progressData.turns_completed || 0,
                        required: progressData.required_turns || 7,
                        can_complete: (progressData.turns_completed || 0) >= (progressData.required_turns || 7),
                        lesson_id: lessonId || undefined,
                        custom_lesson_id: customLessonId || undefined,
                        progress_id: progressData.id
                      };
                      setLessonProgress(lessonProgressData);
                      console.log('[Progress Init] Set lesson progress:', lessonProgressData);
                    }
                  }
                }
              }
            } catch (progressError) {
              console.error('[Progress Init] Error loading lesson progress:', progressError);
            }
          }
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

  // Step 1: User clicks 'Start Conversation' - Use integrated VAD settings
  const handleStartConversation = async () => {
    console.log('[Start] Starting conversation...');
    
    // Use default VAD settings if none selected
    const finalVadSettings = vadSettings || { type: 'semantic', eagerness: 'low' };
    
    // Call the VAD settings confirm handler directly
    await handleVADSettingsConfirm(finalVadSettings);
  };

  // Step 1.5: Handle VAD settings confirmation
  const handleVADSettingsConfirm = async (settings: VADSettings) => {
    console.log('[Chat] VAD settings confirmed:', settings);
    setVadSettings(settings);
    
    // Unlock audio playbook on user gesture
    if (!audioContextRef.current) {
      audioContextRef.current = new AudioContext({ sampleRate: 24000 });
    }
    if (audioContextRef.current.state === 'suspended') {
      await audioContextRef.current.resume();
    }
    console.log('[Chat] AudioContext initialized and resumed');
    console.log('[Chat] Setting conversationStarted to true');
    setConversationStarted(true);
    // WebSocket/session setup will proceed in useEffect
  };

  // Step 2: WebSocket/session setup after conversationStarted
  useEffect(() => {
    console.log('[Chat] WebSocket useEffect triggered, conversationStarted:', conversationStarted);
    if (!conversationStarted) return;
    let ws: WebSocket | null = null;
    let isMounted = true;
    (async function connectWS() {
      try {
        console.log('[Chat] Starting WebSocket connection...');
        const { data } = await supabase.auth.getSession();
        const token = data?.session?.access_token;
        if (!isMounted) return;
        const wsUrl = API_BASE.replace('http://', 'ws://').replace('https://', 'wss://');
        ws = new WebSocket(`${wsUrl}/ws?token=${token}`);
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
              curriculum_id: curriculumId,
              vad_settings: vadSettings
            };
          } else {
            initMsg = {
              type: 'init',
              language: selectedLanguage,
              level: selectedLevel,
              context: selectedContext,
              curriculum_id: curriculumId,
              vad_settings: vadSettings
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
              // Always set conversation ID when we receive it
              setConversationId(data.conversation.conversation_id);
              console.log(`[Chat][${now}] Conversation ID set:`, data.conversation.conversation_id);
              
              if (!sessionReady) {
                setSessionReady(true);
                console.log(`[Chat][${now}] Conversation ready, conversation_id:`, data.conversation.conversation_id);
              } else {
                console.log(`[Chat][${now}] Updated conversation ID after session was ready. Data:`, JSON.stringify(data));
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
            case 'lesson.progress':
              // Handle lesson progress updates
              const progressData: LessonProgress = {
                turns: data.turns,
                required: data.required,
                can_complete: data.can_complete,
                lesson_id: data.lesson_id,
                custom_lesson_id: data.custom_lesson_id,
                progress_id: data.progress_id
              };
              setLessonProgress(progressData);
              console.log('Lesson progress updated:', progressData);
              
              // Additional debugging
              console.log(`[Progress Debug] Turns: ${data.turns}/${data.required}, Can complete: ${data.can_complete}`);
              console.log(`[Progress Debug] Lesson ID: ${data.lesson_id}, Custom Lesson ID: ${data.custom_lesson_id}`);
              console.log(`[Progress Debug] Progress ID: ${data.progress_id}`);
              
              // Show notification when lesson can be completed
              if (data.can_complete && !lessonProgress?.can_complete) {
                console.log('[Progress Debug] Lesson completion unlocked!');
                // You could add a toast notification here if desired
              }
              break;
            case 'suggestion.available':
              // Emit custom event for lesson suggestions
              const suggestionEvent = new CustomEvent('suggestion.available', {
                detail: {
                  curriculum_id: data.curriculum_id,
                  threshold_data: data.threshold_data
                }
              });
              window.dispatchEvent(suggestionEvent);
              console.log('Suggestion notification dispatched:', data);
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
          console.error('[Chat] WebSocket error:', error);
          setIsConnected(false);
          setError('WebSocket connection error');
        };
        wsRef.current = ws;
      } catch (error) {
        console.error('[Chat] Failed to connect to server:', error);
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

              const url = `${API_BASE}/api/hint?token=${session.access_token}`;
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

  const handleCompleteLesson = async () => {
    if (!lessonProgress?.progress_id || !lessonProgress.can_complete) {
      return;
    }

    setIsCompletingLesson(true);
    setLoadingSummary(true);
    
    try {
      // Stop recording if currently recording
      if (isRecording) {
        console.log('[Complete Lesson] Stopping recording...');
        stopRecording();
      }
      
      // Stop any audio playback
      stopAudioPlayback();
      
      // Close WebSocket connection to OpenAI
      if (wsRef.current) {
        console.log('[Complete Lesson] Closing WebSocket connection...');
        wsRef.current.close();
        wsRef.current = null;
      }
      
      // Wait a moment for cleanup
      await new Promise(resolve => setTimeout(resolve, 500));

      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error('No active session');
      }

      // First, complete the lesson
      const response = await fetch(`${API_BASE}/api/lesson_progress/complete?token=${session.access_token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          progress_id: lessonProgress.progress_id
        })
      });

      const responseData = await response.json();

      if (!response.ok) {
        throw new Error(responseData.detail || 'Failed to complete lesson');
      }

      console.log('[Complete Lesson] Lesson completed successfully:', responseData);
      
      // Add debugging for the summary call
      console.log('[Complete Lesson] Progress ID:', lessonProgress.progress_id);
      console.log('[Complete Lesson] Session token length:', session.access_token.length);
      
      // Now fetch the lesson summary with proper URL encoding
      const encodedProgressId = encodeURIComponent(lessonProgress.progress_id);
      const encodedToken = encodeURIComponent(session.access_token);
      const summaryUrl = `${API_BASE}/api/lesson_progress/${encodedProgressId}/summary?token=${encodedToken}`;
      console.log('[Complete Lesson] Summary URL:', summaryUrl);
      
      const summaryResponse = await fetch(summaryUrl);
      
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        console.log('[Complete Lesson] Fetched summary:', summaryData);
        setLessonSummaryData(summaryData);
        setShowLessonSummary(true);
      } else {
        console.error('[Complete Lesson] Failed to fetch summary');
        // Fallback: redirect immediately if summary fails
        const curriculumId = searchParams.get('curriculum_id');
        if (curriculumId) {
          router.push(`/?curriculum_id=${curriculumId}`);
        } else {
          router.push('/');
        }
      }
      
    } catch (error) {
      console.error('[Complete Lesson] Error completing lesson:', error);
      setError(error instanceof Error ? error.message : 'Failed to complete lesson');
    } finally {
      setIsCompletingLesson(false);
      setLoadingSummary(false);
    }
  };

  const handleReturnToDashboard = () => {
    const curriculumId = searchParams.get('curriculum_id');
    if (curriculumId) {
      router.push(`/?curriculum_id=${curriculumId}`);
    } else {
      router.push('/');
    }
  };

  const handleCompleteConversation = async () => {
    if (!conversation_id) {
      return;
    }

    setIsCompletingConversation(true);
    setLoadingSummary(true);
    
    try {
      // Stop recording if currently recording
      if (isRecording) {
        console.log('[Complete Conversation] Stopping recording...');
        stopRecording();
      }
      
      // Stop any audio playback
      stopAudioPlayback();
      
      // Close WebSocket connection to OpenAI
      if (wsRef.current) {
        console.log('[Complete Conversation] Closing WebSocket connection...');
        wsRef.current.close();
        wsRef.current = null;
      }
      
      // Wait a moment for cleanup
      await new Promise(resolve => setTimeout(resolve, 500));

      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        throw new Error('No active session');
      }

      // First, complete the conversation
      const response = await fetch(`${API_BASE}/api/conversations/complete?token=${session.access_token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          conversation_id: conversation_id
        })
      });

      const responseData = await response.json();

      if (!response.ok) {
        throw new Error(responseData.detail || 'Failed to complete conversation');
      }

      console.log('[Complete Conversation] Conversation completed successfully:', responseData);
      
      // Now fetch the conversation summary
      const encodedConversationId = encodeURIComponent(conversation_id);
      const encodedToken = encodeURIComponent(session.access_token);
      const summaryUrl = `${API_BASE}/api/conversations/${encodedConversationId}/summary?token=${encodedToken}`;
      console.log('[Complete Conversation] Summary URL:', summaryUrl);
      
      const summaryResponse = await fetch(summaryUrl);
      
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        console.log('[Complete Conversation] Fetched summary:', summaryData);
        setConversationSummaryData(summaryData);
        setShowConversationSummary(true);
      } else {
        console.error('[Complete Conversation] Failed to fetch summary');
        // Fallback: redirect immediately if summary fails
        router.push('/history');
      }
      
    } catch (error) {
      console.error('[Complete Conversation] Error completing conversation:', error);
      setError(error instanceof Error ? error.message : 'Failed to complete conversation');
    } finally {
      setIsCompletingConversation(false);
      setLoadingSummary(false);
    }
  };

  const handleReturnToHistory = () => {
    router.push('/history');
  };

  // UI rendering logic
  if (!conversationStarted) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen">
        <div className="bg-white/80 rounded-xl shadow-lg p-8 flex flex-col items-center max-w-lg w-full mx-4">
          <h2 className="text-2xl font-bold mb-6 text-gray-800">Ready to begin?</h2>
          <p className="mb-8 text-gray-700 text-center">Your session is set up for <b>{languageNames[selectedLanguage]}</b> at level <b>{selectedLevel}</b> in the context of <b>{selectedContext.startsWith('Lesson:') ? selectedContext.replace('Lesson:', '').trim() : getDisplayContextTitle(selectedContext)}</b>.</p>
          
          {/* Integrated VAD Settings */}
          <div className="w-full space-y-6 mb-8">
            <div>
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                Response Mode
              </label>
              <div className="space-y-3">
                <div>
                  <label className="flex items-center p-3 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50 transition-colors cursor-pointer">
                    <input
                      type="radio"
                      name="vadType"
                      value="semantic"
                      checked={vadSettings?.type === 'semantic'}
                      onChange={(e) => setVadSettings({ type: 'semantic', eagerness: vadSettings?.eagerness || 'low' })}
                      className="mr-3 text-orange-500 focus:ring-orange-500"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-gray-800">Smart Detection</div>
                    </div>
                    <div className="relative group">
                      <div className="w-5 h-5 bg-gray-300 rounded-full flex items-center justify-center text-xs text-white cursor-help">
                        i
                      </div>
                      <div className="absolute right-0 top-6 w-64 p-2 bg-gray-800 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                        AI understands when you're done speaking and responds naturally
                      </div>
                    </div>
                  </label>
                  
                  {/* Response Speed - directly under Smart Detection */}
                  {vadSettings?.type === 'semantic' && (
                    <div className="ml-8 mt-3 bg-orange-50/50 rounded-lg p-3 border-l-3 border-orange-300">
                      <label className="block text-xs font-semibold text-gray-600 mb-2">
                        Response speed
                      </label>
                      <select
                        value={vadSettings.eagerness}
                        onChange={(e) => setVadSettings({ ...vadSettings, eagerness: e.target.value as 'low' | 'medium' | 'high' })}
                        className="w-full p-2 text-sm border border-orange-200 rounded-md bg-white focus:ring-1 focus:ring-orange-500 focus:border-orange-500"
                      >
                        <option value="low">Patient</option>
                        <option value="medium">Balanced</option>
                        <option value="high">Quick</option>
                      </select>
                    </div>
                  )}
                </div>
                
                <label className="flex items-center p-3 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50 transition-colors cursor-pointer">
                  <input
                    type="radio"
                    name="vadType"
                    value="disabled"
                    checked={vadSettings?.type === 'disabled'}
                    onChange={(e) => setVadSettings({ type: 'disabled', eagerness: 'low' })}
                    className="mr-3 text-orange-500 focus:ring-orange-500"
                  />
                  <div className="flex-1">
                    <div className="font-medium text-gray-800">Manual Control</div>
                  </div>
                  <div className="relative group">
                    <div className="w-5 h-5 bg-gray-300 rounded-full flex items-center justify-center text-xs text-white cursor-help">
                      i
                    </div>
                    <div className="absolute right-0 top-6 w-64 p-2 bg-gray-800 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                      Press a button when you want to send your message
                    </div>
                  </div>
                </label>
              </div>
            </div>
          </div>
          
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
                  : getDisplayContextTitle(selectedContext)}
              </span>
            </div>
            <div className="flex flex-col items-start">
              <span className="text-xs text-gray-500 uppercase tracking-wide">Level</span>
              <span className="font-semibold text-base text-gray-800">{selectedLevel}</span>
            </div>
            {isLessonConversation && (
              <div className="flex flex-col items-start">
                <span className="text-xs text-orange-500 uppercase tracking-wide font-medium">Lesson Mode</span>
                <span className="text-sm text-orange-600 font-medium">Progress Tracked</span>
              </div>
            )}
          </div>
          <div className="flex items-center space-x-4">
            {/* Lesson Progress in Header - More Prominent */}
            {isLessonConversation && lessonProgress && (
              <div className="flex items-center space-x-3 bg-orange-50 rounded-lg px-4 py-2 border border-orange-200">
                <div className="flex flex-col items-start">
                  <span className="text-xs text-orange-600 uppercase tracking-wide font-medium">Progress</span>
                  <span className="text-sm font-semibold text-orange-800">
                    {lessonProgress.turns}/{lessonProgress.required} turns
                  </span>
                </div>
                <div className="w-24 bg-orange-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-300 ${
                      lessonProgress.can_complete 
                        ? 'bg-green-500' 
                        : 'bg-orange-500'
                    }`}
                    style={{ width: `${Math.min((lessonProgress.turns / lessonProgress.required) * 100, 100)}%` }}
                  />
                </div>
                {lessonProgress.can_complete && (
                  <div className="flex items-center">
                    <span className="text-green-600 text-lg">✅</span>
                  </div>
                )}
              </div>
            )}
            <div className="flex items-center space-x-2">
              <span className={`h-3 w-3 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
              <span className="text-sm text-gray-600">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
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
                  language={selectedLanguage}
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
        <div className="max-w-6xl mx-auto flex justify-center items-center space-x-4">
          {!isRecording ? (
            <button
              onClick={handleStartRecording}
              className="w-14 h-14 rounded-full bg-gray-100 hover:bg-gray-200 border-2 border-gray-300 transition-colors flex items-center justify-center group"
            >
              <div className="w-0 h-0 border-l-[12px] border-l-orange-500 border-t-[8px] border-t-transparent border-b-[8px] border-b-transparent ml-1 group-hover:border-l-orange-600"></div>
            </button>
          ) : (
            <button
              onClick={stopRecording}
              className="w-14 h-14 rounded-full bg-gray-100 hover:bg-gray-200 border-2 border-gray-300 transition-colors flex items-center justify-center"
            >
              <div className="w-3 h-3 bg-orange-500 rounded-sm"></div>
            </button>
          )}
          
          {/* Lesson Completion Button - Only show when lesson can be completed */}
          {isLessonConversation && lessonProgress?.can_complete && (
            <button
              onClick={handleCompleteLesson}
              disabled={isCompletingLesson}
              className="px-8 py-3 rounded-full bg-orange-500 hover:bg-orange-600 text-white font-medium transition-all duration-200 disabled:opacity-50 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95"
            >
              {isCompletingLesson ? (
                <div className="flex items-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white mr-2"></div>
                  Completing...
                </div>
              ) : (
                <div className="flex items-center">
                  <span className="mr-2">✅</span>
                  Complete Lesson
                </div>
              )}
            </button>
          )}

          {/* End Conversation Button - Only show for non-lesson conversations */}
          {!isLessonConversation && conversation_id && (
            <button
              onClick={handleCompleteConversation}
              disabled={isCompletingConversation}
              className="px-8 py-3 rounded-full bg-red-500 hover:bg-red-600 text-white font-medium transition-all duration-200 disabled:opacity-50 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95"
            >
              {isCompletingConversation ? (
                <div className="flex items-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white mr-2"></div>
                  Ending...
                </div>
              ) : (
                <div className="flex items-center">
                  <span className="mr-2">🏁</span>
                  End Conversation
                </div>
              )}
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
      

      
      {/* Lesson Summary Modal */}
      <LessonSummaryModal
        isOpen={showLessonSummary}
        onClose={() => setShowLessonSummary(false)}
        onReturnToDashboard={handleReturnToDashboard}
        summaryData={lessonSummaryData}
        loading={loadingSummary}
        token={token}
      />

      {/* Conversation Summary Modal */}
      <LessonSummaryModal
        isOpen={showConversationSummary}
        onClose={() => setShowConversationSummary(false)}
        onReturnToDashboard={handleReturnToDashboard}
        summaryData={conversationSummaryData}
        loading={loadingSummary}
        token={token}
      />
    </div>
  );
}

export default function Chat() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <ChatComponent />
    </Suspense>
  );
} 