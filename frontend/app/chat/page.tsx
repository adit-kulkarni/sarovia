'use client';

import React, { useEffect, useState, useRef, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '../../supabaseClient';
import { Feedback, LessonProgress } from '../types/feedback';
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
  const [isMuted, setIsMuted] = useState(false);
  const [isConversationActive, setIsConversationActive] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedLanguage, setSelectedLanguage] = useState('en');
  const [selectedLevel, setSelectedLevel] = useState('A1');
  const [selectedContext, setSelectedContext] = useState('restaurant');
  const [isLoading, setIsLoading] = useState(true);

  const [currentHint, setCurrentHint] = useState<string | null>(null);
  const [isLoadingHint, setIsLoadingHint] = useState(false);
  const [customHintInput, setCustomHintInput] = useState('');
  const [showTranslateInput, setShowTranslateInput] = useState(false);
  const [activeTab, setActiveTab] = useState<'feedback' | 'hints'>('feedback');
  const [conversation_id, setConversationId] = useState<string | null>(null);
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);
  const [messageFeedbacks, setMessageFeedbacks] = useState<Record<string, string>>({});
  const [sessionReady, setSessionReady] = useState(false);
  const [conversationStarted, setConversationStarted] = useState(false);

  
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
        
        data.contexts.forEach((context: { id: string; title: string }) => {
          titleCache[context.id] = context.title;
        });
        
        setContextTitleCache(titleCache);
      }
    } catch (error) {
      console.error('Error loading personalized context titles:', error);
    }
  };

  // Function to check if user has curriculums/language paths
  const checkUserCurriculums = async (token: string) => {
    try {
      setCurriculumsLoading(true);
      const response = await fetch(`${API_BASE}/api/curriculums?token=${token}`);
      if (response.ok) {
        const curriculums = await response.json();
        setHasCurriculums(curriculums.length > 0);
        console.log('[Curriculum Check] User has curriculums:', curriculums.length > 0);
      } else {
        setHasCurriculums(false);
        console.log('[Curriculum Check] Failed to fetch curriculums');
      }
    } catch (error) {
      console.error('[Curriculum Check] Error checking curriculums:', error);
      setHasCurriculums(false);
    } finally {
      setCurriculumsLoading(false);
    }
  };

  // Debug state changes
  useEffect(() => {
    console.log('[Chat] State change - conversationStarted:', conversationStarted);
  }, [conversationStarted]);
  
  useEffect(() => {
    console.log('[Chat] State change - sessionReady:', sessionReady);
  }, [sessionReady]);


  const [lessonProgress, setLessonProgress] = useState<LessonProgress | null>(null);
  const [isCompletingLesson, setIsCompletingLesson] = useState(false);
  const [isLessonConversation, setIsLessonConversation] = useState(false);
  
  // Conversation completion states (for non-lesson conversations)
  const [isCompletingConversation, setIsCompletingConversation] = useState(false);
  const [conversationSummaryData, setConversationSummaryData] = useState<Record<string, unknown> | null>(null);
  const [showConversationSummary, setShowConversationSummary] = useState(false);
  
  // Lesson Summary Modal States
  const [showLessonSummary, setShowLessonSummary] = useState(false);
  const [lessonSummaryData, setLessonSummaryData] = useState<Record<string, unknown> | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  
  // Token state for API calls
  const [token, setToken] = useState<string | null>(null);
  
  // Add state to track if user has language paths
  const [hasCurriculums, setHasCurriculums] = useState<boolean | null>(null);
  const [curriculumsLoading, setCurriculumsLoading] = useState(false);
  
  // VAD Settings States
  const [vadSettings, setVadSettings] = useState<VADSettings>({ type: 'semantic', eagerness: 'low' });

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const currentSourceRef = useRef<AudioBufferSourceNode | null>(null);
  const isPlayingRef = useRef(false);
  const audioBufferRef = useRef<Int16Array[]>([]);

  const router = useRouter();
  const searchParams = useSearchParams();



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
        
        // Check if user has curriculums/language paths
        await checkUserCurriculums(session.access_token);
        
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
      } catch {
        setError('Failed to initialize chat');
        setIsLoading(false);
      }
    };

    initializeChat();
  }, [router, searchParams]);



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
            // Only switch to feedback tab if the new feedback would be visible in filtered view
            // For now, always switch - we'll implement smart filtering next
            setActiveTab('feedback');
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
    setIsConversationActive(true);
    await startRecording();
  };

  const handleToggleMute = async () => {
    if (isMuted) {
      // Unmute - resume recording
      setIsMuted(false);
      setIsRecording(true);
      // Resume the audio context
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }
    } else {
      // Mute - pause recording
      setIsMuted(true);
      setIsRecording(false);
      // Suspend the current audio processing but keep connection alive
      if (audioContextRef.current && audioContextRef.current.state === 'running') {
        await audioContextRef.current.suspend();
      }
    }
  };

  const handleSaveConversation = async () => {
    // Set saving state
    setIsSaving(true);
    
    // Stop recording
    setIsRecording(false);
    setIsMuted(false);
    
    // Stop audio playback
    stopAudioPlayback();
    
    // Close audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    // Close WebSocket connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    // Trigger the completion/report generation
    try {
      if (isLessonConversation) {
        await handleCompleteLesson();
      } else {
        await handleCompleteConversation();
      }
    } finally {
      setIsSaving(false);
      setIsConversationActive(false);
    }
  };

  const startRecording = async () => {
    try {
      // Ensure AudioContext is initialized and resumed on user gesture
      initAudioContext();
      if (audioContextRef.current && audioContextRef.current.state === 'suspended') {
        await audioContextRef.current.resume();
      }
      
      // If stream doesn't exist, get it
      if (!streamRef.current) {
        streamRef.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
      
      // Create audio source from the stream
      const source = audioContextRef.current?.createMediaStreamSource(streamRef.current);
      
      // Create a script processor to handle the audio data
      const processor = audioContextRef.current?.createScriptProcessor(1024, 1, 1);
      
      if (processor) {
        processor.onaudioprocess = (e) => {
                      if (wsRef.current?.readyState === WebSocket.OPEN && !isMuted) {
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
      setIsMuted(false);
    } catch (error) {
      console.error('Error starting recording:', error);
      setError(`Error starting recording: ${error}`);
    }
  };

  const stopRecording = () => {
    setIsRecording(false);
    setIsMuted(false);
    setIsConversationActive(false);
    
    // Clean up audio context
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    
    // Clean up stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }
  };



  const getHint = async () => {
    console.warn('getHint called, conversation_id:', conversation_id, 'customInput:', customHintInput);
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
      const body = { 
        conversation_id,
        ...(customHintInput.trim() && { custom_request: customHintInput.trim() })
      };
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
        // Clear custom input after successful request
        setCustomHintInput('');
        setShowTranslateInput(false);
        // Always switch to hints tab when hint arrives
        setActiveTab('hints');
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



  // UI rendering logic
  if (!conversationStarted) {
    // Show loading state while checking curriculums
    if (hasCurriculums === null || curriculumsLoading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500"></div>
          <span className="ml-4 text-orange-600 font-semibold">Checking your language paths...</span>
        </div>
      );
    }

    // Show no curriculums message
    if (!hasCurriculums) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen">
          <div className="bg-white/80 rounded-xl shadow-lg p-8 flex flex-col items-center max-w-lg w-full mx-4 text-center">
            <div className="w-16 h-16 bg-orange-100 rounded-full flex items-center justify-center mb-6">
              <svg className="w-8 h-8 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.746 0 3.332.477 4.5 1.253v13C19.832 18.477 18.246 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
              </svg>
            </div>
            <h2 className="text-2xl font-bold mb-4 text-gray-800">Set up your language path first</h2>
            <p className="mb-6 text-gray-600">Before you can start conversations, you need to create a language learning path. This helps us personalize your experience and track your progress.</p>
            <button
              onClick={() => router.push('/')}
              className="px-6 py-3 rounded-full text-white font-medium bg-orange-500 hover:bg-orange-600 transition-colors"
            >
              Create Language Path
            </button>
          </div>
        </div>
      );
    }

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
                      onChange={() => setVadSettings({ type: 'semantic', eagerness: vadSettings?.eagerness || 'low' })}
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
                        AI understands when you&apos;re done speaking and responds naturally
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
                    onChange={() => setVadSettings({ type: 'disabled', eagerness: 'low' })}
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
            disabled={!hasCurriculums}
            className={`px-8 py-3 rounded-full text-white font-medium transition-colors ${
              !hasCurriculums 
                ? 'bg-gray-400 cursor-not-allowed' 
                : 'bg-orange-500 hover:bg-orange-600'
            }`}
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
            <div className="flex items-center space-x-3">
              <div className="flex items-center space-x-2">
                <div className="relative">
                  <div className="w-8 h-8 rounded-full bg-orange-100 flex items-center justify-center">
                    <svg className="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 9a3 3 0 100-6 3 3 0 000 6zm-7 9a7 7 0 1114 0H3z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <span className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white ${isConnected ? 'bg-green-500' : 'bg-red-500'}`}></span>
                </div>
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-gray-800">AI Teacher</span>
                  <span className="text-xs text-gray-500">
                    {isConnected ? 'Online' : 'Offline'}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Messages */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-6xl mx-auto space-y-4 p-4">
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

        {/* Right Panel - Tabbed Feedback/Hints */}
        <div className="w-80 bg-white/80 backdrop-blur-sm border-l border-orange-100 flex flex-col">
          {/* Tab Headers */}
          <div className="flex border-b border-orange-100">
            <button
              onClick={() => setActiveTab('feedback')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'feedback'
                  ? 'text-orange-600 border-b-2 border-orange-600 bg-orange-50'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              Feedback
            </button>
            <button
              onClick={() => setActiveTab('hints')}
              className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                activeTab === 'hints'
                  ? 'text-orange-600 border-b-2 border-orange-600 bg-orange-50'
                  : 'text-gray-600 hover:text-gray-800'
              }`}
            >
              Hints
            </button>
          </div>
          
          {/* Tab Content */}
          <div className="flex-1 overflow-y-auto p-4">
            {activeTab === 'feedback' ? (
              <FeedbackPanel
                feedbacks={feedbacks}
                onFeedbackClick={handleFeedbackClick}
              />
            ) : (
              <div className="space-y-4">
                {currentHint ? (
                  <div className="bg-orange-50 rounded-lg p-4 border border-orange-100">
                    <h4 className="text-sm font-medium text-gray-800 mb-2">Latest Hint</h4>
                    <p className="text-gray-700">{currentHint}</p>
                  </div>
                ) : (
                  <div className="text-center text-gray-500 py-8">
                    <p className="text-sm">No hints yet. Use the hint buttons to get suggestions!</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="bg-white/80 backdrop-blur-sm border-t border-orange-100 p-4">
        <div className="max-w-6xl mx-auto flex justify-center items-center space-x-4">
          {isSaving ? (
            /* Saving state - Loading indicator */
            <div className="flex flex-col items-center space-y-2">
              <div className="w-16 h-16 rounded-full bg-orange-500 flex items-center justify-center shadow-lg">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-white"></div>
              </div>
              <span className="text-orange-600 font-medium text-sm">Generating Report...</span>
            </div>
          ) : !isConversationActive ? (
            /* Initial state - Hint buttons and Mic button with label */
            <div className="flex items-center space-x-6">
              {/* Hint Buttons */}
              <div className="flex items-center space-x-3">
                {/* Generic Hint Button */}
                <div className="flex flex-col items-center space-y-1">
                  <button
                    onClick={() => getHint()}
                    disabled={isLoadingHint}
                    className="w-10 h-10 rounded-full bg-orange-100 hover:bg-orange-200 transition-all duration-200 flex items-center justify-center border border-orange-300 shadow-sm hover:shadow-md"
                    title="Get conversation hint"
                  >
                    {isLoadingHint ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-orange-500"></div>
                    ) : (
                      <svg className="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                  <span className="text-orange-600 font-medium text-xs">Hint</span>
                </div>
                
                {/* Translate Button and Input */}
                <div className="flex flex-col items-center space-y-1">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setShowTranslateInput(!showTranslateInput)}
                      className="w-10 h-10 rounded-full bg-orange-100 hover:bg-orange-200 transition-all duration-200 flex items-center justify-center border border-orange-300 shadow-sm hover:shadow-md"
                      title="Translate phrase"
                    >
                      <svg className="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M7 2a1 1 0 011 1v1h3a1 1 0 110 2H9.578a18.87 18.87 0 01-1.724 4.78c.29.354.596.696.914 1.026a1 1 0 11-1.44 1.389c-.188-.196-.373-.396-.554-.6a19.098 19.098 0 01-3.107 3.567 1 1 0 01-1.334-1.49 17.087 17.087 0 003.13-3.733 18.992 18.992 0 01-1.487-2.494 1 1 0 111.79-.89c.234.47.489.928.764 1.372.417-.934.752-1.913.997-2.927H3a1 1 0 110-2h3V3a1 1 0 011-1zm6 6a1 1 0 01.894.553l2.991 5.982a.869.869 0 01.02.037l.99 1.98a1 1 0 11-1.79.895L15.383 16h-4.764l-.724 1.447a1 1 0 11-1.788-.894l.99-1.98.019-.038 2.99-5.982A1 1 0 0113 8zm-1.382 6h2.764L13 11.236 11.618 14z" clipRule="evenodd" />
                      </svg>
                    </button>
                    
                    {showTranslateInput && (
                      <div className="flex items-center space-x-2 bg-white border border-orange-300 rounded-lg px-3 py-2 shadow-sm">
                        <p className="text-xs text-black mb-0">How do I say...?</p>
                        <input
                          type="text"
                          value={customHintInput}
                          onChange={(e) => setCustomHintInput(e.target.value)}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter' && !isLoadingHint && customHintInput.trim()) {
                              getHint();
                            }
                          }}
                          placeholder="Translate a phrase here"
                          className="text-sm border-none bg-transparent focus:outline-none italic text-gray-600 placeholder-gray-400 w-48"
                          disabled={isLoadingHint}
                          autoFocus
                        />
                        <button
                          onClick={() => customHintInput.trim() && getHint()}
                          disabled={isLoadingHint || !customHintInput.trim()}
                          className="w-6 h-6 rounded bg-orange-500 text-white hover:bg-orange-600 transition-colors disabled:opacity-50 flex items-center justify-center"
                        >
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                  <span className="text-orange-600 font-medium text-xs">Translate</span>
                </div>
              </div>
              
              {/* Start Button */}
              <div className="flex flex-col items-center space-y-2">
                <button
                  onClick={handleStartRecording}
                  className="w-16 h-16 rounded-full bg-orange-500 hover:bg-orange-600 transition-all duration-200 flex items-center justify-center group shadow-lg hover:shadow-xl hover:scale-105 active:scale-95"
                >
                  <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
                  </svg>
                </button>
                <span className="text-orange-600 font-medium text-sm">Start Chatting</span>
              </div>
            </div>
          ) : (
            /* Active conversation state - Mic mute button, Hint buttons, and Save button */
            <div className="flex items-center space-x-6">
              {/* Hint Buttons */}
              <div className="flex items-center space-x-3">
                {/* Generic Hint Button */}
                <div className="flex flex-col items-center space-y-1">
                  <button
                    onClick={() => getHint()}
                    disabled={isLoadingHint}
                    className="w-10 h-10 rounded-full bg-orange-100 hover:bg-orange-200 transition-all duration-200 flex items-center justify-center border border-orange-300 shadow-sm hover:shadow-md"
                    title="Get conversation hint"
                  >
                    {isLoadingHint ? (
                      <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-orange-500"></div>
                    ) : (
                      <svg className="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                  <span className="text-orange-600 font-medium text-xs">Hint</span>
                </div>
                
                {/* Translate Button and Input */}
                <div className="flex flex-col items-center space-y-1">
                  <div className="flex items-center space-x-2">
                    <button
                      onClick={() => setShowTranslateInput(!showTranslateInput)}
                      className="w-10 h-10 rounded-full bg-orange-100 hover:bg-orange-200 transition-all duration-200 flex items-center justify-center border border-orange-300 shadow-sm hover:shadow-md"
                      title="Translate phrase"
                    >
                      <svg className="w-5 h-5 text-orange-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M7 2a1 1 0 011 1v1h3a1 1 0 110 2H9.578a18.87 18.87 0 01-1.724 4.78c.29.354.596.696.914 1.026a1 1 0 11-1.44 1.389c-.188-.196-.373-.396-.554-.6a19.098 19.098 0 01-3.107 3.567 1 1 0 01-1.334-1.49 17.087 17.087 0 003.13-3.733 18.992 18.992 0 01-1.487-2.494 1 1 0 111.79-.89c.234.47.489.928.764 1.372.417-.934.752-1.913.997-2.927H3a1 1 0 110-2h3V3a1 1 0 011-1zm6 6a1 1 0 01.894.553l2.991 5.982a.869.869 0 01.02.037l.99 1.98a1 1 0 11-1.79.895L15.383 16h-4.764l-.724 1.447a1 1 0 11-1.788-.894l.99-1.98.019-.038 2.99-5.982A1 1 0 0113 8zm-1.382 6h2.764L13 11.236 11.618 14z" clipRule="evenodd" />
                      </svg>
                    </button>
                    
                    {showTranslateInput && (
                      <div className="flex items-center space-x-2 bg-white border border-orange-300 rounded-lg px-3 py-2 shadow-sm">
                        <p className="text-xs text-black mb-0">How do I say...?</p>
                        <input
                          type="text"
                          value={customHintInput}
                          onChange={(e) => setCustomHintInput(e.target.value)}
                          onKeyPress={(e) => {
                            if (e.key === 'Enter' && !isLoadingHint && customHintInput.trim()) {
                              getHint();
                            }
                          }}
                          placeholder="Translate a phrase here"
                          className="text-sm border-none bg-transparent focus:outline-none italic text-gray-600 placeholder-gray-400 w-48"
                          disabled={isLoadingHint}
                          autoFocus
                        />
                        <button
                          onClick={() => customHintInput.trim() && getHint()}
                          disabled={isLoadingHint || !customHintInput.trim()}
                          className="w-6 h-6 rounded bg-orange-500 text-white hover:bg-orange-600 transition-colors disabled:opacity-50 flex items-center justify-center"
                        >
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
                          </svg>
                        </button>
                      </div>
                    )}
                  </div>
                  <span className="text-orange-600 font-medium text-xs">Translate</span>
                </div>
              </div>
              
              {/* Mic Button */}
              <div className="flex flex-col items-center space-y-1">
                <button
                  onClick={handleToggleMute}
                  className="w-14 h-14 rounded-full bg-orange-500 hover:bg-orange-600 transition-all duration-200 flex items-center justify-center shadow-lg hover:shadow-xl hover:scale-105 active:scale-95"
                >
                  {isMuted ? (
                    /* Mic off icon */
                    <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M9.383 3.076A1 1 0 0110 4v12a1 1 0 01-1.707.707L4.586 13H2a1 1 0 01-1-1V8a1 1 0 011-1h2.586l3.707-3.707a1 1 0 011.09-.217zM12.293 7.293a1 1 0 011.414 0L15 8.586l1.293-1.293a1 1 0 111.414 1.414L16.414 10l1.293 1.293a1 1 0 01-1.414 1.414L15 11.414l-1.293 1.293a1 1 0 01-1.414-1.414L13.586 10l-1.293-1.293a1 1 0 010-1.414z" clipRule="evenodd" />
                    </svg>
                  ) : (
                    /* Mic on icon */
                    <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z" clipRule="evenodd" />
                    </svg>
                  )}
                </button>
                <span className="text-orange-600 font-medium text-xs">
                  {isMuted ? 'Unmute' : 'Mute'}
                </span>
              </div>
              
              <div className="flex flex-col items-center space-y-1">
                <button
                  onClick={handleSaveConversation}
                  disabled={isCompletingLesson || isCompletingConversation}
                  className="w-14 h-14 rounded-full bg-orange-500 hover:bg-orange-600 text-white font-medium transition-all duration-200 disabled:opacity-50 shadow-lg hover:shadow-xl hover:scale-105 active:scale-95 flex items-center justify-center"
                >
                  {(isCompletingLesson || isCompletingConversation) ? (
                    <div className="animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-white"></div>
                  ) : (
                    <svg className="w-5 h-5 text-white" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M7.707 10.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 00-1.414-1.414L11 11.586V6a1 1 0 10-2 0v5.586l-1.293-1.293zM5 4a2 2 0 012-2h6a2 2 0 012 2v1a1 1 0 11-2 0V4H7v1a1 1 0 11-2 0V4zm0 4a1 1 0 000 2v6a2 2 0 002 2h6a2 2 0 002-2v-6a1 1 0 100-2H5z"/>
                    </svg>
                  )}
                </button>
                <span className="text-orange-600 font-medium text-xs">Save</span>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Error Message - Hidden for now */}
      {false && error && (
        <div className="fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg">
          {error}
        </div>
      )}
      

      
      {/* Lesson Summary Modal */}
      <LessonSummaryModal
        isOpen={showLessonSummary}
        onClose={() => setShowLessonSummary(false)}
        onReturnToDashboard={handleReturnToDashboard}
        summaryData={lessonSummaryData as any}
        loading={loadingSummary}
        token={token}
      />

      {/* Conversation Summary Modal */}
      <LessonSummaryModal
        isOpen={showConversationSummary}
        onClose={() => setShowConversationSummary(false)}
        onReturnToDashboard={handleReturnToDashboard}
        summaryData={conversationSummaryData as any}
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