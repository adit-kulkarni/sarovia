'use client';

import { useEffect, useState } from 'react';
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
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/curriculums/${curriculumId}/lessons?token=${token}`);
      if (!res.ok) throw new Error('Failed to fetch lessons');
      const data: LessonPreview[] = await res.json();
      setLessons(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // Fetch lesson templates for selected curriculum's language
  useEffect(() => {
    async function fetchLessonTemplates(language: string) {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`${API_BASE}/api/lesson_templates?language=${language}`);
        if (!res.ok) throw new Error('Failed to fetch lesson templates');
        const data: LessonTemplatePreview[] = await res.json();
        setLessonTemplates(data);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    }
    if (selectedCurriculum) {
      fetchLessonTemplates(selectedCurriculum.language);
    } else {
      setLessonTemplates([]);
    }
  }, [selectedCurriculum]);

  const handleCurriculumChange = (id: string) => {
    const found = curriculums.find(c => c.id === id);
    if (found) setSelectedCurriculum(found);
  };

  const handleAddLanguage = () => {
    router.push('/curriculum'); // Go to curriculum creation page
  };

  const handleStartLesson = (lessonId: string) => {
    router.push(`/curriculum/lesson/${lessonId}`);
  };

  const handleStartConversation = () => {
    if (!selectedCurriculum) return;
    router.push(`/chat?language=${selectedCurriculum.language}&level=${selectedCurriculum.start_level}`);
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.refresh();
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
    <div className="max-w-5xl mx-auto p-6">
      {/* Conversation Launcher */}
      <div className="flex justify-center mb-8">
        <button
          className="px-8 py-3 rounded-full text-white font-medium bg-orange-500 hover:bg-orange-600 transition-colors text-lg"
          onClick={handleStartConversation}
          disabled={!selectedCurriculum}
        >
          Jump into a Conversation
        </button>
      </div>
      {/* Language Path Cards */}
      <div className="mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xl font-bold">Language Paths</h2>
          <button
            className="ml-2 p-2 rounded-full bg-orange-500 text-white hover:bg-orange-600 focus:outline-none focus:ring-2 focus:ring-orange-300"
            title="Add Language Path"
            onClick={() => setShowAdd(v => !v)}
          >
            <span className="text-xl font-bold">+</span>
          </button>
        </div>
        {showAdd && (
          <form className="mb-4 flex gap-4 items-end" onSubmit={async e => {
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
              <label className="block text-xs font-medium mb-1">Language</label>
              <select value={newLang} onChange={e => setNewLang(e.target.value)} className="rounded border-gray-300">
                {languagesList.map(l => <option key={l.code} value={l.code}>{l.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium mb-1">Starting Level</label>
              <select value={newLevel} onChange={e => setNewLevel(e.target.value)} className="rounded border-gray-300">
                {levels.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
              disabled={adding}
            >
              {adding ? 'Adding...' : 'Add'}
            </button>
          </form>
        )}
        <div className="flex space-x-4 overflow-x-auto pb-2" style={{ WebkitOverflowScrolling: 'touch' }}>
          {curriculums.map(c => (
            <div
              key={c.id}
              className={`relative min-w-[260px] max-w-[300px] rounded-xl shadow p-5 cursor-pointer border-2 transition-all duration-150 ${selectedCurriculum && c.id === selectedCurriculum.id ? 'border-orange-500 bg-orange-50' : 'border-gray-200 bg-white'} hover:border-orange-400`}
              onClick={() => handleCurriculumChange(c.id)}
            >
              {/* Delete button */}
              <button
                className="absolute top-2 right-2 p-1 rounded-full bg-red-500 text-white hover:bg-red-600 z-10"
                title="Remove this learning path"
                onClick={e => { e.stopPropagation(); setShowDeleteId(c.id); setDeleteConfirmChecked(false); }}
              >
                &#10006;
              </button>
              <div className="text-lg font-semibold mb-1">{languages.find(l => l.code === c.language)?.name || c.language}</div>
              <div className="text-sm text-gray-600 mb-1">Start Level: <span className="font-medium">{c.start_level}</span></div>
              <div className="text-sm text-gray-600 mb-1">Start Date: <span className="font-medium">{c.created_at ? new Date(c.created_at).toLocaleDateString() : 'Unknown'}</span></div>
              <div className="text-sm text-gray-600">Current Level: <span className="font-medium">(coming soon)</span></div>
              {/* Delete confirmation popup */}
              {showDeleteId === c.id && (
                <div className="absolute top-8 left-1/2 -translate-x-1/2 z-20 bg-white border border-red-400 rounded-xl shadow-lg p-5 w-72 flex flex-col items-center">
                  <div className="text-red-600 font-semibold mb-2">Delete this curriculum?</div>
                  <div className="text-sm text-gray-700 mb-2 text-center">This action <b>cannot be undone</b> and will remove all progress and lessons for this language path.</div>
                  <label className="flex items-center mb-3 text-xs text-gray-600">
                    <input type="checkbox" className="mr-2" checked={deleteConfirmChecked} onChange={e => setDeleteConfirmChecked(e.target.checked)} />
                    I understand this cannot be undone
                  </label>
                  <div className="flex gap-2">
                    <button
                      className="px-3 py-1 rounded bg-gray-200 text-gray-700 hover:bg-gray-300"
                      onClick={e => { e.stopPropagation(); setShowDeleteId(null); }}
                      disabled={deleting}
                    >
                      Cancel
                    </button>
                    <button
                      className="px-3 py-1 rounded bg-red-600 text-white hover:bg-red-700 disabled:opacity-50"
                      disabled={!deleteConfirmChecked || deleting}
                      onClick={async e => {
                        e.stopPropagation();
                        setDeleting(true);
                        setError(null);
                        try {
                          const res = await fetch(`${API_BASE}/api/curriculums/${c.id}?token=${token}`, { method: 'DELETE' });
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
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Curriculum Path Tiles (for selected curriculum) */}
      <div className="mb-8">
        <h2 className="text-xl font-bold mb-4">Curriculum Path</h2>
        <div className="flex space-x-4 overflow-x-auto pb-2" style={{ WebkitOverflowScrolling: 'touch' }}>
          {lessonTemplates.slice(0, 15).map(lesson => (
            <div
              key={lesson.id}
              className="min-w-[260px] max-w-[300px] bg-white rounded shadow p-4 border border-orange-100"
            >
              <div className="font-semibold mb-2">Lesson {lesson.order_num}: {lesson.title}</div>
              <div className="text-sm text-gray-500 mb-1">Level: {lesson.level || 'N/A'} | Difficulty: {lesson.difficulty || 'N/A'}</div>
              {lesson.objectives && <div className="text-xs text-gray-600">{lesson.objectives}</div>}
            </div>
          ))}
          {lessonTemplates.length === 0 && !loading && (
            <div className="text-gray-400">No lessons found for this curriculum.</div>
          )}
        </div>
      </div>

      {/* User Progress Analytics */}
      {selectedCurriculum && (
        <div className="mb-8">
          <h2 className="text-xl font-bold mb-4">Your Progress</h2>
          {feedbackLoading ? (
            <div className="bg-white rounded shadow p-6 text-gray-500 text-center">Loading analytics...</div>
          ) : feedbackError ? (
            <div className="bg-white rounded shadow p-6 text-red-500 text-center">{feedbackError}</div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Left Column */}
              <div className="space-y-6">
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

      {error && (
        <div className="mt-6 text-red-500 text-center">{error}</div>
      )}
    </div>
  );
};

export default Dashboard; 