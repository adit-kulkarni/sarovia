'use client';

import { useEffect, useState, Fragment } from 'react';
import { useRouter } from 'next/navigation';
import { useUser } from './hooks/useUser';
import Auth from './Auth';
import { supabase } from '../supabaseClient';
import MistakeCategoriesChart from './components/MistakeCategoriesChart';
import SeverityAnalysisChart from './components/SeverityAnalysisChart';
import CommonMistakesList from './components/CommonMistakesList';
import ProgressOverTimeChart from './components/ProgressOverTimeChart';
import ScaledMistakesPerConversationChart from './components/ScaledMistakesPerConversationChart';
import LanguageFeaturesHeatmap from './components/LanguageFeaturesHeatmap';
import PrimaryProgressTimeline from './components/PrimaryProgressTimeline';
import CorrectionPatterns from './components/CorrectionPatterns';
import ProficiencyLevelChart from './components/ProficiencyLevelChart';
import { createClient } from '@supabase/supabase-js';
import { Dialog, Transition } from '@headlessui/react';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/solid';
import { XMarkIcon } from '@heroicons/react/24/outline';
import '@fontsource/press-start-2p';
import YourKnowledgePanel from './components/YourKnowledgePanel';
import { useToast } from './components/Toast';

import LessonSummaryModal from './components/LessonSummaryModal';

interface LanguageCard {
  code: string;
  name: string;
  flag: string;
  countryFlags: string[];
}

interface ContextCard {
  id: string;
  title: string;
  description: string;
  icon: string;
}

interface PersonalizedContext {
  id: string;
  title: string;
  description: string;
  icon: string;
  interest_tags: string[];
}

interface Curriculum {
  id: string;
  language: string;
  start_level: string;
  current_lesson?: number;
  created_at?: string;
}

interface LessonPreview {
  id: string;
  title: string;
  order_num: number;
  status?: string;
}

interface LessonTemplatePreview {
  id: string;
  order_num: number;
  title: string;
  objectives?: string;
  level?: string;
  difficulty?: string;
  progress?: {
    status: 'not_started' | 'in_progress' | 'completed';
    turns_completed: number;
    required_turns: number;
  };
}

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
  created_at?: string;
  conversation_id?: string;
  language?: string;
}

interface LessonSummaryData {
  lessonTitle: string;
  totalTurns: number;
  totalMistakes: number;
  achievements: Achievement[];
  mistakesByCategory: MistakeSummary[];
  conversationDuration: string;
  wordsUsed: number;
  conversationCount: number;
  improvementAreas: string[];
  conversationId?: string;
}

interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string;
  type: 'new' | 'improved' | 'milestone';
  value?: string | number;
}

interface MistakeSummary {
  category: string;
  count: number;
  severity: 'minor' | 'moderate' | 'critical';
  examples: Array<{
    error: string;
    correction: string;
    explanation: string;
  }>;
}

const languages: LanguageCard[] = [
  { 
    code: 'en', 
    name: 'English', 
    flag: '🇬🇧',
    countryFlags: ['🇬🇧', '🇺🇸', '🇨🇦', '🇦🇺', '🇳🇿', '🇮🇪', '🇿🇦', '🇸🇬', '🇮🇳', '🇯🇲']
  },
  { 
    code: 'it', 
    name: 'Italian', 
    flag: '🇮🇹',
    countryFlags: ['🇮🇹', '🇻🇦', '🇸🇲', '🇨🇭', '🇲🇹', '🇸🇮', '🇭🇷', '🇦🇷', '🇧🇷', '🇺🇸']
  },
  { 
    code: 'es', 
    name: 'Spanish', 
    flag: '🇪🇸',
    countryFlags: ['🇪🇸', '🇲🇽', '🇦🇷', '🇨🇴', '🇵🇪', '🇻🇪', '🇨🇱', '🇪🇨', '🇬🇹', '🇨🇺']
  },
  { 
    code: 'pt', 
    name: 'Portuguese', 
    flag: '🇵🇹',
    countryFlags: ['🇵🇹', '🇧🇷', '🇦🇴', '🇲🇿', '🇨🇻', '🇬🇼', '🇸🇹', '🇹🇱', '🇲🇴', '🇬🇶']
  },
  { 
    code: 'fr', 
    name: 'French', 
    flag: '🇫🇷',
    countryFlags: ['🇫🇷', '🇨🇦', '🇧🇪', '🇨🇭', '🇱🇺', '🇲🇨', '🇸🇳', '🇨🇮', '🇲🇦', '🇭🇹']
  },
  { 
    code: 'de', 
    name: 'German', 
    flag: '🇩🇪',
    countryFlags: ['🇩🇪', '🇦🇹', '🇨🇭', '🇱🇮', '🇱🇺', '🇧🇪', '🇩🇰', '🇵🇱', '🇮🇹', '🇳🇦']
  },
  { 
    code: 'kn', 
    name: 'Kannada', 
    flag: '🇮🇳',
    countryFlags: ['🇮🇳']
  }
];

const contextCards: ContextCard[] = [
  {
    id: 'restaurant',
    title: 'Ordering at a Restaurant',
    description: 'Practice ordering food and drinks, making special requests, and interacting with waitstaff',
    icon: '🍽️'
  },
  {
    id: 'drinks',
    title: 'Asking Someone Out for Drinks',
    description: 'Learn how to invite someone for drinks and maintain an engaging conversation',
    icon: '🍷'
  },
  {
    id: 'introduction',
    title: 'Introducing Yourself to New People',
    description: 'Practice making introductions and starting conversations with new acquaintances',
    icon: '👋'
  },
  {
    id: 'market',
    title: 'Haggling at the Local Market',
    description: 'Master the art of negotiation and bargaining at local markets',
    icon: '🛍️'
  },
  {
    id: 'karaoke',
    title: 'On a Karaoke Night Out',
    description: 'Experience a fun night out with friends at karaoke',
    icon: '🎤'
  },
  {
    id: 'city',
    title: 'Finding Things to Do in the City',
    description: 'Learn how to ask for and discuss local attractions and activities',
    icon: '🏙️'
  }
];

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
const languagesList = [
  { code: 'en', name: 'English' },
  { code: 'it', name: 'Italian' },
  { code: 'es', name: 'Spanish' },
  { code: 'pt', name: 'Portuguese' },
  { code: 'fr', name: 'French' },
  { code: 'de', name: 'German' },
  { code: 'kn', name: 'Kannada' },
];

const supabaseClient = createClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
);

// Component to display multiple country flags with overflow handling
const MultiCountryFlags = ({ language }: { language: LanguageCard }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const maxVisibleFlags = 3; // Show up to 3 flags initially
  const visibleFlags = language.countryFlags.slice(0, maxVisibleFlags);
  const allFlags = language.countryFlags;
  
  return (
    <div className="flex items-center gap-1 relative flex-1 mr-2">
      {/* Language name */}
      <span className="font-bold text-2xl mr-2">{language.name}</span>
      
      {/* Visible flags with hover for all flags */}
      <div 
        className="flex items-center gap-1 relative cursor-help"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        {visibleFlags.map((flag, index) => (
          <span key={index} className="text-lg">{flag}</span>
        ))}
        
        {/* Tooltip showing all flags */}
        {showTooltip && allFlags.length > maxVisibleFlags && (
          <div className="absolute top-full left-0 mt-2 bg-black text-white px-3 py-2 rounded-lg text-sm whitespace-nowrap z-50 shadow-lg">
            {allFlags.join(' ')}
            <div className="absolute bottom-full left-4 border-4 border-transparent border-b-black"></div>
          </div>
        )}
      </div>
    </div>
  );
};

