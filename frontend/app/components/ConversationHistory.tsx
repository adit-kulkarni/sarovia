import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '../../supabaseClient';

interface Conversation {
  id: string;
  context: string;
  language: string;
  level: string;
  created_at: string;
  updated_at: string;
  messages: {
    content: string;
    role: string;
    created_at: string;
  }[];
}

const contextTitles: { [key: string]: string } = {
  restaurant: 'Restaurant',
  drinks: 'Drinks',
  introduction: 'Introduction',
  market: 'Market',
  karaoke: 'Karaoke',
  city: 'City Guide'
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

export default function ConversationHistory() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [contextTitleCache, setContextTitleCache] = useState<{ [key: string]: string }>({});
  const router = useRouter();

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          setError('Not authenticated');
          return;
        }

        const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
        const response = await fetch(`${API_BASE}/api/conversations?token=${session.access_token}`);
        if (!response.ok) {
          throw new Error('Failed to fetch conversations');
        }

        const data = await response.json();
        setConversations(data);
        
        // Load personalized context titles for any conversations that use them
        await loadPersonalizedContextTitles(data, session.access_token);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
  }, []);
  
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

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const getPreviewMessage = (conversation: Conversation) => {
    const messages = conversation.messages;
    if (messages && messages.length > 0) {
      const lastMessage = messages[messages.length - 1];
      return lastMessage.content.substring(0, 50) + (lastMessage.content.length > 50 ? '...' : '');
    }
    return 'No messages';
  };

  if (loading) {
    return (
      <div className="w-80 bg-white/80 backdrop-blur-sm border-r border-orange-100 p-4">
        <div className="animate-pulse">
          <div className="h-4 bg-orange-100 rounded w-3/4 mb-4"></div>
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-orange-50 rounded"></div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="w-80 bg-white/80 backdrop-blur-sm border-r border-orange-100 p-4">
        <div className="text-red-500">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="w-80 bg-white/80 backdrop-blur-sm border-r border-orange-100 p-4 overflow-y-auto h-screen">
      <h2 className="text-xl font-semibold text-orange-700 mb-4">Conversation History</h2>
      <div className="space-y-4">
        {conversations.map((conversation) => (
          <div
            key={conversation.id}
            className="bg-white rounded-lg shadow-sm p-4 cursor-pointer hover:shadow-md transition-shadow"
            onClick={() => router.push(`/chat?context=${conversation.context}&language=${conversation.language}&conversation=${conversation.id}`)}
          >
            <div className="flex justify-between items-start mb-2">
              <div>
                <span className="font-semibold text-orange-600">{getDisplayContextTitle(conversation.context)}</span>
                <span className="text-gray-500 text-sm ml-2">({languageNames[conversation.language]})</span>
              </div>
              <span className="text-xs text-gray-400">{formatDate(conversation.created_at)}</span>
            </div>
            <p className="text-sm text-gray-600 line-clamp-2">{getPreviewMessage(conversation)}</p>
            <div className="mt-2 flex items-center">
              <span className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded">
                Level {conversation.level}
              </span>
            </div>
          </div>
        ))}
        {conversations.length === 0 && (
          <div className="text-center text-gray-500 py-8">
            No conversations yet. Start a new chat to begin!
          </div>
        )}
      </div>
    </div>
  );
} 