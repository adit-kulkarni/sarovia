'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';

// Types
interface InsightCard {
  id: string;
  message: string;
  type: string;
  severity: string;
  trend: string;
  action: string;
  chart_type: string;
  chart_data: {
    labels: string[];
    data: number[];
    type: string;
  };
  examples?: any[];
  improvement_percentage?: number;
}

interface InsightsData {
  insights: InsightCard[];
  last_updated: string;
  analysis_period: string;
  summary: {
    total_patterns: number;
    total_conversations: number;
    improvement_areas: number;
  };
}

// Chart Component
const SimpleChart: React.FC<{ data: InsightCard['chart_data']; className?: string }> = ({ data, className = '' }) => {
  if (!data.labels || !data.data || data.labels.length === 0) {
    return <div className={`text-gray-400 text-sm ${className}`}>No chart data available</div>;
  }

  const maxValue = data.data.length > 0 ? Math.max(...data.data) : 1;
  
  if (data.type === 'bar') {
    return (
      <div className={`space-y-2 ${className}`}>
        {data.labels.map((label, index) => (
          <div key={index} className="flex items-center gap-2">
            <div className="w-20 text-xs text-gray-600 truncate">{label}</div>
            <div className="flex-1 bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-500 h-2 rounded-full" 
                style={{ width: `${(data.data[index] / maxValue) * 100}%` }}
              />
            </div>
            <div className="w-8 text-xs text-gray-600">{data.data[index]}</div>
          </div>
        ))}
      </div>
    );
  }
  
  if (data.type === 'line') {
    return (
      <div className={`flex items-end gap-1 h-16 ${className}`}>
        {data.data.map((value, index) => (
          <div key={index} className="flex-1 flex flex-col items-center">
            <div 
              className="bg-blue-500 rounded-t w-full"
              style={{ height: `${(value / maxValue) * 100}%`, minHeight: '2px' }}
            />
            <div className="text-xs text-gray-600 mt-1 truncate w-full text-center">
              {data.labels[index]}
            </div>
          </div>
        ))}
      </div>
    );
  }
  
  return <div className={`text-gray-400 text-sm ${className}`}>Chart type not supported</div>;
};

