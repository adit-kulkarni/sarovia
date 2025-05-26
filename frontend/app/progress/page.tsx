'use client';

import { useEffect, useState } from 'react';
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

interface Mistake {
  category: string;
  type: string;
  error: string;
  correction: string;
  explanation: string;
  severity: 'minor' | 'moderate' | 'critical';
  languageFeatureTags?: string[];
}

interface Feedback {
  messageId: string;
  originalMessage: string;
  mistakes: Mistake[];
  hasMistakes: boolean;
  timestamp: string;
}

const ProgressPage = () => {
  const [loading, setLoading] = useState(true);
  const [feedbacks, setFeedbacks] = useState<Feedback[]>([]);

  useEffect(() => {
    const fetchFeedback = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        // Fetch feedback data from message_feedback table
        const { data, error } = await supabase
          .from('message_feedback')
          .select('*')
          .order('created_at', { ascending: false });

        if (error) throw error;
        setFeedbacks(data || []);
      } catch (error) {
        console.error('Error fetching feedback:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchFeedback();
  }, []);

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <h1 className="text-2xl font-bold mb-6">Learning Progress</h1>
        <div className="text-center">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-6">Learning Progress</h1>

      {/* Top Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Total Conversations</h3>
          <p className="text-3xl font-bold text-gray-900">{feedbacks.length}</p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Total Mistakes</h3>
          <p className="text-3xl font-bold text-gray-900">
            {feedbacks.reduce((acc, f) => acc + f.mistakes.length, 0)}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Perfect Messages</h3>
          <p className="text-3xl font-bold text-gray-900">
            {feedbacks.filter(f => !f.hasMistakes).length}
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-sm font-medium text-gray-500">Average Severity</h3>
          <p className="text-3xl font-bold text-gray-900">
            {/* Calculate average severity */}
            {(() => {
              const severityMap = { minor: 1, moderate: 2, critical: 3 };
              const total = feedbacks.reduce((acc, f) => 
                acc + f.mistakes.reduce((sum, m) => sum + severityMap[m.severity], 0), 0);
              const count = feedbacks.reduce((acc, f) => acc + f.mistakes.length, 0);
              return count ? (total / count).toFixed(1) : '0';
            })()}
          </p>
        </div>
      </div>

      {/* Main Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          {/* 1. Mistake Categories Chart */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Mistake Categories</h3>
            <div className="h-64">
              {/* TODO: Implement pie chart */}
              <p className="text-gray-500 text-center">Pie chart showing distribution of mistake categories</p>
            </div>
          </div>

          {/* 2. Severity Analysis */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Mistake Severity</h3>
            <div className="h-64">
              {/* TODO: Implement stacked bar chart */}
              <p className="text-gray-500 text-center">Stacked bar chart showing severity distribution</p>
            </div>
          </div>

          {/* 3. Common Mistake Types */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Common Mistakes</h3>
            <div className="space-y-4">
              {/* TODO: Implement top mistakes list */}
              <p className="text-gray-500 text-center">List of most common mistake types</p>
            </div>
          </div>
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          {/* 4. Progress Over Time */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Progress Over Time</h3>
            <div className="h-64">
              {/* TODO: Implement line graph */}
              <p className="text-gray-500 text-center">Line graph showing progress over time</p>
            </div>
          </div>

          {/* 5. Language Feature Analysis */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Language Features</h3>
            <div className="h-64">
              {/* TODO: Implement heat map */}
              <p className="text-gray-500 text-center">Heat map of language features</p>
            </div>
          </div>

          {/* 6. Context Performance */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-lg font-medium mb-4">Context Performance</h3>
            <div className="space-y-4">
              {/* TODO: Implement context breakdown */}
              <p className="text-gray-500 text-center">Performance breakdown by context</p>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Section */}
      <div className="mt-6">
        {/* 7. Correction Patterns */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-medium mb-4">Correction Patterns</h3>
          <div className="space-y-4">
            {/* TODO: Implement correction patterns */}
            <p className="text-gray-500 text-center">Most common corrections and patterns</p>
          </div>
        </div>

        {/* 8. Learning Progress Indicators */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-medium mb-4">Learning Progress</h3>
          <div className="space-y-4">
            {/* TODO: Implement progress indicators */}
            <p className="text-gray-500 text-center">Progress bars and achievement badges</p>
          </div>
        </div>

        {/* 9. Personalized Insights */}
        <div className="bg-white rounded-lg shadow p-6 mb-6">
          <h3 className="text-lg font-medium mb-4">Learning Insights</h3>
          <div className="space-y-4">
            {/* TODO: Implement AI-generated insights */}
            <p className="text-gray-500 text-center">AI-generated recommendations and insights</p>
          </div>
        </div>

        {/* 10. Comparative Analysis */}
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-medium mb-4">Comparative Analysis</h3>
          <div className="space-y-4">
            {/* TODO: Implement comparative analysis */}
            <p className="text-gray-500 text-center">Performance comparison with previous periods and peers</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProgressPage; 