'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import { useUser } from '../hooks/useUser';

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
        setConversations(data || []);
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
                  onClick={() => handleConversationClick(conversation.id)}
                  className="block hover:bg-orange-50 transition rounded-lg p-2 cursor-pointer"
                >
                  <div className="p-4">
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="text-lg font-medium text-orange-600">
                          {contextTitles[conversation.context] || conversation.context}
                        </h3>
                        <p className="text-sm text-gray-500">
                          {new Date(conversation.created_at).toLocaleDateString()}
                        </p>
                      </div>
                      <div className="text-right">
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
                    </div>
                    <div className="mt-4">
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
    </div>
  );
};

export default HistoryPage; 