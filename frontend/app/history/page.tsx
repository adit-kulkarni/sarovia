'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import { useUser } from '../hooks/useUser';
import LessonSummaryModal from '../components/LessonSummaryModal';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

interface Conversation {
  id: string;
  created_at: string;
  context: string;
  language: string;
  level: string;
  messages: {
    content: string;
    role: string;
    created_at: string;
  }[];
}

interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  feedback?: Mistake[];
}

interface Mistake {
  category: string;
  type: string;
  error: string;
  correction: string;
  explanation: string;
  severity: 'minor' | 'moderate' | 'critical';
}

const contextTitles: { [key: string]: string } = {
  restaurant: 'Ordering at a Restaurant',
  drinks: 'Asking Someone Out for Drinks',
  introduction: 'Introducing Yourself to New People',
  market: 'Haggling at the Local Market',
  karaoke: 'On a Karaoke Night Out',
  city: 'Finding Things to Do in the City'
};

// Cache for personalized context titles
const personalizedContextTitles: { [key: string]: string } = {};

// Function to get context title (handles both classic and personalized contexts)
const getContextTitle = async (contextId: string, token?: string): Promise<string> => {
  // If it's a classic context, return immediately
  if (contextTitles[contextId]) {
    return contextTitles[contextId];
  }
  
  // If it's a personalized context (starts with "user_"), fetch from API
  if (contextId.startsWith('user_')) {
    // Check cache first
    if (personalizedContextTitles[contextId]) {
      return personalizedContextTitles[contextId];
    }
    
    // Fetch from API
    if (token) {
      try {
        const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
        const response = await fetch(`${API_BASE}/api/personalized_contexts?token=${token}`);
        if (response.ok) {
          const data = await response.json();
          const context = data.contexts.find((ctx: any) => ctx.id === contextId);
          if (context) {
            personalizedContextTitles[contextId] = context.title;
            return context.title;
          }
        }
      } catch (error) {
        console.error('Error fetching personalized context title:', error);
      }
    }
  }
  
  // Fallback to the original context ID
  return contextId;
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

const HistoryPage = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<string | null>(null);
  const [conversationData, setConversationData] = useState<ConversationMessage[]>([]);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const user = useUser();

  // Add state for context titles
  const [contextTitleCache, setContextTitleCache] = useState<{ [key: string]: string }>({});

  // Report card modal state
  const [showReportCardModal, setShowReportCardModal] = useState(false);
  const [reportCardData, setReportCardData] = useState<any>(null);
  const [loadingReportCardId, setLoadingReportCardId] = useState<string | null>(null);
  const [reportCardError, setReportCardError] = useState<string | null>(null);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        if (!user) {
          setError('Not authenticated');
          return;
        }

        // Get session and token
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
          setToken(session.access_token);
        }

        const { data, error } = await supabase
          .from('conversations')
          .select(`
            id,
            created_at,
            context,
            language,
            level,
            messages (
              content,
              role,
              created_at
            )
          `)
          .eq('user_id', user.id)
          .order('created_at', { ascending: false });

        if (error) throw error;
        
        const conversationsData = data || [];
        setConversations(conversationsData);
        
        // Load personalized context titles for any conversations that use them
        if (session?.access_token) {
          await loadPersonalizedContextTitles(conversationsData, session.access_token);
        }
      } catch (error) {
        console.error('Error fetching conversations:', error);
        setError('Failed to load conversations');
      } finally {
        setLoading(false);
      }
    };

    if (user) {
      fetchConversations();
    }
  }, [user]);
  
  const loadPersonalizedContextTitles = async (conversations: Conversation[], token: string) => {
    const personalizedContextIds = conversations
      .map(conv => conv.context)
      .filter(contextId => contextId.startsWith('user_'));
    
    if (personalizedContextIds.length === 0) return;
    
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
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

  const loadConversationData = async (conversationId: string) => {
    setConversationLoading(true);
    setConversationError(null);

    try {
      if (!token) {
        throw new Error('No authentication token found');
      }

      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const url = `${API_BASE}/api/conversations/${conversationId}/review?token=${encodeURIComponent(token)}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to load conversation: ${response.status}`);
      }

      const data = await response.json();
      
      // Merge feedback data with messages
      const messagesWithFeedback = (data.messages || []).map((message: any) => {
        const feedback = data.feedback?.[message.id];
        return {
          ...message,
          feedback: feedback?.mistakes || []
        };
      });
      
      setConversationData(messagesWithFeedback);
    } catch (error) {
      console.error('Error loading conversation:', error);
      setConversationError(error instanceof Error ? error.message : 'Failed to load conversation');
    } finally {
      setConversationLoading(false);
    }
  };

  const handleConversationClick = (conversationId: string) => {
    setSelectedConversation(conversationId);
    loadConversationData(conversationId);
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } catch {
      return '';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'moderate': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'minor': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleViewReportCard = async (conversationId: string) => {
    if (!token) {
      setReportCardError('No authentication token found');
      return;
    }

    setLoadingReportCardId(conversationId);
    setReportCardError(null);

    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const encodedConversationId = encodeURIComponent(conversationId);
      const encodedToken = encodeURIComponent(token);
      const summaryUrl = `${API_BASE}/api/conversations/${encodedConversationId}/summary?token=${encodedToken}`;

      console.log('[Report Card] Summary URL:', summaryUrl);

      const response = await fetch(summaryUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to load report card: ${response.status}`);
      }

      const summaryData = await response.json();
      console.log('[Report Card] Fetched summary:', summaryData);
      
      setReportCardData(summaryData);
      setShowReportCardModal(true);
    } catch (error) {
      console.error('Error loading report card:', error);
      setReportCardError(error instanceof Error ? error.message : 'Failed to load report card');
    } finally {
      setLoadingReportCardId(null);
    }
  };

  const handleCloseReportCard = () => {
    setShowReportCardModal(false);
    setReportCardData(null);
    setReportCardError(null);
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Conversation History</h1>
        <div className="text-center">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Conversation History</h1>
        <div className="text-red-500 text-center">{error}</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Conversation History</h1>

      {selectedConversation ? (
        // Conversation Detail View
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-medium">Conversation Review</h2>
            <button
              onClick={() => {
                setSelectedConversation(null);
                setConversationData([]);
                setConversationError(null);
              }}
              className="text-gray-500 hover:text-gray-700 px-3 py-1 rounded-md border border-gray-300 hover:bg-gray-50"
            >
              ← Back to History
            </button>
          </div>
          
          <div className="p-6">
            {conversationLoading ? (
              <div className="flex flex-col items-center justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-orange-500 mb-4"></div>
                <p className="text-gray-600">Loading conversation...</p>
              </div>
            ) : conversationError ? (
              <div className="text-center py-12 text-red-500">
                <p>Error: {conversationError}</p>
              </div>
            ) : conversationData.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <p>No conversation history available.</p>
              </div>
            ) : (
              <div className="bg-white rounded-xl border-2 border-gray-200 max-h-96 overflow-y-auto">
                {conversationData.every(msg => msg.role === 'user') && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 m-4 mb-2">
                    <p className="text-sm text-yellow-800">
                      <span className="font-semibold">Note:</span> This conversation only contains your messages. 
                      AI responses may not have been saved properly during this session.
                    </p>
                  </div>
                )}
                <div className="p-4 space-y-4">
                  {conversationData.map((message) => (
                    <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                        message.role === 'user' 
                          ? 'bg-orange-500 text-white' 
                          : 'bg-gray-200 text-gray-800'
                      }`}>
                        <div className="text-sm">{message.content}</div>
                        {message.timestamp && (
                          <div className={`text-xs mt-1 ${
                            message.role === 'user' ? 'text-orange-100' : 'text-gray-500'
                          }`}>
                            {formatTimestamp(message.timestamp)}
                          </div>
                        )}
                        
                        {/* Feedback for user messages */}
                        {message.role === 'user' && message.feedback && message.feedback.length > 0 && (
                          <div className="mt-3 space-y-2">
                            {message.feedback.map((mistake, index) => (
                              <div key={index} className="bg-white rounded-lg p-3 text-gray-800 shadow-sm">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs font-semibold text-gray-600 uppercase">
                                    {mistake.category} - {mistake.type}
                                  </span>
                                  <span className={`px-2 py-1 rounded-full text-xs font-semibold border ${getSeverityColor(mistake.severity)}`}>
                                    {mistake.severity}
                                  </span>
                                </div>
                                <div className="text-sm mb-2">
                                  <span className="line-through text-red-600">{mistake.error}</span>
                                  <span className="mx-2">→</span>
                                  <span className="text-green-600 font-semibold">{mistake.correction}</span>
                                </div>
                                <p className="text-xs text-gray-600">{mistake.explanation}</p>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      ) : (
        // Conversation List View
        <div className="bg-white rounded-lg shadow">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-medium">Your Conversations</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {conversations.length === 0 ? (
              <div className="p-6 text-center text-gray-500">
                No conversations yet. Start a new chat to begin!
              </div>
            ) : (
              conversations.map((conversation) => (
                <div
                  key={conversation.id}
                  className="block hover:bg-orange-50 transition rounded-lg p-2"
                >
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div
                        onClick={() => handleConversationClick(conversation.id)}
                        className="cursor-pointer flex-1"
                      >
                        <h3 className="text-lg font-medium text-orange-600">
                          {getDisplayContextTitle(conversation.context)}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {new Date(conversation.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="text-right flex flex-col items-end">
                        <div className="mb-2">
                          <p className="text-sm text-gray-500">
                            Level: {conversation.level}
                          </p>
                          <p className="text-sm text-gray-500">
                            {languageNames[conversation.language] || conversation.language}
                          </p>
                          <p className="text-sm font-medium text-orange-600 mt-1">
                            {conversation.messages.length} {conversation.messages.length === 1 ? 'message' : 'messages'}
                          </p>
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleViewReportCard(conversation.id);
                          }}
                          disabled={loadingReportCardId === conversation.id}
                          className="px-3 py-1.5 text-xs rounded-lg font-semibold shadow transition-colors bg-orange-300 hover:bg-orange-400 text-orange-800 disabled:opacity-50"
                        >
                          {loadingReportCardId === conversation.id ? 'Loading...' : '📊 Report Card'}
                        </button>
                      </div>
                    </div>
                    <div
                      onClick={() => handleConversationClick(conversation.id)}
                      className="mt-4 cursor-pointer"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <h4 className="text-sm font-medium text-gray-700">Conversation Preview:</h4>
                        <span className="text-xs text-gray-500">
                          {conversation.messages.length} {conversation.messages.length === 1 ? 'message' : 'messages'} • {conversation.messages.filter(m => m.role === 'user').length} from you
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 line-clamp-2">
                        {conversation.messages[0]?.content || 'No messages in this conversation'}
                      </p>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* Report Card Modal */}
      <LessonSummaryModal
        isOpen={showReportCardModal}
        onClose={handleCloseReportCard}
        onReturnToDashboard={() => {
          handleCloseReportCard();
          // Stay on history page - no redirect needed
        }}
        summaryData={reportCardData}
        loading={loadingReportCardId !== null}
        token={token}
      />

      {/* Report Card Error Display */}
      {reportCardError && (
        <div className="fixed bottom-4 right-4 bg-red-500 text-white px-4 py-2 rounded-lg shadow-lg">
          {reportCardError}
          <button
            onClick={() => setReportCardError(null)}
            className="ml-2 text-white hover:text-gray-200"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
};

export default HistoryPage; 