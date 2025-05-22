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

const ProgressPage = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchConversations = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

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
          .order('created_at', { ascending: false })
          .limit(10);

        if (error) throw error;
        setConversations(data || []);
      } catch (error) {
        console.error('Error fetching conversations:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchConversations();
  }, []);

  // Calculate stats from conversations
  const stats = {
    totalConversations: conversations.length,
    totalMinutes: conversations.length * 15, // Assuming average 15 minutes per conversation
    averageScore: 85, // This would need to be calculated from actual scores
    streak: 7, // This would need to be calculated from actual data
  };

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Learning Progress</h1>
        <div className="text-center">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Learning Progress</h1>

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Total Conversations</h3>
          <p className="text-3xl font-bold text-gray-900">{stats.totalConversations}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Total Minutes</h3>
          <p className="text-3xl font-bold text-gray-900">{stats.totalMinutes}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Average Score</h3>
          <p className="text-3xl font-bold text-gray-900">{stats.averageScore}%</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Current Streak</h3>
          <p className="text-3xl font-bold text-gray-900">{stats.streak} days</p>
        </div>
      </div>

      {/* Recent Conversations */}
      <div className="bg-white rounded-lg shadow">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-lg font-medium">Recent Conversations</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {conversations.map((conversation) => (
            <Link
              key={conversation.id}
              href={`/conversations/${conversation.id}`}
              className="block hover:bg-blue-50 transition rounded-lg p-2"
            >
              <div className="p-4">
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <h3 className="text-lg font-medium">{conversation.context}</h3>
                    <p className="text-sm text-gray-500">
                      {new Date(conversation.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm text-gray-500">
                      Level: {conversation.level}
                    </p>
                    <p className="text-sm text-gray-500">
                      Language: {conversation.language}
                    </p>
                  </div>
                </div>
                <div className="mt-4">
                  <h4 className="text-sm font-medium text-gray-700 mb-2">Conversation Preview:</h4>
                  <p className="text-sm text-gray-600 line-clamp-2">
                    {conversation.messages[0]?.content || 'No messages in this conversation'}
                  </p>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};

export default ProgressPage; 