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
import CorrectionPatterns from './components/CorrectionPatterns';
import ProficiencyLevelChart from './components/ProficiencyLevelChart';
import { createClient } from '@supabase/supabase-js';
import { Dialog, Transition } from '@headlessui/react';
import { PlusIcon, TrashIcon } from '@heroicons/react/24/solid';
import '@fontsource/press-start-2p';
import YourKnowledgePanel from './components/YourKnowledgePanel';
import WeaknessAnalysis from './components/WeaknessAnalysis';
import LessonSummaryModal from './components/LessonSummaryModal';

interface LanguageCard {
  code: string;
  name: string;
  flag: string;
}

interface ContextCard {
  id: string;
  title: string;
  description: string;
  icon: string;
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
  newVocabulary: string[];
  improvementAreas: string[];
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
  { code: 'en', name: 'English', flag: '🇬🇧' },
  { code: 'it', name: 'Italian', flag: '🇮🇹' },
  { code: 'es', name: 'Spanish', flag: '🇪🇸' },
  { code: 'pt', name: 'Portuguese', flag: '🇵🇹' },
  { code: 'fr', name: 'French', flag: '🇫🇷' },
  { code: 'de', name: 'German', flag: '🇩🇪' },
  { code: 'kn', name: 'Kannada', flag: '🇮🇳' }
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

const API_BASE = 'http://localhost:8000';

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
  const [lessonProgress, setLessonProgress] = useState<Record<string, any>>({});
  const [showLessonSummary, setShowLessonSummary] = useState(false);
  const [lessonSummaryData, setLessonSummaryData] = useState<LessonSummaryData | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingSummaryMap, setLoadingSummaryMap] = useState<Record<string, boolean>>({});
  const [showCompletedLessons, setShowCompletedLessons] = useState(false);
  const [displayedLessonsCount, setDisplayedLessonsCount] = useState(10);
  const router = useRouter();

  const user = useUser();

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
  }, []);

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
      alert(e instanceof Error ? e.message : String(e));
    }
  };

  const handleStartConversation = () => {
    setShowContextModal(true);
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
        alert('No progress found for this lesson');
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
        alert('Failed to load report card. Please try again.');
      }
    } catch (error) {
      console.error('[View Report Card] Error:', error);
      alert('Failed to load report card. Please try again.');
    } finally {
      setLoadingSummaryMap(prev => ({ ...prev, [lessonId]: false }));
      setLoadingSummary(false);
    }
  };

  const handleCloseLessonSummary = () => {
    setShowLessonSummary(false);
    setLessonSummaryData(null);
  };

  useEffect(() => {
    const fetchFeedback = async () => {
      setFeedbackLoading(true);
      setFeedbackError(null);
      try {
        const { data: { user } } = await supabaseClient.auth.getUser();
        if (!user) return;
        // Fetch feedback data from message_feedback table
        const { data, error } = await supabaseClient
          .from('message_feedback')
          .select('*')
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
  }, []);

  if (authLoading) {
    return <div className="max-w-5xl mx-auto p-6">Loading authentication...</div>;
  }
  if (!user || !token) {
    return <Auth />;
  }

  return (
    <div className="relative max-w-6xl mx-auto p-6 min-h-screen bg-gradient-to-br from-orange-50 via-white to-orange-100">
      {/* Jump into a Conversation Button */}
      <div className="flex flex-col items-center mb-8 relative" style={{zIndex: 1}}>
        {/* Top doodle burst */}
        <svg width="240" height="50" viewBox="0 0 240 50" fill="none" xmlns="http://www.w3.org/2000/svg" className="mb-2">
          {/* Left scribble */}
          <path d="M20 20 Q10 18 25 25 Q10 28 28 30" stroke="#222" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          <path d="M35 10 Q25 15 40 18 Q28 22 45 25" stroke="#222" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Right scribble */}
          <path d="M220 20 Q230 18 215 25 Q230 28 212 30" stroke="#222" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          <path d="M205 10 Q215 15 200 18 Q212 22 195 25" stroke="#222" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Top scribble */}
          <path d="M120 5 Q122 12 118 18 Q125 10 130 18" stroke="#222" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        </svg>
        <button
          className="retro-header px-7 py-3 text-lg font-extrabold bg-orange-500 text-white border-4 border-orange-300 rounded-full shadow-[0_8px_32px_0_rgba(255,140,0,0.18)] hover:bg-orange-600 hover:scale-105 transition-all duration-200 focus:outline-none focus:ring-4 focus:ring-orange-200 relative"
          style={{
            textShadow: '2px 2px 0 #ffb74d',
            color: '#fff',
            boxShadow: '0 8px 32px 0 rgba(255,140,0,0.18), 0 2px 0 #ffb74d',
            background: 'linear-gradient(180deg, #ff9800 0%, #fb8c00 100%)',
            letterSpacing: '1px',
            overflow: 'visible',
          }}
          onClick={handleStartConversation}
        >
          <span className="mr-2 text-xl align-middle">💬</span>Jump into a Conversation
        </button>
        {/* Bottom doodle burst */}
        <svg width="240" height="50" viewBox="0 0 240 50" fill="none" xmlns="http://www.w3.org/2000/svg" className="mt-2">
          {/* Left scribble */}
          <path d="M20 30 Q10 32 25 25 Q10 22 28 20" stroke="#222" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          <path d="M35 40 Q25 35 40 32 Q28 28 45 25" stroke="#222" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Right scribble */}
          <path d="M220 30 Q230 32 215 25 Q230 22 212 20" stroke="#222" strokeWidth="3.5" strokeLinecap="round" fill="none" />
          <path d="M205 40 Q215 35 200 32 Q212 28 195 25" stroke="#222" strokeWidth="2.5" strokeLinecap="round" fill="none" />
          {/* Bottom scribble */}
          <path d="M120 45 Q122 38 118 32 Q125 40 130 32" stroke="#222" strokeWidth="2.5" strokeLinecap="round" fill="none" />
        </svg>
      </div>
      {/* Floating Add Button */}
      <div className="mb-12">
        <h2 className="retro-header text-3xl font-extrabold text-center mb-4">
          Language Paths
        </h2>
        <div className="flex items-center mb-2 px-10 gap-2">
        <button
            className="bg-orange-500 hover:bg-orange-600 text-white rounded-full shadow-lg p-1.5 transition-transform duration-200 hover:scale-110 focus:outline-none focus:ring-4 focus:ring-orange-300"
            title="Add Language Path"
            onClick={() => setShowAdd(v => !v)}
            style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.10)' }}
          >
            <PlusIcon className="h-4 w-4" />
        </button>
          <span className="ml-2 text-sm text-gray-700 font-medium select-none">Add Language Path</span>
        </div>
        <div className="px-10 py-2">
          <div className="flex space-x-4 overflow-x-auto pb-2 mb-4" style={{ WebkitOverflowScrolling: 'touch' }}>
            {curriculums.map(c => (
              <div
                key={c.id}
                className={`relative min-w-[240px] max-w-[280px] rounded-2xl bg-white/60 backdrop-blur-md shadow-xl p-4 cursor-pointer border-2 transition-all duration-200 ${selectedCurriculum && c.id === selectedCurriculum.id ? 'border-orange-500 scale-102 ring-4 ring-orange-100' : 'border-transparent hover:border-orange-300 hover:scale-101'} group`}
                onClick={() => handleCurriculumChange(c.id)}
                style={{ boxShadow: '0 8px 32px 0 rgba(255,140,0,0.10)' }}
              >
                {/* Delete button */}
                <button
                  className="absolute top-2 right-2 bg-white shadow-lg rounded-full p-1.5 z-20 border-2 border-red-200 hover:bg-red-500 hover:text-white transition-colors duration-200 group-hover:scale-105 focus:outline-none"
                  title="Remove this learning path"
                  onClick={e => { e.stopPropagation(); setShowDeleteId(c.id); setDeleteConfirmChecked(false); }}
                  style={{ boxShadow: '0 4px 16px 0 rgba(255,0,0,0.10)' }}
                >
                  <TrashIcon className="h-4 w-4" />
                </button>
                <div className="text-2xl font-bold mb-2 flex items-center gap-2">
                  {languages.find(l => l.code === c.language)?.flag}
                  {languages.find(l => l.code === c.language)?.name || c.language}
                </div>
                <div className="text-sm text-gray-700 mb-1">Start Level: <span className="font-semibold">{c.start_level}</span></div>
                <div className="text-sm text-gray-700 mb-1">Start Date: <span className="font-semibold">{c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Unknown'}</span></div>
                <div className="text-sm text-gray-700">Current Level: <span className="font-semibold">(coming soon)</span></div>
              </div>
            ))}
          </div>
        </div>
            </div>

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
                    isCompleted ? 'border-green-200' : isInProgress ? 'border-orange-200' : 'border-gray-100'
                  }`}
                  style={{ boxShadow: '0 4px 24px 0 rgba(255,140,0,0.08)' }}
                >
                  {/* Progress Status Badge */}
                  {progress && (
                    <div className={`${isCompact ? 'px-4 pt-2' : 'px-5 pt-3'}`}>
                      <div className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                        isCompleted 
                          ? 'bg-green-100 text-green-800' 
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
                        className={`${isCompact ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm'} rounded-lg font-semibold shadow transition-colors bg-blue-500 hover:bg-blue-600 text-white`}
                        onClick={() => handleViewReportCard(lesson.id)}
                        disabled={loadingSummaryMap[lesson.id]}
                      >
                        {loadingSummaryMap[lesson.id] ? 'Loading...' : '📊 Report Card'}
                      </button>
                    )}
                    <button
                      className={`${isCompact ? 'px-4 py-1.5 text-xs' : 'px-5 py-2 text-sm'} rounded-lg font-semibold shadow transition-colors ${
                        isCompleted 
                          ? 'bg-green-500 hover:bg-green-600 text-white' 
                          : isInProgress 
                            ? 'bg-orange-500 hover:bg-orange-600 text-white' 
                            : 'bg-orange-500 hover:bg-orange-600 text-white'
                      }`}
                      onClick={() => handleStartLesson(lesson.id)}
                    >
                      {isCompleted ? 'Review Lesson' : isInProgress ? 'Continue Lesson' : 'Start Lesson'}
                    </button>
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
                      className="w-full mb-4 p-4 bg-green-50 hover:bg-green-100 border-2 border-green-200 rounded-xl transition-colors duration-200 focus:outline-none focus:ring-4 focus:ring-green-100"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="bg-green-500 text-white rounded-full p-2">
                            ✅
                          </div>
                          <div className="text-left">
                            <h3 className="text-lg font-bold text-green-800">
                              Completed Lessons ({allCompletedLessons.length})
                            </h3>
                            <p className="text-sm text-green-600">
                              Great job! Click to view your completed lessons
                            </p>
                          </div>
                        </div>
                        <div className={`transform transition-transform duration-200 ${showCompletedLessons ? 'rotate-180' : ''}`}>
                          <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </div>
                      </div>
                    </button>
                    
                    {/* Expanded Completed Lessons */}
                    {showCompletedLessons && (
                      <div className="flex space-x-4 overflow-x-auto pb-2 bg-green-50/50 rounded-xl p-4 border border-green-200" style={{ WebkitOverflowScrolling: 'touch' }}>
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

      {/* User Progress Analytics */}
      {selectedCurriculum && (
        <div className="mb-8">
          <h2 className="retro-header text-3xl font-extrabold text-center mb-4">
            Your Progress
          </h2>
          {feedbackLoading ? (
            <div className="bg-white rounded shadow p-6 text-gray-500 text-center">Loading analytics...</div>
          ) : feedbackError ? (
            <div className="bg-white rounded shadow p-6 text-red-500 text-center">{feedbackError}</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column */}
              <div className="space-y-6">
                {/* Your Knowledge Panel as first analytics card */}
                <div className="bg-white rounded-lg shadow p-6">
                  <YourKnowledgePanel language={selectedCurriculum.language} level={selectedCurriculum.start_level} />
                </div>
                {/* 1. Mistake Categories Chart */}
                <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
                  <h3 className="text-lg font-medium mb-4">Mistake Categories</h3>
                  <div className="flex-1 overflow-hidden">
                    <MistakeCategoriesChart 
                      mistakes={filteredFeedbacks.reduce((acc, f) => [...acc, ...f.mistakes], [] as Mistake[])} 
                    />
                  </div>
                </div>
                {/* 2. Severity Analysis */}
                <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
                  <h3 className="text-lg font-medium mb-4">Mistake Severity</h3>
                  <div className="flex-1 overflow-hidden">
                    <SeverityAnalysisChart 
                      mistakes={filteredFeedbacks.reduce((acc, f) => [...acc, ...f.mistakes], [] as Mistake[])}
                      totalConversations={filteredFeedbacks.length}
                      totalMessages={filteredFeedbacks.length}
                    />
                  </div>
                </div>
                {/* 3. Common Mistake Types */}
                <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
                  <h3 className="text-lg font-medium mb-4">Common Mistakes</h3>
                  <div className="flex-1 overflow-y-auto">
                    <CommonMistakesList 
                      mistakes={filteredFeedbacks.reduce((acc, f) => [...acc, ...f.mistakes], [] as Mistake[])} 
                    />
                  </div>
                </div>
              </div>
              {/* Right Column */}
              <div className="space-y-6">
                {/* Weakness Analysis and Custom Lessons */}
                <div className="bg-white rounded-lg shadow p-6">
                  <WeaknessAnalysis 
                    curriculumId={selectedCurriculum.id} 
                    language={selectedCurriculum.language}
                    token={token || ''}
                  />
                </div>
                {/* 4. Progress Over Time */}
                <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
                  <h3 className="text-lg font-medium mb-4">Progress Over Time</h3>
                  <div className="flex-1 overflow-hidden">
                    <ProgressOverTimeChart 
                      mistakes={filteredFeedbacks.reduce((acc, f) => [...acc, ...f.mistakes], [] as Mistake[])}
                      feedbacks={filteredFeedbacks.map(f => ({
                        timestamp: f.created_at || f.timestamp,
                        mistakes: f.mistakes
                      }))}
                    />
                  </div>
                </div>
                {/* 5. Language Feature Analysis */}
                <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
                  <h3 className="text-lg font-medium mb-4">Language Features</h3>
                  <div className="flex-1 overflow-y-auto">
                    <LanguageFeaturesHeatmap 
                      mistakes={filteredFeedbacks.reduce((acc, f) => [...acc, ...f.mistakes], [] as Mistake[])} 
                    />
                  </div>
                </div>
                {/* 6. Context Performance */}
                <div className="bg-white rounded-lg shadow p-6 h-[400px] flex flex-col">
                  <h3 className="text-lg font-medium mb-4">Mistakes per 30-Message Conversation</h3>
                  <div className="flex-1 overflow-hidden">
                    <ScaledMistakesPerConversationChart feedbacks={filteredFeedbacks} />
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
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
                            <span className="text-2xl mb-1">{languages.find(lang => lang.code === l.code)?.flag}</span>
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
                <Dialog.Panel className="w-full max-w-lg transform overflow-hidden rounded-2xl bg-white p-8 text-left align-middle shadow-xl transition-all">
                  <Dialog.Title as="h3" className="text-2xl font-bold mb-4 text-orange-600 text-center">
                    Choose a Conversation Context
                  </Dialog.Title>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    {contextCards.map(context => (
                      <button
                        key={context.id}
                        className="flex flex-col items-center justify-center rounded-xl border-2 p-5 bg-orange-50 hover:bg-orange-100 border-orange-200 hover:border-orange-400 transition-all duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-orange-300"
                        onClick={() => handleContextSelect(context.id)}
                        disabled={contextLoading}
                      >
                        <span className="text-3xl mb-2">{context.icon}</span>
                        <span className="font-bold text-lg mb-1 text-orange-700">{context.title}</span>
                        <span className="text-sm text-gray-600 text-center">{context.description}</span>
                      </button>
                    ))}
                  </div>
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
                          {languages.find(l => l.code === c.language)?.flag}
                          {languages.find(l => l.code === c.language)?.name || c.language}
                        </div>
                        <div className="text-sm text-gray-700 mb-1">Start Level: <span className="font-semibold">{c.start_level}</span></div>
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
      />

      {error && (
        <div className="mt-6 text-red-500 text-center">{error}</div>
        )}
      </div>
  );
};

export default Dashboard; 