// Insight Card Component
const InsightCardComponent: React.FC<{ 
  insight: InsightCard; 
  onClick: () => void; 
  isExpanded: boolean;
}> = ({ insight, onClick, isExpanded }) => {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'border-red-200 bg-red-50';
      case 'moderate': return 'border-orange-200 bg-orange-50';
      case 'low': return 'border-green-200 bg-green-50';
      default: return 'border-blue-200 bg-blue-50';
    }
  };

  const getTrendIcon = (trend: string) => {
    switch (trend) {
      case 'increasing': return '↗';
      case 'decreasing': return '↘';
      case 'stable': return '→';
      default: return '•';
    }
  };

  return (
    <div 
      className={`border rounded-lg p-4 cursor-pointer transition-all duration-200 ${getSeverityColor(insight.severity)} hover:shadow-md`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-gray-800 font-medium mb-2">{insight.message}</p>
          <div className="flex items-center gap-2 text-sm text-gray-600">
            <span>{getTrendIcon(insight.trend)}</span>
            <span className="capitalize">{insight.trend}</span>
            <span>•</span>
            <span className="capitalize">{insight.severity} priority</span>
          </div>
        </div>
        <div className="text-gray-400 ml-2">
          {isExpanded ? '▲' : '▼'}
        </div>
      </div>
      
      {isExpanded && (
        <div className="mt-4 space-y-3 border-t pt-3">
          <div>
            <h4 className="font-medium text-gray-700 mb-2">Pattern Over Time</h4>
            <SimpleChart data={insight.chart_data} />
          </div>
          
          {insight.examples && insight.examples.length > 0 && (
            <div>
              <h4 className="font-medium text-gray-700 mb-2">Recent Examples</h4>
              <div className="space-y-2">
                {insight.examples.slice(0, 2).map((example, index) => (
                  <div key={index} className="bg-white p-2 rounded border text-sm">
                    <div className="text-red-600">✗ {example.error}</div>
                    <div className="text-green-600">✓ {example.correction}</div>
                    {example.explanation && (
                      <div className="text-gray-600 mt-1">{example.explanation}</div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          <div className="bg-blue-100 p-3 rounded">
            <h4 className="font-medium text-blue-800 mb-1">Suggested Action</h4>
            <p className="text-blue-700 text-sm">{insight.action}</p>
          </div>
        </div>
      )}
    </div>
  );
};

// Helper to rank verbs by strength
function rankVerbs(verbs: Record<string, Record<string, string[]>>) {
  return Object.entries(verbs)
    .map(([lemma, tenses]) => {
      const tenseCount = Object.keys(tenses).length;
      const personSet = new Set<string>();
      Object.values(tenses).forEach(persons => persons.forEach(p => personSet.add(p)));
      return {
        lemma,
        tenseCount,
        personCount: personSet.size,
        score: tenseCount * personSet.size,
        tenses: tenses
      };
    })
    .sort((a, b) => b.score - a.score);
}

const PARTS = [
  'nouns', 'pronouns', 'adjectives', 'verbs', 'adverbs', 
  'prepositions', 'conjunctions', 'articles', 'interjections',
];

export default function ProgressPage() {
  const [activeTab, setActiveTab] = useState('insights');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [insights, setInsights] = useState(null);
  const router = useRouter();

  useEffect(() => {
    const checkAuth = () => {
      const token = localStorage.getItem('token');
      if (!token) {
        router.push('/');
        return;
      }
      
      // For now, just load demo data
      setTimeout(() => {
        setInsights({
          insights: [
            {
              id: 'demo-1',
              message: "You've been mixing up 'ser' and 'estar' in recent conversations",
              type: 'grammar_pattern',
              severity: 'moderate',
              trend: 'stable',
              action: 'Practice the differences between ser (permanent) and estar (temporary)'
            },
            {
              id: 'demo-2', 
              message: "Your past tense conjugations have improved this month!",
              type: 'progress_trend',
              severity: 'low',
              trend: 'improving',
              action: 'Keep practicing past tense verbs to maintain progress'
            }
          ],
          summary: {
            total_conversations: 12,
            total_patterns: 8,
            improvement_areas: 2
          }
        });
        setLoading(false);
      }, 1000);
    };

    checkAuth();
  }, [router]);

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-12 bg-gray-200 rounded w-1/2"></div>
          <div className="space-y-3">
            <div className="h-32 bg-gray-200 rounded"></div>
            <div className="h-32 bg-gray-200 rounded"></div>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h2 className="text-red-800 font-semibold">Error</h2>
          <p className="text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">Your Progress</h1>
        <p className="text-gray-600">AI-powered insights into your language learning journey</p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-8">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('insights')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'insights'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Insights
            {insights && insights.summary.improvement_areas > 0 && (
              <span className="ml-2 bg-red-100 text-red-800 text-xs font-medium px-2 py-0.5 rounded-full">
                {insights.summary.improvement_areas}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('growth')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'growth'
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            Your Growth
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'insights' && (
        <div className="space-y-6">
          {insights && insights.insights.length > 0 ? (
            <>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
                <h3 className="font-semibold text-blue-800 mb-2">Analysis Summary</h3>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <div className="text-2xl font-bold text-blue-600">{insights.summary.total_conversations}</div>
                    <div className="text-blue-700">Conversations Analyzed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-blue-600">{insights.summary.total_patterns}</div>
                    <div className="text-blue-700">Patterns Identified</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-blue-600">30 days</div>
                    <div className="text-blue-700">Analysis Period</div>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                {insights.insights.map((insight) => (
                  <div
                    key={insight.id}
                    className={`border rounded-lg p-4 transition-all duration-200 hover:shadow-md ${
                      insight.severity === 'high' ? 'border-red-200 bg-red-50' :
                      insight.severity === 'moderate' ? 'border-orange-200 bg-orange-50' :
                      'border-green-200 bg-green-50'
                    }`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <p className="text-gray-800 font-medium mb-2">{insight.message}</p>
                        <div className="flex items-center gap-2 text-sm text-gray-600">
                          <span>{insight.trend === 'improving' ? '↗' : insight.trend === 'stable' ? '→' : '↘'}</span>
                          <span className="capitalize">{insight.trend}</span>
                          <span>•</span>
                          <span className="capitalize">{insight.severity} priority</span>
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-4 bg-blue-100 p-3 rounded">
                      <h4 className="font-medium text-blue-800 mb-1">Suggested Action</h4>
                      <p className="text-blue-700 text-sm">{insight.action}</p>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="text-center py-12">
              <div className="text-6xl mb-4">📊</div>
              <h3 className="text-xl font-semibold text-gray-700 mb-2">No Insights Yet</h3>
              <p className="text-gray-600 mb-4">
                Start having conversations to see personalized insights about your learning progress.
              </p>
              <button
                onClick={() => router.push('/chat')}
                className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700"
              >
                Start Practicing
              </button>
            </div>
          )}
        </div>
      )}

      {activeTab === 'growth' && (
        <div className="space-y-8">
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📈</div>
            <h3 className="text-xl font-semibold text-gray-700 mb-2">Growth Analysis Coming Soon</h3>
            <p className="text-gray-600">
              Your detailed knowledge analysis will appear here as you practice more.
            </p>
          </div>
        </div>
      )}
    </div>
  );
} 