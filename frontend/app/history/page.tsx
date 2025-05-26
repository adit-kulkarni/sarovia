'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';
import Link from 'next/link';

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

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) {
          setError('Not authenticated');
          return;
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

    fetchConversations();
  }, []);

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

      {/* Conversation List */}
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
              <Link
                key={conversation.id}
                href={`/chat?context=${conversation.context}&language=${conversation.language}&level=${conversation.level}&conversation=${conversation.id}`}
                className="block hover:bg-orange-50 transition rounded-lg p-2"
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
              </Link>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default HistoryPage; 