'use client';

import React, { useState, useEffect } from 'react';
import { TrashIcon } from '@heroicons/react/24/solid';
import { useRouter } from 'next/navigation';

interface WeaknessPattern {
  category: string;
  type: string;
  frequency: number;
  severity_distribution: {
    minor: number;
    moderate: number;
    critical: number;
  };
  examples: Array<{
    error: string;
    correction: string;
    explanation: string;
  }>;
  language_feature_tags: string[];
}

interface CustomLesson {
  id: string;
  title: string;
  difficulty: string;
  objectives: string;
  content: string;
  cultural_element: string;
  practice_activity: string;
  targeted_weaknesses: string[];
  created_at: string;
  // Additional fields for suggestions
  pattern_focus?: string;
  pattern_frequency?: number;
}

interface WeaknessAnalysisProps {
  curriculumId: string;
  language: string;
  token: string;
}

interface LessonSuggestion {
  id: string;
  suggestions_count: number;
  generated_lessons: CustomLesson[];
  suggestion_data: any;
  created_at: string;
}

export default function WeaknessAnalysis({ curriculumId, language, token }: WeaknessAnalysisProps) {
  const [customLessons, setCustomLessons] = useState<CustomLesson[]>([]);
  const [error, setError] = useState<string | null>(null);
  
  // New suggestion system state
  const [hasNotifications, setHasNotifications] = useState(false);
  const [suggestionsCount, setSuggestionsCount] = useState(0);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [currentSuggestions, setCurrentSuggestions] = useState<LessonSuggestion | null>(null);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  const [dailySuggestionsLoaded, setDailySuggestionsLoaded] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [isUnseen, setIsUnseen] = useState(false); // Track if suggestions are unseen (red vs grey)

  const router = useRouter();

  useEffect(() => {
    loadCustomLessons();
    checkDailySuggestions();
  }, [curriculumId]);
  
  // Listen for suggestion notifications from WebSocket/feedback system
  useEffect(() => {
    const handleSuggestionNotification = (event: CustomEvent) => {
      if (event.detail.curriculum_id === curriculumId) {
        setHasNotifications(true);
        setSuggestionsCount(prev => prev + 1);
      }
    };
    
    window.addEventListener('suggestion.available', handleSuggestionNotification as EventListener);
    return () => {
      window.removeEventListener('suggestion.available', handleSuggestionNotification as EventListener);
    };
  }, [curriculumId]);

  const loadCustomLessons = async () => {
    if (!token || !curriculumId) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/custom_lessons?curriculum_id=${curriculumId}&token=${token}`, {
        method: 'GET',
      });
      
      if (!response.ok) {
        throw new Error('Failed to load custom lessons');
      }
      
      const data = await response.json();
      setCustomLessons(data || []);
    } catch (err) {
      console.error('Error loading custom lessons:', err);
    }
  };



  const startCustomLessonConversation = async (customLessonId: string) => {
    if (!token || !curriculumId) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/start_custom_lesson_conversation?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          custom_lesson_id: customLessonId,
          curriculum_id: curriculumId,
        }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to start custom lesson conversation');
      }
      
      const data = await response.json();
      
      // Use router.push with same URL pattern as regular lessons
      router.push(`/chat?conversation=${data.conversation_id}&curriculum_id=${curriculumId}`);
    } catch (err) {
      // Use alert for consistency with regular lessons
      alert(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const deleteCustomLesson = async (lessonId: string) => {
    if (!token) return;
    
    if (!confirm('Are you sure you want to delete this custom lesson?')) {
      return;
    }
    
    try {
      const response = await fetch(`http://localhost:8000/api/custom_lessons/${lessonId}?token=${token}`, {
        method: 'DELETE',
      });
      
      if (!response.ok) {
        throw new Error('Failed to delete custom lesson');
      }
      
      setCustomLessons(prev => prev.filter(lesson => lesson.id !== lessonId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  // New suggestion system functions
  const checkDailySuggestions = async () => {
    if (!token || !curriculumId || dailySuggestionsLoaded) return;
    
    try {
      // First check for existing suggestions, with auto-generate enabled for first daily visit
      const response = await fetch(`http://localhost:8000/api/lesson_suggestions/check?curriculum_id=${curriculumId}&auto_generate=true&token=${token}`);
      if (response.ok) {
        const data = await response.json();
        if (data.has_suggestions) {
          setHasNotifications(true);
          setSuggestionsCount(data.suggestion_count || 1);
          setIsUnseen(data.is_unseen !== false); // Default to unseen unless explicitly false
          
          // If suggestions were auto-generated or exist from today, load them immediately
          if (data.type === 'auto_generated' || (data.type === 'existing' && data.from_today)) {
            setCurrentSuggestions({
              id: data.suggestions[0].id || data.suggestions[0].suggestion_id,
              suggestions_count: data.suggestion_count,
              generated_lessons: data.suggestions[0].lessons || data.suggestions[0].generated_lessons,
              suggestion_data: data.suggestions[0],
              created_at: new Date().toISOString()
            });
          }
        }
        setDailySuggestionsLoaded(true);
      }
    } catch (err) {
      console.error('Error checking daily suggestions:', err);
      setDailySuggestionsLoaded(true);
    }
  };

  const checkSuggestions = async () => {
    if (!token || !curriculumId) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/lesson_suggestions/check?curriculum_id=${curriculumId}&token=${token}`);
      if (response.ok) {
        const data = await response.json();
        if (data.has_suggestions) {
          setHasNotifications(true);
          setSuggestionsCount(data.suggestion_count || 1);
        }
      }
    } catch (err) {
      console.error('Error checking suggestions:', err);
    }
  };

  const generateSuggestions = async () => {
    if (!token || !curriculumId) return;
    
    setLoadingSuggestions(true);
    try {
      const response = await fetch(`http://localhost:8000/api/lesson_suggestions/generate?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curriculum_id: curriculumId }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
      }
      
      const data = await response.json();
      setCurrentSuggestions({
        id: data.suggestion_id,
        suggestions_count: data.lessons.length,
        generated_lessons: data.lessons,
        suggestion_data: data,
        created_at: new Date().toISOString()
      });
      setShowSuggestions(true);
      setHasNotifications(false);
      setSuggestionsCount(0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoadingSuggestions(false);
    }
  };

  const useSuggestion = async (lessonIndex: number) => {
    if (!currentSuggestions || !token) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/lesson_suggestions/${currentSuggestions.id}/use?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lesson_index: lessonIndex }),
      });
      
      if (!response.ok) {
        throw new Error('Failed to create lesson from suggestion');
      }
      
      const data = await response.json();
      setCustomLessons(prev => [data.lesson, ...prev]);
      
      // Remove the used lesson from current suggestions and update count
      const updatedLessons = currentSuggestions.generated_lessons.filter((_, index) => index !== lessonIndex);
      if (updatedLessons.length === 0) {
        // All lessons used, close modal
        setShowSuggestions(false);
        setCurrentSuggestions(null);
        setHasNotifications(false);
        setSuggestionsCount(0);
        setIsUnseen(false);
      } else {
        // Update current suggestions with remaining lessons
        setCurrentSuggestions({
          ...currentSuggestions,
          generated_lessons: updatedLessons,
          suggestions_count: updatedLessons.length
        });
        setSuggestionsCount(updatedLessons.length);
      }
      
      alert('Custom lesson created successfully!');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const dismissSuggestion = async (lessonIndex: number) => {
    if (!currentSuggestions || !token) return;
    
    try {
      await fetch(`http://localhost:8000/api/lesson_suggestions/${currentSuggestions.id}/dismiss?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lesson_index: lessonIndex }),
      });
      
      // Remove the dismissed lesson from current suggestions and update count
      const updatedLessons = currentSuggestions.generated_lessons.filter((_, index) => index !== lessonIndex);
      if (updatedLessons.length === 0) {
        // All lessons dismissed, close modal
        setShowSuggestions(false);
        setCurrentSuggestions(null);
        setHasNotifications(false);
        setSuggestionsCount(0);
        setIsUnseen(false);
      } else {
        // Update current suggestions with remaining lessons
        setCurrentSuggestions({
          ...currentSuggestions,
          generated_lessons: updatedLessons,
          suggestions_count: updatedLessons.length
        });
        setSuggestionsCount(updatedLessons.length);
      }
    } catch (err) {
      console.error('Error dismissing suggestion:', err);
    }
  };

  const markSuggestionsAsSeen = async () => {
    if (!currentSuggestions || !token || !isUnseen) return;
    
    try {
      await fetch(`http://localhost:8000/api/lesson_suggestions/${currentSuggestions.id}/mark_seen?token=${token}`, {
        method: 'POST',
      });
      setIsUnseen(false); // Change notification from red to grey
    } catch (err) {
      console.error('Error marking suggestions as seen:', err);
    }
  };

  const dismissAllSuggestions = async () => {
    if (!currentSuggestions || !token) return;
    
    try {
      await fetch(`http://localhost:8000/api/lesson_suggestions/${currentSuggestions.id}/dismiss?token=${token}`, {
        method: 'POST',
      });
      setShowSuggestions(false);
      setCurrentSuggestions(null);
      setHasNotifications(false);
      setSuggestionsCount(0);
      setIsUnseen(false);
    } catch (err) {
      console.error('Error dismissing suggestions:', err);
    }
  };

  const closeSuggestionsModal = async () => {
    // Just close the modal and mark as seen if needed
    setShowSuggestions(false);
    if (isUnseen) {
      await markSuggestionsAsSeen();
    }
  };

  const refreshSuggestions = async () => {
    if (!token || !curriculumId) return;
    
    if (!confirm('This will generate new suggestions and count against your daily limit (3 per day). Continue?')) {
      return;
    }
    
    setRefreshing(true);
    try {
      const response = await fetch(`http://localhost:8000/api/lesson_suggestions/refresh?token=${token}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ curriculum_id: curriculumId }),
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(errorText);
      }
      
      const data = await response.json();
      
      if (data.has_suggestions) {
        setCurrentSuggestions({
          id: data.suggestion_id,
          suggestions_count: data.suggestion_count,
          generated_lessons: data.lessons,
          suggestion_data: data,
          created_at: new Date().toISOString()
        });
        setHasNotifications(true);
        setSuggestionsCount(data.suggestion_count);
        setIsUnseen(true); // New suggestions are always unseen
        setShowSuggestions(true);
      } else {
        alert(data.message || 'No new suggestions available');
        setHasNotifications(false);
        setSuggestionsCount(0);
        setIsUnseen(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setRefreshing(false);
    }
  };

  const showSuggestionsModal = () => {
    if (hasNotifications && currentSuggestions) {
      // Load cached suggestions instantly
      setShowSuggestions(true);
    } else if (hasNotifications) {
      // Generate suggestions if threshold is met but not cached
      generateSuggestions();
    } else {
      // Check for suggestions manually
      checkSuggestions();
    }
  };

  return (
    <>
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Custom Lessons</h3>
          <div className="flex gap-3">
            {/* Suggestion button with notification bubble */}
            <div className="flex gap-2">
              <div className="relative">
                <button
                  onClick={showSuggestionsModal}
                  disabled={loadingSuggestions}
                  className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed relative"
                >
                  {loadingSuggestions ? 'Loading...' : hasNotifications ? 'See Lesson Suggestions' : 'Check for Suggestions'}
                  {hasNotifications && (
                    <span className={`absolute -top-2 -right-2 ${isUnseen ? 'bg-red-500' : 'bg-gray-400'} text-white text-xs rounded-full w-5 h-5 flex items-center justify-center`}>
                      {suggestionsCount > 0 ? suggestionsCount : '!'}
                    </span>
                  )}
                </button>
              </div>
              {(hasNotifications || currentSuggestions) && (
                <button
                  onClick={refreshSuggestions}
                  disabled={refreshing || loadingSuggestions}
                  className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed text-sm"
                  title="Generate new suggestions (counts against daily limit)"
                >
                  {refreshing ? 'Refreshing...' : 'Refresh Lesson Suggestions'}
                </button>
              )}
            </div>

          </div>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          AI-generated lessons automatically suggested based on your conversation feedback and mistake patterns.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}
        
        {customLessons.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No custom lessons yet. Check lesson suggestions or have conversations to get AI-generated lessons based on your mistakes!
          </p>
        ) : (
          <div className="space-y-4">
            {customLessons.map((lesson) => (
              <div 
                key={lesson.id} 
                className="flex flex-col justify-between min-w-[320px] max-w-[340px] bg-white rounded-2xl shadow-lg border border-gray-100 p-0 overflow-hidden"
                style={{ boxShadow: '0 4px 24px 0 rgba(34, 197, 94, 0.08)' }}
              >
                {/* Top: Level & Difficulty + Delete Icon */}
                <div className="px-5 pt-4 pb-1 relative">
                  <div className="flex justify-between items-start">
                    <div className="flex items-center gap-2 text-xs text-gray-500 font-semibold mb-1">
                      <span className="px-2 py-1 bg-green-600 text-white text-xs rounded">CUSTOM</span>
                      <span>Level: {lesson.difficulty}</span>
                    </div>
                    <button
                      onClick={() => deleteCustomLesson(lesson.id)}
                      className="text-gray-400 hover:text-red-500 transition-colors"
                      title="Delete custom lesson"
                    >
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                  
                  {/* Title */}
                  <div className="text-xl font-bold text-gray-900 mb-2">
                    {lesson.title}
                  </div>
                </div>
                
                {/* Description */}
                <div className="px-5 pb-4 text-sm text-gray-700 flex-1">
                  {lesson.objectives}
                </div>
                
                {/* Bottom: Start Lesson Button */}
                <div className="px-5 h-16 flex items-center justify-end border-t border-gray-100 bg-green-50">
                  <button
                    onClick={() => startCustomLessonConversation(lesson.id)}
                    className="px-5 py-2 mx-2 rounded-lg bg-green-600 text-white font-semibold shadow hover:bg-green-700 transition-colors text-sm"
                  >
                    Start Practice
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>



      {/* Lesson Suggestions Modal */}
      {showSuggestions && currentSuggestions && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-xl font-bold text-gray-900">
                  Lesson Suggestions Based on Your Mistakes
                </h3>
                <button
                  onClick={closeSuggestionsModal}
                  className="text-gray-400 hover:text-gray-600"
                  title="Close (mark as seen)"
                >
                  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              <p className="text-gray-600 mb-6">
                We've analyzed your recent conversation mistakes and generated these targeted lessons to help you improve.
              </p>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {currentSuggestions.generated_lessons.map((lesson, index) => (
                  <div key={index} className="border border-gray-200 rounded-lg p-4 relative">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-1 bg-blue-600 text-white text-xs rounded">SUGGESTED</span>
                        <span className="text-xs text-gray-500">Level: {lesson.difficulty}</span>
                      </div>
                      <button
                        onClick={() => dismissSuggestion(index)}
                        className="text-gray-400 hover:text-red-500 transition-colors"
                        title="Dismiss this suggestion"
                      >
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                    
                    <h4 className="font-bold text-gray-900 mb-2">{lesson.title}</h4>
                    
                    {lesson.pattern_focus && (
                      <p className="text-xs text-red-600 mb-2">
                        <strong>Targets:</strong> {lesson.pattern_focus} ({lesson.pattern_frequency}x mistakes)
                      </p>
                    )}
                    
                    <p className="text-sm text-gray-700 mb-3">{lesson.objectives}</p>
                    
                    <details className="mb-4">
                      <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700 font-medium">
                        View Details
                      </summary>
                      <div className="mt-2 space-y-2 text-xs text-gray-600">
                        <div><strong>Content:</strong> {lesson.content}</div>
                        <div><strong>Cultural:</strong> {lesson.cultural_element}</div>
                        <div><strong>Practice:</strong> {lesson.practice_activity}</div>
                      </div>
                    </details>
                    
                    <button
                      onClick={() => useSuggestion(index)}
                      className="w-full px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-semibold"
                    >
                      Create This Lesson
                    </button>
                  </div>
                ))}
              </div>
              
              <div className="mt-6 flex justify-end gap-3">
                <button
                  onClick={dismissAllSuggestions}
                  className="px-4 py-2 text-gray-600 bg-gray-100 rounded hover:bg-gray-200"
                >
                  Dismiss All
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
} 