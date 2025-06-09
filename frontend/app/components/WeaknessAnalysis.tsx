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
}

interface WeaknessAnalysisProps {
  curriculumId: string;
  language: string;
  token: string;
}

export default function WeaknessAnalysis({ curriculumId, language, token }: WeaknessAnalysisProps) {
  const [customLessons, setCustomLessons] = useState<CustomLesson[]>([]);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewLesson, setPreviewLesson] = useState<CustomLesson | null>(null);
  const [showPreviewModal, setShowPreviewModal] = useState(false);

  const router = useRouter();

  useEffect(() => {
    loadCustomLessons();
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

  const generateCustomLesson = async () => {
    console.log('[WeaknessAnalysis] Generate button clicked!');
    console.log('[WeaknessAnalysis] token:', token ? 'present' : 'missing');
    console.log('[WeaknessAnalysis] curriculumId:', curriculumId);
    
    if (!token || !curriculumId) {
      console.log('[WeaknessAnalysis] Missing token or curriculumId, returning early');
      setError('Missing authentication token or curriculum ID');
      return;
    }
    
    setGenerating(true);
    setError(null);
    console.log('[WeaknessAnalysis] Starting generation...');
    
    try {
      console.log('[WeaknessAnalysis] Generating custom lesson...');
      const url = `http://localhost:8000/api/generate_custom_lesson?token=${token}`;
      console.log('[WeaknessAnalysis] Making request to:', url);
      
      const response = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          curriculum_id: curriculumId,
          weakness_patterns: [], // Let the backend analyze and find patterns
        }),
      });
      
      console.log('[WeaknessAnalysis] Response status:', response.status);
      console.log('[WeaknessAnalysis] Response ok:', response.ok);
      
      if (!response.ok) {
        const errorText = await response.text();
        console.error('[WeaknessAnalysis] Error response:', errorText);
        throw new Error(`Failed to generate custom lesson: ${response.status} ${errorText}`);
      }
      
      const newLesson = await response.json();
      console.log('[WeaknessAnalysis] Generated lesson:', newLesson);
      
      // Show preview modal instead of directly adding to list
      setPreviewLesson(newLesson);
      setShowPreviewModal(true);
      console.log('[WeaknessAnalysis] Modal should be showing now');
      
    } catch (err) {
      console.error('[WeaknessAnalysis] Error during lesson generation:', err);
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setGenerating(false);
      console.log('[WeaknessAnalysis] Generation complete, generating state reset');
    }
  };

  const savePreviewedLesson = async () => {
    if (!previewLesson || !token) return;
    
    try {
      const response = await fetch(`http://localhost:8000/api/save_custom_lesson?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(previewLesson),
      });
      
      if (!response.ok) {
        throw new Error('Failed to save custom lesson');
      }
      
      const savedLesson = await response.json();
      setCustomLessons(prev => [savedLesson, ...prev]);
      setShowPreviewModal(false);
      setPreviewLesson(null);
      alert('Custom lesson saved successfully!');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    }
  };

  const cancelPreview = () => {
    setShowPreviewModal(false);
    setPreviewLesson(null);
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

  return (
    <>
      <div className="bg-white rounded-lg shadow p-6">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-medium text-gray-900">Custom Lessons</h3>
          <button
            onClick={generateCustomLesson}
            disabled={generating}
            className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {generating ? 'Generating...' : 'Generate Custom Lesson'}
          </button>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          AI-generated lessons based on your conversation feedback and most common mistake patterns.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-red-700 text-sm">
            {error}
          </div>
        )}
        
        {customLessons.length === 0 ? (
          <p className="text-gray-500 text-center py-8">
            No custom lessons yet. Click "Generate Custom Lesson" to create one based on your feedback data!
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

      {/* Lesson Preview Modal */}
      {showPreviewModal && previewLesson && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
          <div 
            className="flex flex-col justify-between max-w-[340px] w-full bg-white rounded-2xl shadow-lg border border-gray-100 p-0 overflow-hidden"
            style={{ boxShadow: '0 4px 24px 0 rgba(34, 197, 94, 0.15)' }}
          >
            {/* Top: Level & Difficulty + Close Icon */}
            <div className="px-5 pt-4 pb-1 relative">
              <div className="flex justify-between items-start">
                <div className="flex items-center gap-2 text-xs text-gray-500 font-semibold mb-1">
                  <span className="px-2 py-1 bg-green-600 text-white text-xs rounded">CUSTOM</span>
                  <span>Level: {previewLesson.difficulty}</span>
                </div>
                <button
                  onClick={cancelPreview}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                  title="Close preview"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
              
              {/* Title */}
              <div className="text-xl font-bold text-gray-900 mb-2">
                {previewLesson.title}
              </div>
            </div>

            {/* Description */}
            <div className="px-5 pb-4 text-sm text-gray-700 flex-1">
              {previewLesson.objectives}
              
              {/* Additional details (collapsible/expandable) */}
              <div className="mt-3 pt-3 border-t border-gray-100">
                <details className="group">
                  <summary className="cursor-pointer text-xs text-gray-500 hover:text-gray-700 font-medium">
                    View Details
                  </summary>
                  <div className="mt-2 space-y-2 text-xs text-gray-600">
                    <div><strong>Content:</strong> {previewLesson.content}</div>
                    <div><strong>Cultural:</strong> {previewLesson.cultural_element}</div>
                    <div><strong>Practice:</strong> {previewLesson.practice_activity}</div>
                    {previewLesson.targeted_weaknesses.length > 0 && (
                      <div>
                        <strong>Targets:</strong> {previewLesson.targeted_weaknesses.join(', ')}
                      </div>
                    )}
                  </div>
                </details>
              </div>
            </div>

            {/* Footer - matches lesson template style with green accent */}
            <div className="px-5 h-16 flex items-center justify-end border-t border-gray-100 bg-green-50">
              <button
                onClick={cancelPreview}
                className="px-4 py-2 text-gray-600 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 mr-3 text-sm font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={savePreviewedLesson}
                className="px-5 py-2 bg-green-600 text-white rounded-lg font-semibold shadow hover:bg-green-700 transition-colors text-sm"
              >
                Save Lesson
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
} 