// AI Insights Component
// Progress Section Component with Tabs
const ProgressSection = ({ 
  selectedCurriculum, 
  feedbackLoading, 
  feedbackError, 
  filteredFeedbacks, 
  knowledgeRefreshKey, 
  token 
}: {
  selectedCurriculum: Curriculum;
  feedbackLoading: boolean;
  feedbackError: string | null;
  filteredFeedbacks: Feedback[];
  knowledgeRefreshKey: number;
  token: string | null;
}) => {
  // Persist tab state in localStorage to survive component remounting
  const [activeTab, setActiveTab] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('progressActiveTab') || 'timeline';
    }
    return 'timeline';
  });

  // Update localStorage when tab changes
  const handleTabChange = (tab: string) => {
    setActiveTab(tab);
    if (typeof window !== 'undefined') {
      localStorage.setItem('progressActiveTab', tab);
    }
  };
  
  // Get all mistakes from feedbacks
  const allMistakes = filteredFeedbacks.reduce((acc, feedback) => [...acc, ...feedback.mistakes], [] as Mistake[]);
  
  if (feedbackLoading) {
    return (
      <div className="mb-8">
        <h2 className="retro-header text-3xl font-extrabold text-center mb-4">Your Progress</h2>
        <div className="bg-white rounded shadow p-6 text-gray-500 text-center">Loading analytics...</div>
      </div>
    );
  }
  
  if (feedbackError) {
    return (
      <div className="mb-8">
        <h2 className="retro-header text-3xl font-extrabold text-center mb-4">Your Progress</h2>
        <div className="bg-white rounded shadow p-6 text-red-500 text-center">{feedbackError}</div>
      </div>
    );
  }

  return (
    <div className="mb-8">
      <h2 className="retro-header text-3xl font-extrabold text-center mb-6">Your Progress</h2>
      
      {/* Tab Navigation */}
      <div className="mb-8">
        <nav className="flex justify-center space-x-3">
          <button
            onClick={() => handleTabChange('timeline')}
            className={`py-4 px-6 rounded-full font-bold text-lg transition-all duration-200 ${
              activeTab === 'timeline'
                ? 'bg-orange-500 text-white shadow-lg'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
          >
            🚀 Growth
          </button>
          <button
            onClick={() => handleTabChange('growth')}
            className={`py-4 px-6 rounded-full font-bold text-lg transition-all duration-200 ${
              activeTab === 'growth'
                ? 'bg-orange-500 text-white shadow-lg'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
          >
            🧠 Knowledge
          </button>
          <button
            onClick={() => handleTabChange('data')}
            className={`py-4 px-6 rounded-full font-bold text-lg transition-all duration-200 ${
              activeTab === 'data'
                ? 'bg-orange-500 text-white shadow-lg'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
          >
            📝 Feedback
          </button>
          <button
            onClick={() => handleTabChange('insights')}
            className={`py-4 px-6 rounded-full font-bold text-lg transition-all duration-200 ${
              activeTab === 'insights'
                ? 'bg-orange-500 text-white shadow-lg'
                : 'bg-gray-200 text-gray-600 hover:bg-gray-300'
            }`}
          >
            💡 Insights
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'timeline' && (
        <div className="space-y-6">
          {/* Primary Progress Timeline */}
          <div className="bg-white rounded-lg shadow p-6 h-[600px] flex flex-col">
            <PrimaryProgressTimeline 
              selectedCurriculum={selectedCurriculum}
            />
          </div>
        </div>
      )}

      {activeTab === 'growth' && (
        <div className="space-y-6">
          {/* Your Knowledge Panel */}
          <div className="bg-white rounded-lg shadow p-6">
            <YourKnowledgePanel 
              language={selectedCurriculum.language} 
              level={selectedCurriculum.start_level}
              refreshTrigger={knowledgeRefreshKey}
            />
          </div>
        </div>
      )}

      {activeTab === 'insights' && (
        <div className="space-y-6">
          {token && (
            <AIInsightsSection 
              curriculumId={selectedCurriculum.id}
              token={token}
              language={selectedCurriculum.language}
            />
          )}
          

        </div>
      )}

      {activeTab === 'data' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-6">
            {/* Mistake Categories Chart */}
            <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
              <h3 className="text-lg font-medium mb-4">Mistake Categories</h3>
              <div className="flex-1 overflow-hidden">
                <MistakeCategoriesChart mistakes={allMistakes} />
              </div>
            </div>
            
            {/* Common Mistake Types */}
            <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
              <h3 className="text-lg font-medium mb-4">Common Mistakes</h3>
              <div className="flex-1 overflow-y-auto">
                <CommonMistakesList mistakes={allMistakes} />
              </div>
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Language Feature Analysis */}
            <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
              <h3 className="text-lg font-medium mb-4">Language Features</h3>
              <div className="flex-1 overflow-y-auto">
                <LanguageFeaturesHeatmap mistakes={allMistakes} />
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const AIInsightsSection = ({ curriculumId, token, language }: { 
  curriculumId: string; 
  token: string; 
  language: string; 
}) => {
  const router = useRouter();
  const { addToast } = useToast();
  const [insights, setInsights] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [hasTimedOut, setHasTimedOut] = useState(false);
  const [isForceRefresh, setIsForceRefresh] = useState(false);
  const [showLessonModal, setShowLessonModal] = useState(false);
  const [selectedInsight, setSelectedInsight] = useState<any>(null);
  const [lessonPreview, setLessonPreview] = useState<any>(null);
  const [generatingLesson, setGeneratingLesson] = useState(false);

  const fetchInsights = async (forceRefresh = false) => {
    try {
      const loadingState = forceRefresh ? setRefreshing : setLoading;
      loadingState(true);
      setError(null);
      setHasTimedOut(false);
      setIsForceRefresh(forceRefresh);
      
      // Add timeout handling
      const controller = new AbortController();
      const timeoutId = setTimeout(() => {
        controller.abort();
        setHasTimedOut(true);
      }, 45000); // 45 second timeout
      
      // Use fast endpoint by default, fallback to full insights on refresh
      const endpoint = forceRefresh ? 'insights' : 'insights/fast';
      const url = `${API_BASE}/api/${endpoint}?curriculum_id=${curriculumId}&days=30&token=${token}${forceRefresh ? '&refresh=true' : ''}`;
      const response = await fetch(url, {
        signal: controller.signal,
        headers: {
          'Cache-Control': forceRefresh ? 'no-cache' : 'default'
        }
      });
      
      clearTimeout(timeoutId);
      
      if (response.ok) {
        const data = await response.json();
        console.log('Insights API response:', data);
        setInsights(data);
        setError(null);
      } else {
        const errorText = await response.text();
        console.error('Insights API error:', response.status, errorText);
        throw new Error(`Failed to fetch insights: ${response.status}`);
      }
    } catch (err: any) {
      console.error('Error fetching insights:', err);
      if (err.name === 'AbortError' || hasTimedOut) {
        setError('Insights are taking longer than usual to load. This may be due to analyzing a large amount of conversation data. Please try again or use the Refresh button.');
        setHasTimedOut(true);
      } else {
        setError('Failed to load insights from your conversation data. Please try refreshing.');
      }
      // Don't clear insights on error - keep showing previous data if available
    } finally {
      setLoading(false);
      setRefreshing(false);
      setIsForceRefresh(false);
    }
  };

  const handlePracticeNow = async (insight: any) => {
    setSelectedInsight(insight);
    setGeneratingLesson(true);
    setShowLessonModal(true);
    
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${API_BASE}/api/generate_targeted_lesson?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          curriculum_id: curriculumId,
          insight_data: {
            category: insight.type.split('_')[0], // Extract category from type like "grammar_pattern"
            message: insight.message,
            severity: insight.severity,
            chart_data: insight.chart_data || {}
          },
          language: language
        })
      });

      if (response.ok) {
        const lesson = await response.json();
        setLessonPreview(lesson);
      } else {
        throw new Error('Failed to generate lesson');
      }
    } catch (err) {
      console.error('Error generating targeted lesson:', err);
      // Handle error - maybe show error message in modal
    } finally {
      setGeneratingLesson(false);
    }
  };

  const handleCreateLesson = async () => {
    if (!lessonPreview || !token) return;
    
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      
      // Step 1: Save the lesson
      const saveResponse = await fetch(`${API_BASE}/api/save_custom_lesson?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          curriculum_id: curriculumId,
          language: language,
          ...lessonPreview
        })
      });

      if (!saveResponse.ok) {
        throw new Error('Failed to save lesson');
      }

      const savedLesson = await saveResponse.json();
      console.log('Lesson created successfully:', savedLesson);

      // Step 2: Start a conversation with the custom lesson
      const startResponse = await fetch(`${API_BASE}/api/start_custom_lesson_conversation?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          custom_lesson_id: savedLesson.id,
          curriculum_id: curriculumId,
        }),
      });

      if (!startResponse.ok) {
        throw new Error('Failed to start lesson conversation');
      }

      const conversationData = await startResponse.json();

      // Step 3: Close modal and navigate to chat
      setShowLessonModal(false);
      setLessonPreview(null);
      setSelectedInsight(null);
      
      // Navigate to the chat interface with the new conversation
      router.push(`/chat?conversation=${conversationData.conversation_id}&curriculum_id=${curriculumId}`);
      
    } catch (err) {
      console.error('Error creating and starting lesson:', err);
      addToast(err instanceof Error ? err.message : 'Failed to create and start lesson', 'error');
    }
  };

  useEffect(() => {
    let mounted = true;
    
    if (curriculumId && token) {
      fetchInsights().then(() => {
        if (!mounted) return;
        // Component is still mounted after fetch
      });
    }
    
    return () => {
      mounted = false;
    };
  }, [curriculumId, token, language]);

  // Loading state with timeout message
  if (loading) {
    return (
      <div className="space-y-4">
        <div className="animate-pulse space-y-4">
          <div className="h-32 bg-gray-200 rounded"></div>
          <div className="h-32 bg-gray-200 rounded"></div>
        </div>
        <div className="text-center text-gray-600 mt-4">
          <p className="mb-2">Analyzing your conversation patterns...</p>
          <p className="text-sm text-gray-500">
            {isForceRefresh ? 
              'Generating comprehensive insights (may take up to 45 seconds)' : 
              'Loading fast insights (usually 5-10 seconds)'
            }
          </p>
          {hasTimedOut && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
              <p className="text-yellow-800 text-sm">
                Analysis is taking longer than expected. You can wait or try refreshing.
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Error state - but preserve insights if we have them
  if (error && !insights) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <div className="flex items-start">
          <div className="flex-shrink-0">
            <div className="text-red-400">⚠️</div>
          </div>
          <div className="ml-3 flex-1">
            <h3 className="text-sm font-medium text-red-800">
              Unable to Load Insights
            </h3>
            <p className="mt-1 text-sm text-red-700">{error}</p>
            <div className="mt-4">
              <button
                onClick={() => fetchInsights(true)}
                disabled={refreshing}
                className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500 disabled:opacity-50"
              >
                {refreshing ? 'Retrying...' : 'Try Again'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Show error banner but keep insights visible
  if (error && insights) {
    return (
      <div className="space-y-4">
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
          <p className="text-yellow-800 text-sm">
            ⚠️ Unable to refresh insights: {error}
          </p>
        </div>
        {/* Render insights below */}
        {renderInsightsContent()}
      </div>
    );
  }

  // No insights but no error - show friendly message
  if (!insights || !insights.insights || insights.insights.length === 0) {
    return (
      <div className="text-center py-8">
        <div className="text-4xl mb-4">🔍</div>
        <h3 className="text-lg font-semibold text-gray-700 mb-2">No Insights Available Yet</h3>
        <p className="text-gray-600 mb-4">
          You need more conversation feedback data to generate AI insights. Have a few more conversations 
          and come back to see personalized analysis of your learning patterns.
        </p>
        <div className="text-sm text-gray-500 mb-4">
          <p>• Minimum: 5-10 conversations with feedback</p>
          <p>• Better insights: 20+ conversations over several days</p>
        </div>
        <button
          onClick={() => fetchInsights(true)}
          disabled={refreshing}
          className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors disabled:opacity-50"
        >
          {refreshing ? 'Checking...' : 'Check for Insights'}
        </button>
      </div>
    );
  }

  function renderInsightsContent() {
    return (
      <div className="space-y-4">
        {/* Summary */}
        <div className="bg-orange-50 border border-orange-200 rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-orange-800">Analysis Summary</h3>
            <div className="flex items-center gap-2">
              <button
                onClick={() => fetchInsights(true)}
                disabled={refreshing}
                className="text-xs text-orange-600 bg-orange-200 hover:bg-orange-300 px-2 py-1 rounded transition-colors disabled:opacity-50"
                title="Refresh insights with latest data"
              >
                {refreshing ? '🔄 Refreshing...' : '🔄 Refresh'}
              </button>
              <div className="text-xs text-orange-600 bg-orange-200 px-2 py-1 rounded">
                Updated: {new Date(insights.last_updated).toLocaleDateString()}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-2xl font-bold text-orange-600">{insights.summary.total_conversations}</div>
              <div className="text-orange-700">Conversations Analyzed</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-600">{insights.summary.total_patterns}</div>
              <div className="text-orange-700">Patterns Identified</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-orange-600">{insights.analysis_period}</div>
              <div className="text-orange-700">Analysis Period</div>
            </div>
          </div>
        </div>

        {/* Insights Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {insights.insights.map((insight: any) => (
            <div
              key={insight.id}
              className={`border rounded-lg transition-all duration-200 hover:shadow-md overflow-hidden ${
                insight.severity === 'high' ? 'border-red-200 bg-red-50' :
                insight.severity === 'moderate' ? 'border-orange-200 bg-orange-50' :
                'border-green-200 bg-green-50'
              }`}
            >
              {/* Content Area */}
              <div className="p-4">
                <p className="text-gray-800 font-medium">{insight.message}</p>
              </div>
              
              {/* Bottom: Action Button */}
              <div className={`px-4 h-14 flex items-center justify-end border-t ${
                insight.severity === 'high' ? 'border-red-200 bg-red-50' :
                insight.severity === 'moderate' ? 'border-orange-200 bg-orange-50' :
                'border-green-200 bg-green-50'
              }`}>
                <button
                  onClick={() => handlePracticeNow(insight)}
                  className="px-3 py-1.5 text-xs rounded-lg font-semibold shadow transition-colors bg-transparent border-2 border-orange-300 text-orange-800 hover:border-orange-400 hover:bg-orange-50"
                >
                  🎯 Practice Now
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <>
      {renderInsightsContent()}
      
      {/* Lesson Preview Modal */}
      <Transition.Root show={showLessonModal} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setShowLessonModal(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300"
            enterFrom="opacity-0"
            enterTo="opacity-100"
            leave="ease-in duration-200"
            leaveFrom="opacity-100"
            leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-30 transition-opacity" />
          </Transition.Child>

          <div className="fixed inset-0 z-10 overflow-y-auto">
            <div className="flex min-h-full items-end justify-center p-4 text-center sm:items-center sm:p-0">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300"
                enterFrom="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
                enterTo="opacity-100 translate-y-0 sm:scale-100"
                leave="ease-in duration-200"
                leaveFrom="opacity-100 translate-y-0 sm:scale-100"
                leaveTo="opacity-0 translate-y-4 sm:translate-y-0 sm:scale-95"
              >
                <Dialog.Panel className="relative transform overflow-hidden rounded-lg bg-white px-4 pb-4 pt-5 text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg sm:p-6">
                  <div className="absolute right-0 top-0 hidden pr-4 pt-4 sm:block">
                    <button
                      type="button"
                      className="rounded-md bg-white text-gray-400 hover:text-gray-500"
                      onClick={() => setShowLessonModal(false)}
                    >
                      <XMarkIcon className="h-6 w-6" />
                    </button>
                  </div>
                  
                  <div className="sm:flex sm:items-start">
                    <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                      <Dialog.Title as="h3" className="text-lg font-semibold leading-6 text-gray-900 mb-4">
                        Practice Lesson Preview
                      </Dialog.Title>
                      
                      {generatingLesson ? (
                        <div className="text-center py-8">
                          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-500 mx-auto mb-4"></div>
                          <p className="text-gray-600">Generating targeted lesson...</p>
                        </div>
                      ) : lessonPreview ? (
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-semibold text-gray-900">{lessonPreview.title}</h4>
                            <p className="text-sm text-gray-600 mt-1">Difficulty: {lessonPreview.difficulty}</p>
                          </div>
                          
                          <div>
                            <h5 className="font-medium text-gray-900">Objectives:</h5>
                            <p className="text-sm text-gray-700 mt-1">{lessonPreview.objectives}</p>
                          </div>
                          
                          <div>
                            <h5 className="font-medium text-gray-900">Content:</h5>
                            <p className="text-sm text-gray-700 mt-1">{lessonPreview.content}</p>
                          </div>
                          
                          {lessonPreview.cultural_element && (
                            <div>
                              <h5 className="font-medium text-gray-900">Cultural Context:</h5>
                              <p className="text-sm text-gray-700 mt-1">{lessonPreview.cultural_element}</p>
                            </div>
                          )}
                        </div>
                      ) : (
                        <p className="text-gray-500">Failed to generate lesson. Please try again.</p>
                      )}
                    </div>
                  </div>
                  
                  {lessonPreview && !generatingLesson && (
                    <div className="mt-5 sm:mt-4 sm:flex sm:flex-row-reverse">
                      <button
                        type="button"
                        className="inline-flex w-full justify-center rounded-md bg-orange-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-orange-500 sm:ml-3 sm:w-auto"
                        onClick={handleCreateLesson}
                      >
                        Create & Practice
                      </button>
                      <button
                        type="button"
                        className="mt-3 inline-flex w-full justify-center rounded-md bg-white px-3 py-2 text-sm font-semibold text-gray-900 shadow-sm ring-1 ring-inset ring-gray-300 hover:bg-gray-50 sm:mt-0 sm:w-auto"
                        onClick={() => setShowLessonModal(false)}
                      >
                        Cancel
                      </button>
                    </div>
                  )}
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>
    </>
  );
};

const Dashboard = () => {
  const [curriculums, setCurriculums] = useState<Curriculum[]>([]);
  const [selectedCurriculum, setSelectedCurriculum] = useState<Curriculum | null>(null);
  const [lessons, setLessons] = useState<LessonPreview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newLang, setNewLang] = useState('en');
  const [newLevel, setNewLevel] = useState('A1');
  const [adding, setAdding] = useState(false);
  const [showDeleteId, setShowDeleteId] = useState<string | null>(null);
  const [deleteConfirmChecked, setDeleteConfirmChecked] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [lessonTemplates, setLessonTemplates] = useState<LessonTemplatePreview[]>([]);
  const [feedbackLoading, setFeedbackLoading] = useState(true);
  const [filteredFeedbacks, setFilteredFeedbacks] = useState<Feedback[]>([]);
  const [feedbackError, setFeedbackError] = useState<string | null>(null);
  const [showContextModal, setShowContextModal] = useState(false);
  const [contextLoading, setContextLoading] = useState(false);
  const [personalizedContexts, setPersonalizedContexts] = useState<PersonalizedContext[]>([]);
  const [personalizedContextsLoading, setPersonalizedContextsLoading] = useState(false);
  const [userHasInterests, setUserHasInterests] = useState<boolean | null>(null);
  const [contextGenerationInProgress, setContextGenerationInProgress] = useState(false);
  const [lessonProgress, setLessonProgress] = useState<Record<string, any>>({});
  const [showLessonSummary, setShowLessonSummary] = useState(false);
  const [lessonSummaryData, setLessonSummaryData] = useState<LessonSummaryData | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingSummaryMap, setLoadingSummaryMap] = useState<Record<string, boolean>>({});
  const [showCompletedLessons, setShowCompletedLessons] = useState(true);
  const [displayedLessonsCount, setDisplayedLessonsCount] = useState(10);
  const [knowledgeRefreshKey, setKnowledgeRefreshKey] = useState(0);

  const [insights, setInsights] = useState(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const router = useRouter();

  const user = useUser();
  const { addToast } = useToast();

  // Function to get personalized greeting based on time of day
  const getPersonalizedGreeting = () => {
    const hour = new Date().getHours();
    let timeOfDay = '';
    
    if (hour >= 5 && hour < 12) {
      timeOfDay = 'Morning';
    } else if (hour >= 12 && hour < 17) {
      timeOfDay = 'Afternoon';
    } else if (hour >= 17 && hour < 22) {
      timeOfDay = 'Evening';
    } else {
      timeOfDay = 'Night';
    }
    
    const firstName = user?.user_metadata?.full_name?.split(' ')[0] || user?.email?.split('@')[0] || 'there';
    return `Good ${timeOfDay}, ${firstName}!`;
  };

  // Auto-refresh knowledge data when returning to dashboard
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && selectedCurriculum) {
        // Trigger refresh of knowledge panel when user returns to dashboard
        setKnowledgeRefreshKey(prev => prev + 1);
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [selectedCurriculum]);

  // Fetch JWT token on mount
  useEffect(() => {
    const fetchToken = async () => {
      setAuthLoading(true);
      const { data: { session } } = await supabase.auth.getSession();
      if (!session) {
        setToken(null);
        setAuthLoading(false);
        return;
      }
      setToken(session.access_token);
      setAuthLoading(false);
    };
    fetchToken();
  }, [user]); // Re-run when user authentication state changes

  // Fetch curriculums when token is available
  useEffect(() => {
    if (token) fetchCurriculums();
  }, [token]);

  async function fetchCurriculums() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/curriculums?token=${token}`);
      if (!res.ok) throw new Error('Failed to fetch curriculums');
      const data: Curriculum[] = await res.json();
      setCurriculums(data);
      if (data.length > 0) setSelectedCurriculum(data[0]);
      else setSelectedCurriculum(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // Fetch lessons for selected curriculum
  useEffect(() => {
    if (selectedCurriculum && token) fetchLessons(selectedCurriculum.id);
    else setLessons([]);
  }, [selectedCurriculum, token]);

  async function fetchLessons(curriculumId: string) {
    // Don't show loading for lessons since it's quick
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/curriculums/${curriculumId}/lessons?token=${token}`);
      if (!res.ok) throw new Error('Failed to fetch lessons');
      const data: LessonPreview[] = await res.json();
      setLessons(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  // Fetch lesson templates for selected curriculum's language
  useEffect(() => {
    async function fetchLessonTemplates(language: string) {
      // Only show loading state while fetching lesson templates, not other data
      setError(null);
      try {
        if (selectedCurriculum && token) {
          // Use the efficient batch endpoint that gets lessons with progress in one call
          const res = await fetch(
            `${API_BASE}/api/curriculums/${selectedCurriculum.id}/lessons_with_progress?language=${language}&token=${token}`
          );
          if (!res.ok) throw new Error('Failed to fetch lessons with progress');
          const data: LessonTemplatePreview[] = await res.json();
          
          // Create progress map for state
          const progressMap: Record<string, any> = {};
          data.forEach(lesson => {
            if (lesson.progress) {
              progressMap[lesson.id] = lesson.progress;
            }
          });
          
          setLessonProgress(progressMap);
          setLessonTemplates(data);
        } else {
          // Fallback to basic lesson templates without progress
          const res = await fetch(`${API_BASE}/api/lesson_templates?language=${language}`);
          if (!res.ok) throw new Error('Failed to fetch lesson templates');
          const data: LessonTemplatePreview[] = await res.json();
          setLessonTemplates(data);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }
    if (selectedCurriculum) {
      fetchLessonTemplates(selectedCurriculum.language);
    } else {
      setLessonTemplates([]);
    }
  }, [selectedCurriculum?.id, selectedCurriculum?.language, token]);

  const handleCurriculumChange = (id: string) => {
    const found = curriculums.find(c => c.id === id);
    if (found) {
      setSelectedCurriculum(found);
      setDisplayedLessonsCount(10); // Reset to show first 10 lessons
    }
  };

  const handleAddLanguage = () => {
    router.push('/curriculum'); // Go to curriculum creation page
  };

  const handleStartLesson = async (lessonId: string) => {
    if (!selectedCurriculum) return;
    console.log('handleStartLesson', { lessonId, selectedCurriculum }); // Debug log
    try {
      const res = await fetch(`${API_BASE}/api/start_lesson_conversation?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lesson_template_id: String(lessonId), curriculum_id: selectedCurriculum.id })
      });
      if (!res.ok) throw new Error('Failed to start lesson conversation');
      const data = await res.json();
      router.push(`/chat?conversation=${data.conversation_id}&curriculum_id=${selectedCurriculum.id}`);
    } catch (e) {
      addToast(e instanceof Error ? e.message : String(e), 'error');
    }
  };

  const handleStartConversation = () => {
    setShowContextModal(true);
    checkUserInterestsAndLoadContexts();
  };

  const checkUserInterestsAndLoadContexts = async () => {
    if (!token) {
      console.log('No token available for checking interests');
      return;
    }
    
    try {
      setPersonalizedContextsLoading(true);
      console.log('🔍 Checking user interests...');
      
      // Check if user has interests
      const interestsResponse = await fetch(`${API_BASE}/api/user_interests?token=${token}`);
      console.log('📊 Interests response status:', interestsResponse.status);
      
      if (interestsResponse.ok) {
        const interestsData = await interestsResponse.json();
        console.log('📊 Interests data:', interestsData);
        
        const hasInterests = Object.keys(interestsData.interests || {}).length > 0;
        console.log('📊 User has interests:', hasInterests);
        setUserHasInterests(hasInterests);
        
        if (hasInterests) {
          console.log('🎯 Loading personalized contexts...');
          // Load personalized contexts
          const contextsResponse = await fetch(`${API_BASE}/api/personalized_contexts?token=${token}`);
          console.log('🎯 Contexts response status:', contextsResponse.status);
          
          if (contextsResponse.ok) {
            const contextsData = await contextsResponse.json();
            console.log('🎯 Contexts data:', contextsData);
            setPersonalizedContexts(contextsData.contexts || []);
          } else {
            console.error('🎯 Failed to load contexts:', await contextsResponse.text());
          }
        }
      } else {
        console.error('📊 Failed to load interests:', await interestsResponse.text());
        setUserHasInterests(false);
      }
    } catch (error) {
      console.error('💥 Error checking user interests:', error);
      setUserHasInterests(false);
    } finally {
      setPersonalizedContextsLoading(false);
      console.log('✅ Finished checking interests and contexts');
    }
  };

  const generateMoreContexts = async () => {
    if (!token) return;
    
    try {
      setPersonalizedContextsLoading(true);
      const response = await fetch(`${API_BASE}/api/personalized_contexts/generate?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ count: 6 })
      });
      
      if (response.ok) {
        const data = await response.json();
        setPersonalizedContexts(prev => [...prev, ...data.contexts]);
      } else {
        const errorData = await response.json();
        console.error('Failed to generate more contexts:', errorData);
        addToast(errorData.detail || 'Failed to generate more contexts', 'error');
      }
    } catch (error) {
      console.error('Error generating more contexts:', error);
      addToast('Failed to generate more contexts', 'error');
    } finally {
      setPersonalizedContextsLoading(false);
    }
  };

  const handleContextSelect = async (contextId: string) => {
    if (!selectedCurriculum) return;
    setContextLoading(true);
    setShowContextModal(false);
    router.push(`/chat?language=${selectedCurriculum.language}&level=${selectedCurriculum.start_level}&context=${contextId}&curriculum_id=${selectedCurriculum.id}`);
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.refresh();
  };

  const handleViewReportCard = async (lessonId: string) => {
    if (!selectedCurriculum || !token) return;
    
    setLoadingSummaryMap(prev => ({ ...prev, [lessonId]: true }));
    setLoadingSummary(true);
    try {
      // Get the progress ID for this lesson
      const progress = lessonProgress[lessonId];
      if (!progress || !progress.id) {
        addToast('No progress found for this lesson', 'warning');
        return;
      }

      const encodedProgressId = encodeURIComponent(progress.id);
      const encodedToken = encodeURIComponent(token);
      
      const summaryUrl = `${API_BASE}/api/lesson_progress/${encodedProgressId}/summary?token=${encodedToken}`;
      console.log('[View Report Card] Summary URL:', summaryUrl);
      
      const summaryResponse = await fetch(summaryUrl);
      
      if (summaryResponse.ok) {
        const summaryData = await summaryResponse.json();
        console.log('[View Report Card] Fetched summary:', summaryData);
        setLessonSummaryData(summaryData);
        setShowLessonSummary(true);
      } else {
        const errorText = await summaryResponse.text();
        console.error('[View Report Card] Failed to fetch summary:', errorText);
        addToast('Failed to load report card. Please try again.', 'error');
      }
    } catch (error) {
      console.error('[View Report Card] Error:', error);
      addToast('Failed to load report card. Please try again.', 'error');
    } finally {
      setLoadingSummaryMap(prev => ({ ...prev, [lessonId]: false }));
      setLoadingSummary(false);
    }
  };

  const handleCloseLessonSummary = () => {
    setShowLessonSummary(false);
    setLessonSummaryData(null);
  };

  // Function to calculate current level based on completed lessons
  const getCurrentLevel = (curriculum: Curriculum) => {
    if (!selectedCurriculum || selectedCurriculum.id !== curriculum.id) {
      return curriculum.start_level; // Default to start level if not selected curriculum
    }
    
    // Get completed lessons for this curriculum
    const completedLessons = lessonTemplates.filter(lesson => {
      const progress = lesson.progress;
      return progress?.status === 'completed';
    });
    
    if (completedLessons.length === 0) {
      return curriculum.start_level; // No completed lessons, return start level
    }
    
    // Define level order for proper sorting
    const levelOrder = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
    
    // Find the highest level among completed lessons
    const completedLevels = completedLessons
      .map(lesson => lesson.level)
      .filter((level): level is string => level !== null && level !== undefined && levelOrder.includes(level)) // Remove null/undefined and invalid levels
      .sort((a, b) => levelOrder.indexOf(a) - levelOrder.indexOf(b)); // Sort by level order
    
    if (completedLevels.length === 0) {
      return curriculum.start_level; // No valid levels found
    }
    
    // Return the highest completed level
    return completedLevels[completedLevels.length - 1];
  };

  useEffect(() => {
    const fetchFeedback = async () => {
      setFeedbackLoading(true);
      setFeedbackError(null);
      try {
        const { data: { user } } = await supabaseClient.auth.getUser();
        if (!user || !selectedCurriculum) {
          setFilteredFeedbacks([]);
          return;
        }
        
        // Fetch feedback data filtered by the selected curriculum
        const { data, error } = await supabaseClient
          .from('message_feedback')
          .select(`
            *,
            messages!inner(
              conversation_id,
              conversations!inner(
                curriculum_id,
                language
              )
            )
          `)
          .eq('messages.conversations.curriculum_id', selectedCurriculum.id)
          .order('created_at', { ascending: false });
          
        if (error) throw error;
        setFilteredFeedbacks(data || []);
      } catch (error: any) {
        console.error('Error fetching feedback:', error);
        setFeedbackError(error.message || 'Failed to load analytics data.');
      } finally {
        setFeedbackLoading(false);
      }
    };
    
    fetchFeedback();
  }, [selectedCurriculum?.id]); // Add selectedCurriculum as dependency

  // Poll for context generation status
  const checkContextGenerationStatus = async () => {
    if (!token) return;
    
    try {
      const response = await fetch(`${API_BASE}/api/personalized_contexts/status?token=${token}`);
      if (response.ok) {
        const data = await response.json();
        setContextGenerationInProgress(data.is_generating);
        
        // If generation was in progress but now complete, refresh contexts
        if (contextGenerationInProgress && !data.is_generating) {
          console.log('🎯 Context generation completed, refreshing...');
          await checkUserInterestsAndLoadContexts();
        }
      }
    } catch (error) {
      console.error('Error checking context generation status:', error);
    }
  };

  // Poll context generation status every 2 seconds when modal is open
  useEffect(() => {
    let interval: NodeJS.Timeout;
    
    if (showContextModal && token) {
      // Check immediately when modal opens
      checkContextGenerationStatus();
      // Then check every 2 seconds
      interval = setInterval(checkContextGenerationStatus, 2000);
    }
    
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [showContextModal, token, contextGenerationInProgress]);

  if (authLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 to-orange-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }
  if (!user || !token) {
    return <Auth />;
  }

  return (
    <div className="relative max-w-6xl mx-auto p-6 min-h-screen">
      {/* Personalized Greeting */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">
          {getPersonalizedGreeting()}
        </h1>
        <p className="text-gray-600">
          Ready to continue your language learning journey?
        </p>
      </div>

      {/* Practice Now + Language Paths (side by side on desktop) */}
      <div className="w-full flex flex-col lg:flex-row items-start justify-center mb-12 gap-6">
        {/* Scrollable container for both columns */}
        <div className={`hidden lg:flex w-full max-w-4xl ${
          Math.max(curriculums.filter((_, i) => i % 2 === 0).length, curriculums.filter((_, i) => i % 2 === 1).length) >= 3 
            ? 'max-h-[320px] overflow-y-auto scrollbar-thin scrollbar-thumb-orange-300 scrollbar-track-orange-100' 
            : ''
        }`}>
          <div className="flex w-full gap-6">
            {/* Language Paths - Left */}
            <div className="flex flex-col items-end flex-1 min-w-0 max-w-sm">
              <div className="flex flex-col w-full">
                <div className="flex flex-col gap-4 pr-2">
                  {curriculums.filter((_, i) => i % 2 === 0).map(c => (
                    <div
                      key={c.id}
                      className={`relative w-full max-w-[260px] rounded-xl bg-white/60 backdrop-blur-md shadow-xl p-4 cursor-pointer border-2 transition-all duration-200 ${selectedCurriculum && c.id === selectedCurriculum.id ? 'border-orange-500 scale-102 ring-4 ring-orange-100' : 'border-transparent hover:border-orange-300 hover:scale-101'} group ml-auto`}
                      onClick={() => handleCurriculumChange(c.id)}
                      style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.10)' }}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="text-xl font-bold text-gray-800">
                          {languages.find(l => l.code === c.language)?.name || c.language}
                        </div>
                        <div className="flex items-center gap-1 overflow-hidden">
                          <div className="flex -space-x-1">
                            {(languages.find(l => l.code === c.language)?.countryFlags || ['🏳️']).slice(0, 3).map((flag, idx) => (
                              <span key={idx} className="text-lg block w-6 h-6 flex items-center justify-center bg-white rounded-full border border-gray-200 shadow-sm">
                                {flag}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-end justify-between">
                        <div className="space-y-1">
                          <div className="text-xs text-gray-600">Start Level: <span className="font-semibold text-gray-800">{c.start_level}</span></div>
                          <div className="text-xs text-gray-600">Start Date: <span className="font-semibold text-gray-800">{c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Unknown'}</span></div>
                          <div className="text-xs text-gray-600">Current Level: <span className="font-semibold text-gray-800">{getCurrentLevel(c)}</span></div>
                        </div>
                        {/* Delete button - aligned with Current Level */}
                        <button
                          className="bg-white shadow-lg rounded-full p-1 z-20 border-2 border-red-200 hover:bg-red-500 hover:text-white transition-colors duration-200 group-hover:scale-105 focus:outline-none"
                          title="Remove this learning path"
                          onClick={e => { e.stopPropagation(); setShowDeleteId(c.id); setDeleteConfirmChecked(false); }}
                          style={{ boxShadow: '0 4px 16px 0 rgba(255,0,0,0.10)' }}
                        >
                          <TrashIcon className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            
            {/* Microphone Button Centered */}
            <div className="flex flex-col items-center flex-shrink-0 z-10 mt-8">
              <div
                className="bg-white rounded-2xl shadow-lg border border-orange-200 p-8 cursor-pointer hover:shadow-xl hover:scale-105 transition-all duration-200 focus-within:ring-4 focus-within:ring-orange-200 group"
                style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.12)' }}
                onClick={handleStartConversation}
              >
                <div className="flex flex-col items-center">
                  {/* Microphone Icon */}
                  <div className="relative mb-4">
                    {/* Microphone body */}
                    <div className="bg-gradient-to-b from-orange-400 to-orange-600 rounded-full w-12 h-16 relative group-hover:scale-110 transition-transform duration-200 shadow-lg">
                      {/* Microphone grille lines */}
                      <div className="absolute inset-x-0 top-3 space-y-1 px-3">
                        <div className="h-0.5 bg-white/30 rounded"></div>
                        <div className="h-0.5 bg-white/30 rounded"></div>
                        <div className="h-0.5 bg-white/30 rounded"></div>
                      </div>
                      {/* Microphone highlight */}
                      <div className="absolute top-2 left-2 w-2.5 h-4 bg-white/20 rounded-full"></div>
                    </div>
                    {/* Microphone stand */}
                    <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 w-0.5 h-4 bg-gray-400 group-hover:scale-110 transition-transform duration-200"></div>
                    {/* Microphone base */}
                    <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 w-6 h-1.5 bg-gray-500 rounded-full group-hover:scale-110 transition-transform duration-200"></div>
                  </div>
                  <div className="text-center">
                    <h3 className="text-lg font-bold text-gray-800 mb-1">
                      Start Conversation
                    </h3>
                    <p className="text-sm text-gray-600">
                      Practice speaking with AI
                    </p>
                  </div>
                </div>
              </div>
              {/* Add Language Path Button - moved under mic */}
              <div className="flex items-center mt-6 gap-2">
                <button
                  className="bg-orange-500 hover:bg-orange-600 text-white rounded-full shadow-lg p-2 transition-transform duration-200 hover:scale-110 focus:outline-none focus:ring-4 focus:ring-orange-300"
                  title="Add Language Path"
                  onClick={() => setShowAdd(v => !v)}
                  style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.10)' }}
                >
                  <PlusIcon className="h-4 w-4" />
                </button>
                <span className="text-sm text-gray-700 font-medium select-none">Add Language Path</span>
              </div>
            </div>
            
            {/* Language Paths - Right */}
            <div className="flex flex-col items-start flex-1 min-w-0 max-w-sm">
              <div className="flex flex-col w-full">
                <div className="flex flex-col gap-4 pl-2">
                  {curriculums.filter((_, i) => i % 2 === 1).map(c => (
                    <div
                      key={c.id}
                      className={`relative w-full max-w-[260px] rounded-xl bg-white/60 backdrop-blur-md shadow-xl p-4 cursor-pointer border-2 transition-all duration-200 ${selectedCurriculum && c.id === selectedCurriculum.id ? 'border-orange-500 scale-102 ring-4 ring-orange-100' : 'border-transparent hover:border-orange-300 hover:scale-101'} group`}
                      onClick={() => handleCurriculumChange(c.id)}
                      style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.10)' }}
                    >
                      <div className="flex items-center justify-between mb-3">
                        <div className="text-xl font-bold text-gray-800">
                          {languages.find(l => l.code === c.language)?.name || c.language}
                        </div>
                        <div className="flex items-center gap-1 overflow-hidden">
                          <div className="flex -space-x-1">
                            {(languages.find(l => l.code === c.language)?.countryFlags || ['🏳️']).slice(0, 3).map((flag, idx) => (
                              <span key={idx} className="text-lg block w-6 h-6 flex items-center justify-center bg-white rounded-full border border-gray-200 shadow-sm">
                                {flag}
                              </span>
                            ))}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-end justify-between">
                        <div className="space-y-1">
                          <div className="text-xs text-gray-600">Start Level: <span className="font-semibold text-gray-800">{c.start_level}</span></div>
                          <div className="text-xs text-gray-600">Start Date: <span className="font-semibold text-gray-800">{c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Unknown'}</span></div>
                          <div className="text-xs text-gray-600">Current Level: <span className="font-semibold text-gray-800">{getCurrentLevel(c)}</span></div>
                        </div>
                        {/* Delete button - aligned with Current Level */}
                        <button
                          className="bg-white shadow-lg rounded-full p-1 z-20 border-2 border-red-200 hover:bg-red-500 hover:text-white transition-colors duration-200 group-hover:scale-105 focus:outline-none"
                          title="Remove this learning path"
                          onClick={e => { e.stopPropagation(); setShowDeleteId(c.id); setDeleteConfirmChecked(false); }}
                          style={{ boxShadow: '0 4px 16px 0 rgba(255,0,0,0.10)' }}
                        >
                          <TrashIcon className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
        
        {/* Mobile/Tablet: Language Paths below mic */}
        <div className="flex flex-col w-full lg:hidden mt-8">
          <div className="flex flex-col items-center flex-shrink-0 z-10 mb-8">
            <div
              className="bg-white rounded-2xl shadow-lg border border-orange-200 p-8 cursor-pointer hover:shadow-xl hover:scale-105 transition-all duration-200 focus-within:ring-4 focus-within:ring-orange-200 group"
              style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.12)' }}
              onClick={handleStartConversation}
            >
              <div className="flex flex-col items-center">
                {/* Microphone Icon */}
                <div className="relative mb-4">
                  {/* Microphone body */}
                  <div className="bg-gradient-to-b from-orange-400 to-orange-600 rounded-full w-12 h-16 relative group-hover:scale-110 transition-transform duration-200 shadow-lg">
                    {/* Microphone grille lines */}
                    <div className="absolute inset-x-0 top-3 space-y-1 px-3">
                      <div className="h-0.5 bg-white/30 rounded"></div>
                      <div className="h-0.5 bg-white/30 rounded"></div>
                      <div className="h-0.5 bg-white/30 rounded"></div>
                    </div>
                    {/* Microphone highlight */}
                    <div className="absolute top-2 left-2 w-2.5 h-4 bg-white/20 rounded-full"></div>
                  </div>
                  {/* Microphone stand */}
                  <div className="absolute -bottom-2 left-1/2 transform -translate-x-1/2 w-0.5 h-4 bg-gray-400 group-hover:scale-110 transition-transform duration-200"></div>
                  {/* Microphone base */}
                  <div className="absolute -bottom-4 left-1/2 transform -translate-x-1/2 w-6 h-1.5 bg-gray-500 rounded-full group-hover:scale-110 transition-transform duration-200"></div>
                </div>
                <div className="text-center">
                  <h3 className="text-lg font-bold text-gray-800 mb-1">
                    Start Conversation
                  </h3>
                  <p className="text-sm text-gray-600">
                    Practice speaking with AI
                  </p>
                </div>
              </div>
            </div>
            {/* Add Language Path Button - moved under mic */}
            <div className="flex items-center mt-6 gap-2">
              <button
                className="bg-orange-500 hover:bg-orange-600 text-white rounded-full shadow-lg p-2 transition-transform duration-200 hover:scale-110 focus:outline-none focus:ring-4 focus:ring-orange-300"
                title="Add Language Path"
                onClick={() => setShowAdd(v => !v)}
                style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.10)' }}
              >
                <PlusIcon className="h-4 w-4" />
              </button>
              <span className="text-sm text-gray-700 font-medium select-none">Add Language Path</span>
            </div>
          </div>
          <div className="px-6 py-2">
            <div className="flex space-x-4 overflow-x-auto pb-2 mb-4" style={{ WebkitOverflowScrolling: 'touch' }}>
              {curriculums.map(c => (
                <div
                  key={c.id}
                  className={`relative min-w-[220px] max-w-[260px] rounded-xl bg-white/60 backdrop-blur-md shadow-xl p-4 cursor-pointer border-2 transition-all duration-200 ${selectedCurriculum && c.id === selectedCurriculum.id ? 'border-orange-500 scale-102 ring-4 ring-orange-100' : 'border-transparent hover:border-orange-300 hover:scale-101'} group`}
                  onClick={() => handleCurriculumChange(c.id)}
                  style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.10)' }}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="text-xl font-bold text-gray-800">
                      {languages.find(l => l.code === c.language)?.name || c.language}
                    </div>
                    <div className="flex items-center gap-1 overflow-hidden">
                      <div className="flex -space-x-1">
                        {(languages.find(l => l.code === c.language)?.countryFlags || ['🏳️']).slice(0, 3).map((flag, idx) => (
                          <span key={idx} className="text-lg block w-6 h-6 flex items-center justify-center bg-white rounded-full border border-gray-200 shadow-sm">
                            {flag}
                          </span>
                        ))}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-end justify-between">
                    <div className="space-y-1">
                      <div className="text-xs text-gray-600">Start Level: <span className="font-semibold text-gray-800">{c.start_level}</span></div>
                      <div className="text-xs text-gray-600">Start Date: <span className="font-semibold text-gray-800">{c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Unknown'}</span></div>
                      <div className="text-xs text-gray-600">Current Level: <span className="font-semibold text-gray-800">{getCurrentLevel(c)}</span></div>
                    </div>
                    {/* Delete button - aligned with Current Level */}
                    <button
                      className="bg-white shadow-lg rounded-full p-1 z-20 border-2 border-red-200 hover:bg-red-500 hover:text-white transition-colors duration-200 group-hover:scale-105 focus:outline-none"
                      title="Remove this learning path"
                      onClick={e => { e.stopPropagation(); setShowDeleteId(c.id); setDeleteConfirmChecked(false); }}
                      style={{ boxShadow: '0 4px 16px 0 rgba(255,0,0,0.10)' }}
                    >
                      <TrashIcon className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
      {/* Section Divider */}
      <div className="section-divider"></div>

      {/* Curriculum Path Tiles (for selected curriculum) */}
      <div className="mb-12">
        <h2 className="retro-header text-3xl font-extrabold text-center mb-6">
          Curriculum
        </h2>
        <div className="px-10">
          {(() => {
            // Get ALL completed lessons (not limited)
            const allCompletedLessons = lessonTemplates.filter(lesson => {
              const progress = lesson.progress;
              return progress?.status === 'completed';
            });
            
            // Get all active lessons (not started + in progress)
            const allActiveLessons = lessonTemplates.filter(lesson => {
              const progress = lesson.progress;
              return progress?.status !== 'completed';
            });
            
            // Limit active lessons to displayedLessonsCount for display
            const displayedActiveLessons = allActiveLessons.slice(0, displayedLessonsCount);

            const renderLessonCard = (lesson: any, isCompact = false) => {
              const progress = lesson.progress;
              const isCompleted = progress?.status === 'completed';
              const isInProgress = progress?.status === 'in_progress';
              const progressPercentage = progress ? Math.min((progress.turns_completed / progress.required_turns) * 100, 100) : 0;
              
              return (
                <div
                  key={lesson.id}
                  className={`flex flex-col justify-between ${isCompact ? 'min-w-[260px] max-w-[280px]' : 'min-w-[320px] max-w-[340px]'} bg-white rounded-2xl shadow-lg border p-0 overflow-hidden ${
                    isCompleted ? 'border-gray-300' : isInProgress ? 'border-orange-200' : 'border-gray-100'
                  }`}
                  style={{ boxShadow: '0 4px 24px 0 rgba(255,140,0,0.08)' }}
                >
                  {/* Progress Status Badge */}
                  {progress && (
                    <div className={`${isCompact ? 'px-4 pt-2' : 'px-5 pt-3'}`}>
                      <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        isCompleted 
                          ? 'bg-gray-100 text-gray-800' 
                          : isInProgress 
                            ? 'bg-orange-100 text-orange-800' 
                            : 'bg-gray-100 text-gray-800'
                      }`}>
                        {isCompleted ? '✅ Completed' : isInProgress ? '🔄 In Progress' : '⭕ Not Started'}
                      </div>
                    </div>
                  )}
                  
                  {/* Top: Level & Difficulty */}
                  <div className={`${isCompact ? 'px-4 pt-3 pb-1' : 'px-5 pt-4 pb-1'}`}>
                    <div className="text-xs text-gray-500 font-semibold mb-1">
                      Level: {lesson.level || 'N/A'} &bull; Difficulty: {lesson.difficulty || 'N/A'}
                    </div>
                    {/* Title */}
                    <div className={`${isCompact ? 'text-lg' : 'text-xl'} font-bold text-gray-900 mb-2`}>
                      {lesson.title}
                    </div>
                  </div>
                  
                  {/* Progress Bar (if in progress) */}
                  {progress && isInProgress && (
                    <div className={`${isCompact ? 'px-4 pb-2' : 'px-5 pb-2'}`}>
                      <div className="w-full bg-gray-200 rounded-full h-2 mb-1">
                        <div 
                          className="bg-orange-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${progressPercentage}%` }}
                        />
                      </div>
                      <div className="text-xs text-gray-600">
                        {progress.turns_completed}/{progress.required_turns} conversation turns
                      </div>
                    </div>
                  )}
                  
                  {/* Description */}
                  {!isCompact && (
                    <div className="px-5 pb-4 text-sm text-gray-700 flex-1">
                      {lesson.objectives || <span className="italic text-gray-400">No description</span>}
                    </div>
                  )}
                  
                  {/* Bottom: Action Buttons */}
                  <div className={`${isCompact ? 'px-4 h-14' : 'px-5 h-16'} flex items-center justify-end border-t border-gray-100 bg-gray-50 gap-2`}>
                    {isCompleted && (
                      <button
                        className={`${isCompact ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'} rounded-lg font-semibold shadow transition-colors bg-orange-300 hover:bg-orange-400 text-orange-800`}
                        onClick={() => handleViewReportCard(lesson.id)}
                        disabled={loadingSummaryMap[lesson.id]}
                      >
                        {loadingSummaryMap[lesson.id] ? 'Loading...' : '📊 Report Card'}
                      </button>
                    )}
                    {!isCompleted && (
                      <button
                        className={`${isCompact ? 'px-4 py-1.5 text-xs' : 'px-5 py-2 text-sm'} rounded-lg font-semibold shadow transition-colors bg-orange-500 hover:bg-orange-600 text-white`}
                        onClick={() => handleStartLesson(lesson.id)}
                      >
                        {isInProgress ? 'Continue Lesson' : 'Start Lesson'}
                      </button>
                    )}
                  </div>
                </div>
              );
            };

            return (
              <>
                {/* Active Lessons (In Progress + Not Started) */}
                {(displayedActiveLessons.length > 0 || allActiveLessons.length > displayedLessonsCount) && (
                  <div className="mb-8">
                    <div className="flex space-x-6 overflow-x-auto pb-2 mb-4" style={{ WebkitOverflowScrolling: 'touch' }}>
                      {displayedActiveLessons.map(lesson => renderLessonCard(lesson, false))}
                      
                      {/* Load More Card - appears inline with lesson cards */}
                      {allActiveLessons.length > displayedLessonsCount && (
                        <div
                          className="flex flex-col justify-center items-center min-w-[320px] max-w-[340px] bg-gradient-to-br from-orange-50 to-orange-100 rounded-2xl shadow-lg border-2 border-dashed border-orange-300 p-8 cursor-pointer hover:border-orange-500 hover:bg-gradient-to-br hover:from-orange-100 hover:to-orange-200 transition-all duration-200 group"
                          style={{ boxShadow: '0 4px 24px 0 rgba(255,140,0,0.08)' }}
                          onClick={() => setDisplayedLessonsCount(prev => prev + 10)}
                        >
                          <div className="bg-orange-500 text-white rounded-full p-4 mb-4 group-hover:scale-110 transition-transform duration-200">
                            <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M12 4v16m8-8H4" />
                            </svg>
                          </div>
                          <div className="text-center">
                            <div className="text-lg font-bold text-orange-800 mb-2">Load More Lessons</div>
                            <div className="text-sm text-orange-600">
                              {allActiveLessons.length - displayedLessonsCount} more lessons available
                            </div>
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                )}
                
                {/* Completed Lessons - Collapsible Section */}
                {allCompletedLessons.length > 0 && (
                  <div className="mb-4">
                    <button
                      onClick={() => setShowCompletedLessons(!showCompletedLessons)}
                      className="w-full mb-4 p-4 bg-orange-50 hover:bg-orange-100 border-2 border-orange-200 rounded-xl transition-colors duration-200 focus:outline-none focus:ring-4 focus:ring-orange-100"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-left">
                            <h3 className="text-lg font-bold text-orange-800">
                              Completed Lessons ({allCompletedLessons.length})
                            </h3>
                            <p className="text-sm text-orange-600">
                              Great job! Click to view your completed lessons
                            </p>
                          </div>
                        </div>
                        <div className={`transform transition-transform duration-200 ${showCompletedLessons ? 'rotate-180' : ''}`}>
                          <svg className="w-6 h-6 text-orange-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>
                    </button>
                    
                    {/* Expanded Completed Lessons */}
                    {showCompletedLessons && (
                      <div className="flex space-x-4 overflow-x-auto pb-2 bg-gray-50 rounded-xl p-4 border border-gray-200" style={{ WebkitOverflowScrolling: 'touch' }}>
                        {allCompletedLessons.map(lesson => renderLessonCard(lesson, true))}
                      </div>
                    )}
                  </div>
                )}
                

                
                {/* Empty State */}
                {lessonTemplates.length === 0 && !loading && (
                  <div className="text-gray-400 text-center py-8">No lessons found for this curriculum.</div>
                )}
              </>
            );
          })()}
        </div>
      </div>

      {/* Section Divider */}
      <div className="section-divider"></div>

      {/* User Progress Analytics */}
      {selectedCurriculum && (
        <ProgressSection 
          selectedCurriculum={selectedCurriculum}
          feedbackLoading={feedbackLoading}
          feedbackError={feedbackError}
          filteredFeedbacks={filteredFeedbacks}
          knowledgeRefreshKey={knowledgeRefreshKey}
          token={token}
        />
      )}

      {/* Add Curriculum Modal */}
      <Transition.Root show={showAdd} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setShowAdd(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100"
            leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-30 transition-opacity" />
          </Transition.Child>
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100"
                leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-8 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title as="h3" className="text-2xl font-bold mb-4 text-orange-600 text-center">
                    Add a New Language Path
                  </Dialog.Title>
                  <form className="flex flex-col gap-6" onSubmit={async e => {
                    e.preventDefault();
                    setAdding(true);
                    setError(null);
                    try {
                      const res = await fetch(`${API_BASE}/api/curriculums?token=${token}`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ language: newLang, start_level: newLevel })
                      });
                      if (!res.ok) throw new Error('Failed to add curriculum');
                      setShowAdd(false);
                      setNewLang('en');
                      setNewLevel('A1');
                      await fetchCurriculums();
                    } catch (e) {
                      setError(e instanceof Error ? e.message : String(e));
                    } finally {
                      setAdding(false);
                    }
                  }}>
                    <div>
                      <label className="block text-xs font-medium mb-2">Language</label>
                      <div className="grid grid-cols-3 gap-3">
                        {languagesList.filter(l => !curriculums.some(c => c.language === l.code)).map(l => (
                          <button
                            type="button"
                            key={l.code}
                            className={`flex flex-col items-center justify-center rounded-xl border-2 p-3 transition-all duration-150 cursor-pointer focus:outline-none ${newLang === l.code ? 'border-orange-500 bg-orange-50 ring-2 ring-orange-200' : 'border-gray-200 bg-gray-50 hover:border-orange-300'}`}
                            onClick={() => setNewLang(l.code)}
                            disabled={adding}
                          >
                            <span className="text-2xl mb-1">{languages.find(lang => lang.code === l.code)?.countryFlags[0] || '🏳️'}</span>
                            <span className="font-semibold text-sm">{l.name}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium mb-2">Starting Level</label>
                      <div className="flex gap-2 flex-wrap">
                        {levels.map(l => (
                          <button
                            type="button"
                            key={l}
                            className={`px-4 py-2 rounded-xl border-2 font-semibold text-sm transition-all duration-150 cursor-pointer focus:outline-none ${newLevel === l ? 'border-orange-500 bg-orange-50 ring-2 ring-orange-200' : 'border-gray-200 bg-gray-50 hover:border-orange-300'}`}
                            onClick={() => setNewLevel(l)}
                            disabled={adding}
                          >
                            {l}
                          </button>
                        ))}
                      </div>
                    </div>
                    {error && <div className="text-red-500 text-sm text-center">{error}</div>}
                    <div className="flex gap-3 justify-center mt-2">
                      <button
                        type="button"
                        className="px-4 py-2 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
                        onClick={() => setShowAdd(false)}
                        disabled={adding}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="px-6 py-2 bg-orange-500 text-white rounded-full font-semibold shadow hover:bg-orange-600 disabled:opacity-50"
                        disabled={adding || !newLang}
                      >
                        {adding ? 'Adding...' : 'Add'}
              </button>
                    </div>
                  </form>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>

      {/* Context Selection Modal for Conversation */}
      <Transition.Root show={showContextModal} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setShowContextModal(false)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100"
            leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-30 transition-opacity" />
          </Transition.Child>
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100"
                leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-5xl transform overflow-hidden rounded-2xl bg-white p-6 sm:p-8 text-left align-middle shadow-xl transition-all mx-4">
                  <Dialog.Title as="h3" className="text-2xl font-bold mb-6 text-orange-600 text-center">
                    Choose a Conversation Context
                  </Dialog.Title>
                  
                  {/* Check if user has no interests */}
                  {userHasInterests === false && (
                    <div className="text-center py-8 bg-orange-50 rounded-lg mb-6">
                      <div className="text-4xl mb-4">🎯</div>
                      <h4 className="text-lg font-semibold text-orange-700 mb-2">
                        Get Personalized Conversation Topics!
                      </h4>
                      <p className="text-gray-600 mb-4">
                        Visit your profile to set your interests and unlock personalized conversation scenarios.
                      </p>
                      <button
                        onClick={() => {
                          setShowContextModal(false);
                          router.push('/profile');
                        }}
                        className="px-6 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors"
                      >
                        Set Your Interests
                      </button>
                    </div>
                  )}

                  {/* Loading state for contexts being generated */}
                  {userHasInterests === true && (personalizedContextsLoading || contextGenerationInProgress) && personalizedContexts.length === 0 && (
                    <div className="flex gap-6">
                      {/* Mini Sidebar - maintain structure */}
                      <div className="w-32 flex-shrink-0">
                        <div className="sticky top-0 space-y-2">
                          <div className="w-full text-left px-3 py-2 rounded-lg bg-purple-50 border border-purple-200">
                            <div className="flex items-center gap-2">
                              <span className="text-sm">✨</span>
                              <div>
                                <div className="font-medium text-sm text-purple-700">For You</div>
                              </div>
                            </div>
                          </div>
                          
                          <div className="w-full text-left px-3 py-2 rounded-lg bg-orange-50 border border-orange-200">
                            <div className="flex items-center gap-2">
                              <span className="text-sm">🎭</span>
                              <div>
                                <div className="font-medium text-sm text-orange-700">Classic</div>
                              </div>
                            </div>
                          </div>
                        </div>
                      </div>

                      {/* Loading Content Area */}
                      <div className="flex-1">
                        <div className="text-center py-8 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border-2 border-purple-200">
                          <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-purple-500 mx-auto mb-4"></div>
                          <h4 className="text-lg font-semibold text-purple-700 mb-2">
                            {contextGenerationInProgress ? 'Generating your personalized contexts...' : 'Loading your contexts...'}
                          </h4>
                          <p className="text-gray-600">
                            {contextGenerationInProgress 
                              ? 'Creating conversation scenarios with level-specific starter phrases based on your interests. This may take a moment.'
                              : 'Fetching your personalized conversation scenarios.'
                            }
                          </p>
                          {contextGenerationInProgress && (
                            <p className="text-sm text-purple-600 mt-2">
                              ✨ Using AI to craft personalized scenarios with level-aware conversation starters
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Main content with sidebar */}
                  {userHasInterests !== false && !personalizedContextsLoading && !contextGenerationInProgress && (
                    <div className="flex gap-6">
                      {/* Mini Sidebar */}
                      <div className="w-32 flex-shrink-0">
                        <div className="sticky top-0 space-y-2">
                          {userHasInterests === true && (personalizedContexts.length > 0 || !personalizedContextsLoading) && (
                            <button
                              onClick={() => {
                                document.getElementById('for-you-section')?.scrollIntoView({ 
                                  behavior: 'smooth', 
                                  block: 'start' 
                                });
                              }}
                              className="w-full text-left px-3 py-2 rounded-lg bg-purple-50 hover:bg-purple-100 border border-purple-200 hover:border-purple-300 transition-all duration-200 group"
                            >
                              <div className="flex items-center gap-2">
                                <span className="text-sm">✨</span>
                                <div>
                                  <div className="font-medium text-sm text-purple-700 group-hover:text-purple-800">For You</div>
                                </div>
                              </div>
                            </button>
                          )}
                          
                          <button
                            onClick={() => {
                              document.getElementById('classic-contexts-section')?.scrollIntoView({ 
                                behavior: 'smooth', 
                                block: 'start' 
                              });
                            }}
                            className="w-full text-left px-3 py-2 rounded-lg bg-orange-50 hover:bg-orange-100 border border-orange-200 hover:border-orange-300 transition-all duration-200 group"
                          >
                            <div className="flex items-center gap-2">
                              <span className="text-sm">🎭</span>
                              <div>
                                <div className="font-medium text-sm text-orange-700 group-hover:text-orange-800">Classic</div>
                              </div>
                            </div>
                          </button>
                        </div>
                      </div>

                      {/* Content Area */}
                      <div className="flex-1">
                        {/* For You Section */}
                        {userHasInterests === true && personalizedContexts.length > 0 && (
                          <div id="for-you-section" className="mb-6 scroll-mt-4">
                            <div className="flex items-center justify-between mb-4">
                              <h4 className="text-lg font-semibold text-gray-800 flex items-center gap-2">
                                <span>✨</span> For You
                              </h4>
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={generateMoreContexts}
                                  disabled={personalizedContextsLoading}
                                  className="text-sm px-3 py-1 text-purple-600 hover:text-purple-800 hover:bg-purple-50 rounded transition-colors disabled:opacity-50"
                                >
                                  {personalizedContextsLoading ? '...' : 'Load More'}
                                </button>
                                <button
                                  onClick={checkUserInterestsAndLoadContexts}
                                  disabled={personalizedContextsLoading}
                                  className="text-sm px-2 py-1 text-gray-500 hover:text-gray-700 hover:bg-gray-50 rounded transition-colors disabled:opacity-50"
                                  title="Refresh contexts based on current interests"
                                >
                                  🔄
                                </button>
                              </div>
                            </div>
                            <div className="max-h-80 overflow-y-auto">
                              <div className="grid grid-cols-3 gap-3 mb-4">
                                {personalizedContexts.slice(0, 6).map(context => (
                                  <button
                                    key={context.id}
                                    className="flex flex-col items-center justify-center rounded-lg border-2 p-3 bg-gradient-to-br from-purple-50 to-pink-50 hover:from-purple-100 hover:to-pink-100 border-purple-200 hover:border-purple-400 transition-all duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-300 min-h-[120px]"
                                    onClick={() => handleContextSelect(context.id)}
                                    disabled={contextLoading}
                                  >
                                    <span className="text-2xl mb-1">{context.icon}</span>
                                    <span className="font-bold text-sm mb-1 text-purple-700 text-center leading-tight">{context.title}</span>
                                    <span className="text-xs text-gray-600 text-center leading-tight line-clamp-2">{context.description}</span>
                                    <div className="flex flex-wrap gap-1 mt-1">
                                      {context.interest_tags.slice(0, 2).map((tag, index) => (
                                        <span key={index} className="text-xs bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full">
                                          {tag}
                                        </span>
                                      ))}
                                    </div>
                                  </button>
                                ))}
                              </div>
                              
                              {/* Additional contexts in scrollable area */}
                              {personalizedContexts.length > 6 && (
                                <div className="grid grid-cols-3 gap-3">
                                  {personalizedContexts.slice(6).map(context => (
                                    <button
                                      key={context.id}
                                      className="flex flex-col items-center justify-center rounded-lg border-2 p-3 bg-gradient-to-br from-purple-50 to-pink-50 hover:from-purple-100 hover:to-pink-100 border-purple-200 hover:border-purple-400 transition-all duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-purple-300 min-h-[120px]"
                                      onClick={() => handleContextSelect(context.id)}
                                      disabled={contextLoading}
                                    >
                                      <span className="text-2xl mb-1">{context.icon}</span>
                                      <span className="font-bold text-sm mb-1 text-purple-700 text-center leading-tight">{context.title}</span>
                                      <span className="text-xs text-gray-600 text-center leading-tight line-clamp-2">{context.description}</span>
                                      <div className="flex flex-wrap gap-1 mt-1">
                                        {context.interest_tags.slice(0, 2).map((tag, index) => (
                                          <span key={index} className="text-xs bg-purple-100 text-purple-600 px-1.5 py-0.5 rounded-full">
                                            {tag}
                                          </span>
                                        ))}
                                      </div>
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                            
                            {/* Loading state for Load More */}
                            {personalizedContextsLoading && (
                              <div className="text-center py-6 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border-2 border-purple-200">
                                <div className="animate-spin rounded-full h-6 w-6 border-t-2 border-b-2 border-purple-500 mx-auto mb-3"></div>
                                <p className="text-sm text-purple-700 font-medium">
                                  Generating more personalized contexts...
                                </p>
                                <p className="text-xs text-gray-600 mt-1">
                                  ✨ Creating new scenarios with level-specific phrases based on your interests
                                </p>
                              </div>
                            )}
                          </div>
                        )}

                        {/* Generate Contexts Button - when user has interests but no contexts */}
                        {userHasInterests === true && personalizedContexts.length === 0 && !personalizedContextsLoading && (
                          <div id="for-you-section" className="mb-6 scroll-mt-4">
                            <div className="text-center py-8 bg-gradient-to-br from-purple-50 to-pink-50 rounded-lg border-2 border-purple-200">
                              <div className="text-4xl mb-4">✨</div>
                              <h4 className="text-lg font-semibold text-purple-700 mb-2">
                                Generate Your Personalized Contexts
                              </h4>
                              <p className="text-gray-600 mb-4">
                                Create conversation scenarios tailored to your interests.
                              </p>
                              <button
                                onClick={generateMoreContexts}
                                disabled={personalizedContextsLoading}
                                className="px-6 py-2 bg-purple-500 text-white rounded-lg hover:bg-purple-600 transition-colors disabled:opacity-50"
                              >
                                Generate Contexts
                              </button>
                            </div>
                          </div>
                        )}

                        {/* Classic Contexts Section */}
                        <div id="classic-contexts-section" className="scroll-mt-4">
                          <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                            <span>🎭</span> Classic Contexts
                          </h4>
                          <div className="max-h-80 overflow-y-auto">
                            <div className="grid grid-cols-3 gap-3">
                              {contextCards.map(context => (
                                <button
                                  key={context.id}
                                  className="flex flex-col items-center justify-center rounded-lg border-2 p-3 bg-orange-50 hover:bg-orange-100 border-orange-200 hover:border-orange-400 transition-all duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-orange-300 min-h-[120px]"
                                  onClick={() => handleContextSelect(context.id)}
                                  disabled={contextLoading}
                                >
                                  <span className="text-2xl mb-1">{context.icon}</span>
                                  <span className="font-bold text-sm mb-1 text-orange-700 text-center leading-tight">{context.title}</span>
                                  <span className="text-xs text-gray-600 text-center leading-tight line-clamp-2">{context.description}</span>
                                </button>
                              ))}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Show old layout for users with no interests */}
                  {userHasInterests === false && (
                    <div className="max-h-[70vh] overflow-y-auto">
                      {/* Classic Contexts Section */}
                      <div>
                        <h4 className="text-lg font-semibold text-gray-800 mb-4 flex items-center gap-2">
                          <span>🎭</span> Classic Contexts
                        </h4>
                        <div className="max-h-[60vh] overflow-y-auto">
                          <div className="grid grid-cols-3 gap-3">
                            {contextCards.map(context => (
                              <button
                                key={context.id}
                                className="flex flex-col items-center justify-center rounded-lg border-2 p-3 bg-orange-50 hover:bg-orange-100 border-orange-200 hover:border-orange-400 transition-all duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-orange-300 min-h-[120px]"
                                onClick={() => handleContextSelect(context.id)}
                                disabled={contextLoading}
                              >
                                <span className="text-2xl mb-1">{context.icon}</span>
                                <span className="font-bold text-sm mb-1 text-orange-700 text-center leading-tight">{context.title}</span>
                                <span className="text-xs text-gray-600 text-center leading-tight line-clamp-2">{context.description}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      </div>
                    </div>
                  )}

                  {contextLoading && (
                    <div className="flex justify-center mt-6">
                      <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-orange-500"></div>
                    </div>
                  )}
                  <div className="flex justify-center mt-6">
                    <button
                      className="px-4 py-2 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
                      onClick={() => setShowContextModal(false)}
                      disabled={contextLoading}
                    >
                      Cancel
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>

      {/* Delete Curriculum Modal */}
      <Transition.Root show={!!showDeleteId} as={Fragment}>
        <Dialog as="div" className="relative z-50" onClose={() => setShowDeleteId(null)}>
          <Transition.Child
            as={Fragment}
            enter="ease-out duration-300" enterFrom="opacity-0" enterTo="opacity-100"
            leave="ease-in duration-200" leaveFrom="opacity-100" leaveTo="opacity-0"
          >
            <div className="fixed inset-0 bg-black bg-opacity-30 transition-opacity" />
          </Transition.Child>
          <div className="fixed inset-0 z-50 overflow-y-auto">
            <div className="flex min-h-full items-center justify-center p-4 text-center">
              <Transition.Child
                as={Fragment}
                enter="ease-out duration-300" enterFrom="opacity-0 scale-95" enterTo="opacity-100 scale-100"
                leave="ease-in duration-200" leaveFrom="opacity-100 scale-100" leaveTo="opacity-0 scale-95"
              >
                <Dialog.Panel className="w-full max-w-md transform overflow-hidden rounded-2xl bg-white p-8 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title as="h3" className="text-2xl font-bold mb-4 text-red-600 text-center">
                    Delete this curriculum?
                  </Dialog.Title>
                  {(() => {
                    const c = curriculums.find(cur => cur.id === showDeleteId);
                    if (!c) return null;
                    return (
                      <div className="mb-4 text-center">
                        <div className="text-lg font-semibold mb-1 flex items-center justify-center gap-2">
                          <MultiCountryFlags language={languages.find(l => l.code === c.language) || { code: c.language, name: c.language, flag: '🏳️', countryFlags: ['🏳️'] }} />
                        </div>
                        <div className="text-sm text-gray-700 mb-1">Start Level: <span className="font-semibold">{c.start_level}</span></div>
                        <div className="text-sm text-gray-700 mb-1">Current Level: <span className="font-semibold">{getCurrentLevel(c)}</span></div>
                        <div className="text-sm text-gray-700 mb-1">Start Date: <span className="font-semibold">{c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Unknown'}</span></div>
                      </div>
                    );
                  })()}
                  <div className="text-sm text-gray-700 mb-2 text-center">This action <b>cannot be undone</b> and will remove all progress and lessons for this language path.</div>
                  <label className="flex items-center mb-3 text-xs text-gray-600 justify-center">
                    <input type="checkbox" className="mr-2" checked={deleteConfirmChecked} onChange={e => setDeleteConfirmChecked(e.target.checked)} />
                    I understand this cannot be undone
                  </label>
                  <div className="flex gap-2 justify-center">
                    <button
                      className="px-3 py-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
                      onClick={() => setShowDeleteId(null)}
                      disabled={deleting}
                    >
                      Cancel
                    </button>
                    <button
                      className="px-3 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                      disabled={!deleteConfirmChecked || deleting}
                      onClick={async () => {
                        setDeleting(true);
                        setError(null);
                        try {
                          const res = await fetch(`${API_BASE}/api/curriculums/${showDeleteId}?token=${token}`, { method: 'DELETE' });
                          if (!res.ok) throw new Error('Failed to delete curriculum');
                          setShowDeleteId(null);
                          await fetchCurriculums();
                        } catch (e) {
                          setError(e instanceof Error ? e.message : String(e));
                        } finally {
                          setDeleting(false);
                        }
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </Dialog.Panel>
              </Transition.Child>
            </div>
          </div>
        </Dialog>
      </Transition.Root>

      {/* Lesson Summary Modal */}
      <LessonSummaryModal
        isOpen={showLessonSummary}
        onClose={handleCloseLessonSummary}
        onReturnToDashboard={handleCloseLessonSummary}
        summaryData={lessonSummaryData}
        loading={loadingSummary}
        token={token}
      />

      {error && (
        <div className="mt-6 text-red-500 text-center">{error}</div>
        )}
      </div>
  );
};

export default Dashboard; 