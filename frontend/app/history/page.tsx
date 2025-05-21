'use client';

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

export default function History() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConversation, setSelectedConversation] = useState<Conversation | null>(null);
  const router = useRouter();

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (!session) {
          setError('Not authenticated');
          return;
        }

        const response = await fetch(`http://localhost:8000/api/conversations?token=${session.access_token}`);
        if (!response.ok) {
          throw new Error('Failed to fetch conversations');
        }

        const data = await response.json();
        setConversations(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'An error occurred');
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
  }, []);

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  };

  const startNewChat = () => {
    router.push('/chat');
  };

  if (loading) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-6xl mx-auto">
          <div className="animate-pulse space-y-4">
            <div className="h-8 bg-orange-100 rounded w-1/4"></div>
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="h-32 bg-orange-50 rounded"></div>
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen p-8">
        <div className="max-w-6xl mx-auto">
          <div className="text-red-500">Error: {error}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <h1 className="text-3xl font-bold text-orange-600">Conversation History</h1>
          <button
            onClick={startNewChat}
            className="bg-orange-500 hover:bg-orange-600 text-white px-6 py-2 rounded-lg transition-colors"
          >
            Start New Chat
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Conversation List */}
          <div className="space-y-4">
            {conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`bg-white/80 backdrop-blur-sm rounded-xl p-4 cursor-pointer transition-all ${
                  selectedConversation?.id === conversation.id
                    ? 'ring-2 ring-orange-500 shadow-lg'
                    : 'hover:shadow-md'
                }`}
                onClick={() => setSelectedConversation(conversation)}
              >
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <span className="font-semibold text-orange-600">{contextTitles[conversation.context]}</span>
                    <span className="text-gray-500 text-sm ml-2">({languageNames[conversation.language]})</span>
                  </div>
                  <span className="text-xs text-gray-400">{formatDate(conversation.created_at)}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs bg-orange-100 text-orange-700 px-2 py-1 rounded">
                    Level {conversation.level}
                  </span>
                  <span className="text-xs text-gray-500">
                    {conversation.messages.length} messages
                  </span>
                </div>
              </div>
            ))}
            {conversations.length === 0 && (
              <div className="text-center text-gray-500 py-8 bg-white/80 backdrop-blur-sm rounded-xl">
                No conversations yet. Start a new chat to begin!
              </div>
            )}
          </div>

          {/* Conversation Details */}
          <div className="bg-white/80 backdrop-blur-sm rounded-xl p-4">
            {selectedConversation ? (
              <div className="space-y-4">
                <div className="border-b border-orange-100 pb-4">
                  <h2 className="text-xl font-semibold text-orange-700">
                    {contextTitles[selectedConversation.context]}
                  </h2>
                  <p className="text-sm text-gray-500">
                    {languageNames[selectedConversation.language]} • Level {selectedConversation.level}
                  </p>
                  <p className="text-xs text-gray-400 mt-1">
                    {formatDate(selectedConversation.created_at)}
                  </p>
                </div>
                <div className="space-y-4 max-h-[600px] overflow-y-auto">
                  {selectedConversation.messages.map((message, index) => (
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
                          {new Date(message.created_at).toLocaleTimeString()}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => router.push(`/chat?context=${selectedConversation.context}&language=${selectedConversation.language}&conversation=${selectedConversation.id}`)}
                  className="w-full bg-orange-500 hover:bg-orange-600 text-white px-4 py-2 rounded-lg transition-colors"
                >
                  Continue Conversation
                </button>
              </div>
            ) : (
              <div className="text-center text-gray-500 py-8">
                Select a conversation to view details
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 