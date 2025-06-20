'use client';

import { Fragment, useState, useEffect } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon, TrophyIcon, StarIcon, ChatBubbleLeftRightIcon } from '@heroicons/react/24/solid';

interface Achievement {
  id: string;
  title: string;
  description: string;
  icon: string;
  type: 'new' | 'improved' | 'milestone';
  value?: string | number;
  verbs?: string[];  // List of verbs for verb-related achievements
  improved_verbs?: Array<{  // List of improved verbs with their new forms
    verb: string;
    new_forms: number;
    forms: string[];
  }>;
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

interface Mistake {
  category: string;
  type: string;
  error: string;
  correction: string;
  explanation: string;
  severity: string;
  languageFeatureTags?: string[];
}

interface ConversationMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  feedback?: Mistake[];
}

export interface LessonSummaryData {
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

interface LessonSummaryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onReturnToDashboard: () => void;
  summaryData: LessonSummaryData | null;
  loading?: boolean;
  token: string | null;
}

const severityColors = {
  minor: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  moderate: 'bg-orange-100 text-orange-800 border-orange-200',
  critical: 'bg-red-100 text-red-800 border-red-200'
};

export default function LessonSummaryModal({ 
  isOpen, 
  onClose, 
  onReturnToDashboard, 
  summaryData,
  loading = false,
  token
}: LessonSummaryModalProps) {
  const [currentView, setCurrentView] = useState<'achievements' | 'mistakes' | 'conversation' | 'verb-details' | 'improved-verbs'>('achievements');
  const [conversationData, setConversationData] = useState<ConversationMessage[]>([]);
  const [conversationLoading, setConversationLoading] = useState(false);
  const [conversationError, setConversationError] = useState<string | null>(null);
  const [selectedVerbAchievement, setSelectedVerbAchievement] = useState<Achievement | null>(null);

  // Clear conversation data when conversationId changes
  useEffect(() => {
    setConversationData([]);
    setConversationError(null);
  }, [summaryData?.conversationId]);

  // Clear conversation data when modal closes
  useEffect(() => {
    if (!isOpen) {
      setConversationData([]);
      setConversationError(null);
      setCurrentView('achievements'); // Reset to achievements view
      setSelectedVerbAchievement(null); // Clear selected verb achievement
    }
  }, [isOpen]);

  // Load conversation data when conversation tab is selected
  useEffect(() => {
    if (currentView === 'conversation' && summaryData?.conversationId && conversationData.length === 0) {
      loadConversationData();
    }
  }, [currentView, summaryData?.conversationId, conversationData.length]);

  const loadConversationData = async () => {
    if (!summaryData?.conversationId) return;

    setConversationLoading(true);
    setConversationError(null);

    try {
      if (!token) {
        throw new Error('No authentication token found');
      }

      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const url = `${API_BASE}/api/conversations/${summaryData.conversationId}/review?token=${encodeURIComponent(token)}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to load conversation: ${response.status}`);
      }

      const data = await response.json();
      
      // Merge feedback data with messages
      const messagesWithFeedback = (data.messages || []).map((message: { id: string; role: string; content: string; timestamp: string }) => {
        const feedback = data.feedback?.[message.id];
        return {
          ...message,
          feedback: feedback?.mistakes || []
        };
      });
      
      setConversationData(messagesWithFeedback);
    } catch (error) {
      console.error('Error loading conversation:', error);
      setConversationError(error instanceof Error ? error.message : 'Failed to load conversation');
    } finally {
      setConversationLoading(false);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      return new Date(timestamp).toLocaleTimeString([], { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    } catch {
      return '';
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity?.toLowerCase()) {
      case 'critical': return 'bg-red-100 text-red-800 border-red-200';
      case 'moderate': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'minor': return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const handleVerbAchievementClick = (achievement: Achievement) => {
    if (achievement.verbs && achievement.verbs.length > 0) {
      setSelectedVerbAchievement(achievement);
      setCurrentView('verb-details');
    } else if (achievement.improved_verbs && achievement.improved_verbs.length > 0) {
      setSelectedVerbAchievement(achievement);
      setCurrentView('improved-verbs');
    }
  };

  const backToAchievements = () => {
    setCurrentView('achievements');
    setSelectedVerbAchievement(null);
  };

  if (!summaryData && !loading) return null;



  return (
    <Transition appear show={isOpen} as={Fragment}>
      <Dialog as="div" className="relative z-50" onClose={onClose}>
        <Transition.Child
          as={Fragment}
          enter="ease-out duration-300"
          enterFrom="opacity-0"
          enterTo="opacity-100"
          leave="ease-in duration-200"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <div className="fixed inset-0 bg-black bg-opacity-50 backdrop-blur-sm" />
        </Transition.Child>

        <div className="fixed inset-0 overflow-y-auto">
          <div className="flex min-h-full items-center justify-center p-4 text-center">
            <Transition.Child
              as={Fragment}
              enter="ease-out duration-300"
              enterFrom="opacity-0 scale-95"
              enterTo="opacity-100 scale-100"
              leave="ease-in duration-200"
              leaveFrom="opacity-100 scale-100"
              leaveTo="opacity-0 scale-95"
            >
              <Dialog.Panel className="w-full max-w-4xl transform overflow-hidden rounded-3xl bg-gradient-to-br from-orange-50 via-white to-orange-100 p-8 text-left align-middle shadow-2xl transition-all border-4 border-orange-200">
                {loading ? (
                  <div className="flex flex-col items-center justify-center py-12">
                    <div className="animate-spin rounded-full h-12 w-12 border-t-4 border-b-4 border-orange-500 mb-4"></div>
                    <p className="text-lg font-semibold text-gray-700">Analyzing your lesson...</p>
                  </div>
                ) : summaryData && (
                  <>
                    {/* Header */}
                    <div className="flex justify-between items-start mb-6">
                      <div>
                        <Dialog.Title
                          as="h2"
                          className="text-3xl font-extrabold text-gray-900 mb-2"
                          style={{ fontFamily: '"Nunito Sans", sans-serif', fontWeight: 800 }}
                        >
                          🎉 Lesson Complete!
                        </Dialog.Title>
                        <p className="text-lg text-gray-700 font-semibold">
                          {summaryData.lessonTitle}
                        </p>
                      </div>
                      <button
                        type="button"
                        className="rounded-full bg-white p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 transition-colors border-2 border-gray-200"
                        onClick={onClose}
                      >
                        <XMarkIcon className="h-6 w-6" />
                      </button>
                    </div>

                    {/* Quick Stats */}
                    <div className="grid grid-cols-4 gap-4 mb-8">
                      <div className="bg-white rounded-xl p-4 shadow-lg border-2 border-orange-200 text-center">
                        <div className="text-2xl font-bold text-orange-600">{summaryData.totalTurns}</div>
                        <div className="text-sm text-gray-600 font-medium">Conversation Turns</div>
                      </div>
                      <div className="bg-white rounded-xl p-4 shadow-lg border-2 border-blue-200 text-center">
                        <div className="text-2xl font-bold text-blue-600">{summaryData.wordsUsed}</div>
                        <div className="text-sm text-gray-600 font-medium">Words Used</div>
                      </div>
                      <div className="bg-white rounded-xl p-4 shadow-lg border-2 border-green-200 text-center">
                        <div className="text-2xl font-bold text-green-600">#{summaryData.conversationCount}</div>
                        <div className="text-sm text-gray-600 font-medium">Conversation #</div>
                      </div>
                      <div className="bg-white rounded-xl p-4 shadow-lg border-2 border-purple-200 text-center">
                        <div className="text-2xl font-bold text-purple-600">{summaryData.conversationDuration}</div>
                        <div className="text-sm text-gray-600 font-medium">Duration</div>
                      </div>
                    </div>

                    {/* Tab Navigation */}
                    <div className="flex mb-6 bg-white rounded-xl p-1 border-2 border-orange-200">
                      <button
                        onClick={() => setCurrentView('achievements')}
                        className={`flex-1 py-3 px-4 rounded-lg font-semibold transition-all ${
                          currentView === 'achievements'
                            ? 'bg-orange-500 text-white shadow-lg'
                            : 'text-gray-600 hover:text-orange-600'
                        }`}
                      >
                        🏆 Achievements
                      </button>
                      <button
                        onClick={() => setCurrentView('mistakes')}
                        className={`flex-1 py-3 px-4 rounded-lg font-semibold transition-all ${
                          currentView === 'mistakes'
                            ? 'bg-orange-500 text-white shadow-lg'
                            : 'text-gray-600 hover:text-orange-600'
                        }`}
                      >
                        📚 Learning Areas
                      </button>
                      <button
                        onClick={() => setCurrentView('conversation')}
                        className={`flex-1 py-3 px-4 rounded-lg font-semibold transition-all ${
                          currentView === 'conversation'
                            ? 'bg-orange-500 text-white shadow-lg'
                            : 'text-gray-600 hover:text-orange-600'
                        }`}
                      >
                        💬 Conversation Review
                      </button>
                    </div>

                    {/* Content */}
                    <div className="min-h-[300px] mb-8">
                      {currentView === 'achievements' && (
                        <div>
                          <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                            <TrophyIcon className="h-6 w-6 text-yellow-500 mr-2" />
                            Your Achievements
                          </h3>
                          {summaryData.achievements.length > 0 ? (
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                              {summaryData.achievements.map((achievement) => (
                                <div
                                  key={achievement.id}
                                  onClick={() => handleVerbAchievementClick(achievement)}
                                  className={`bg-white rounded-xl p-4 shadow-lg border-2 relative overflow-hidden transition-all ${
                                    achievement.type === 'new' 
                                      ? 'border-yellow-300 bg-gradient-to-r from-yellow-50 to-orange-50' 
                                      : achievement.type === 'improved'
                                      ? 'border-blue-300 bg-gradient-to-r from-blue-50 to-indigo-50'
                                      : 'border-purple-300 bg-gradient-to-r from-purple-50 to-pink-50'
                                  } ${
                                    ((achievement.verbs && achievement.verbs.length > 0) || 
                                     (achievement.improved_verbs && achievement.improved_verbs.length > 0))
                                      ? 'cursor-pointer hover:scale-105 hover:shadow-xl' 
                                      : ''
                                  }`}
                                >

                                  <div className="flex items-start space-x-3">
                                    <div className="text-3xl">{achievement.icon}</div>
                                    <div className="flex-1">
                                      <h4 className="font-bold text-gray-800 flex items-center">
                                        {achievement.title}
                                        {((achievement.verbs && achievement.verbs.length > 0) || 
                                          (achievement.improved_verbs && achievement.improved_verbs.length > 0)) && (
                                          <span className="ml-2 text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded-full">
                                            Click for details
                                          </span>
                                        )}
                                      </h4>
                                      <p className="text-sm text-gray-600 mb-1">{achievement.description}</p>
                                      {achievement.value && (
                                        <div className="text-lg font-semibold text-orange-600">
                                          {achievement.value}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-center py-12 text-gray-500">
                              <TrophyIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                              <p>Keep practicing to unlock achievements!</p>
                            </div>
                          )}
                        </div>
                      )}

                      {currentView === 'mistakes' && (
                        <div>
                          <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                            <StarIcon className="h-6 w-6 text-blue-500 mr-2" />
                            Areas for Improvement
                          </h3>
                          {summaryData.mistakesByCategory.length > 0 ? (
                            <div className="space-y-4">
                              {summaryData.mistakesByCategory.map((category, index) => (
                                <div
                                  key={index}
                                  className="bg-white rounded-xl p-4 shadow-lg border-2 border-gray-200"
                                >
                                  <div className="flex items-center justify-between mb-3">
                                    <h4 className="font-bold text-gray-800 capitalize flex items-center">
                                      <span className="mr-2">{category.category === 'grammar' ? '📚' : category.category === 'vocabulary' ? '🗣️' : '✏️'}</span>
                                      {category.category}
                                    </h4>
                                    <span className={`px-3 py-1 rounded-full text-sm font-semibold border ${severityColors[category.severity]}`}>
                                      {category.count} {category.count === 1 ? 'correction' : 'corrections'}
                                    </span>
                                  </div>
                                  <div className="space-y-2">
                                    {category.examples.slice(0, 2).map((example, exIndex) => (
                                      <div key={exIndex} className="bg-gray-50 rounded-lg p-3 border">
                                        <div className="text-sm">
                                          <span className="line-through text-red-600">{example.error}</span>
                                          <span className="mx-2">→</span>
                                          <span className="text-green-600 font-semibold">{example.correction}</span>
                                        </div>
                                        <p className="text-xs text-gray-600 mt-1">{example.explanation}</p>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <div className="text-center py-12 text-green-600">
                              <StarIcon className="h-16 w-16 mx-auto mb-4 text-green-400" />
                              <p className="font-semibold">Perfect lesson! No corrections needed.</p>
                            </div>
                          )}
                        </div>
                      )}

                      {currentView === 'verb-details' && selectedVerbAchievement && (
                        <div>
                          <div className="flex items-center justify-between mb-6">
                            <h3 className="text-xl font-bold text-gray-800 flex items-center">
                              <span className="text-2xl mr-2">{selectedVerbAchievement.icon}</span>
                              {selectedVerbAchievement.title}
                            </h3>
                            <button
                              onClick={backToAchievements}
                              className="text-gray-500 hover:text-gray-700 px-3 py-1 rounded-md border border-gray-300 hover:bg-gray-50 text-sm"
                            >
                              ← Back to Report Card
                            </button>
                          </div>
                          
                          <div className="bg-white rounded-xl border-2 border-gray-200 p-4">
                            <p className="text-sm text-gray-600 mb-4">{selectedVerbAchievement.description}</p>
                            <div className="space-y-3">
                              <h4 className="font-semibold text-gray-800 mb-3">All verbs you used for the first time:</h4>
                              <div className="grid grid-cols-2 md:grid-cols-3 gap-2 max-h-80 overflow-y-auto">
                                {selectedVerbAchievement.verbs?.map((verb, index) => (
                                  <div
                                    key={index}
                                    className="bg-gradient-to-r from-orange-50 to-yellow-50 border border-orange-200 rounded-lg px-3 py-2 text-center hover:shadow-md transition-shadow"
                                  >
                                    <span className="font-medium text-orange-800">{verb}</span>
                                  </div>
                                ))}
                              </div>
                              <div className="mt-4 text-center">
                                <p className="text-sm text-gray-500">
                                  🎉 You successfully used <strong>{selectedVerbAchievement.verbs?.length}</strong> new verbs in this conversation!
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {currentView === 'improved-verbs' && selectedVerbAchievement && (
                        <div>
                          <div className="flex items-center justify-between mb-6">
                            <h3 className="text-xl font-bold text-gray-800 flex items-center">
                              <span className="text-2xl mr-2">{selectedVerbAchievement.icon}</span>
                              {selectedVerbAchievement.title}
                            </h3>
                            <button
                              onClick={backToAchievements}
                              className="text-gray-500 hover:text-gray-700 px-3 py-1 rounded-md border border-gray-300 hover:bg-gray-50 text-sm"
                            >
                              ← Back to Report Card
                            </button>
                          </div>
                          
                          <div className="bg-white rounded-xl border-2 border-gray-200 p-4">
                            <p className="text-sm text-gray-600 mb-4">{selectedVerbAchievement.description}</p>
                            <div className="space-y-4">
                              <h4 className="font-semibold text-gray-800 mb-3">Verbs with new forms mastered:</h4>
                              <div className="space-y-3 max-h-80 overflow-y-auto">
                                {selectedVerbAchievement.improved_verbs?.map((improvedVerb, index) => (
                                  <div
                                    key={index}
                                    className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4"
                                  >
                                    <div className="flex items-center justify-between mb-2">
                                      <h5 className="font-bold text-blue-800 text-lg">{improvedVerb.verb}</h5>
                                      <span className="bg-blue-100 text-blue-600 px-2 py-1 rounded-full text-xs font-semibold">
                                        +{improvedVerb.new_forms} new form{improvedVerb.new_forms !== 1 ? 's' : ''}
                                      </span>
                                    </div>
                                    <div className="text-sm text-gray-600">
                                      <span className="font-medium">New forms practiced: </span>
                                      <span className="italic">{improvedVerb.forms.join(', ')}</span>
                                    </div>
                                  </div>
                                ))}
                              </div>
                              <div className="mt-4 text-center">
                                <p className="text-sm text-gray-500">
                                  📈 You expanded your knowledge of <strong>{selectedVerbAchievement.improved_verbs?.length}</strong> verbs with <strong>{selectedVerbAchievement.value}</strong> new forms!
                                </p>
                              </div>
                            </div>
                          </div>
                        </div>
                      )}

                      {currentView === 'conversation' && (
                        <div>
                          <h3 className="text-xl font-bold text-gray-800 mb-4 flex items-center">
                            <ChatBubbleLeftRightIcon className="h-6 w-6 text-orange-500 mr-2" />
                            Conversation Review
                          </h3>
                          
                          {conversationLoading ? (
                            <div className="flex flex-col items-center justify-center py-12">
                              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-orange-500 mb-4"></div>
                              <p className="text-gray-600">Loading conversation...</p>
                            </div>
                          ) : conversationError ? (
                            <div className="text-center py-12">
                              <div className="text-red-500 mb-4">
                                <ChatBubbleLeftRightIcon className="h-16 w-16 mx-auto mb-2 text-red-300" />
                                <p className="font-semibold">Unable to load conversation</p>
                                <p className="text-sm text-gray-600 mt-1">{conversationError}</p>
                              </div>
                              <button
                                onClick={loadConversationData}
                                className="px-4 py-2 bg-orange-500 text-white rounded-lg hover:bg-orange-600 transition-colors"
                              >
                                Try Again
                              </button>
                            </div>
                          ) : conversationData.length === 0 ? (
                            <div className="text-center py-12 text-gray-500">
                              <ChatBubbleLeftRightIcon className="h-16 w-16 mx-auto mb-4 text-gray-300" />
                              <p>No conversation history available for this lesson.</p>
                            </div>
                          ) : (
                            <div className="bg-white rounded-xl border-2 border-gray-200 max-h-96 overflow-y-auto">
                              <div className="p-4 space-y-4">
                                {conversationData.map((message) => (
                                  <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                    <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                                      message.role === 'user' 
                                        ? 'bg-orange-500 text-white' 
                                        : 'bg-gray-200 text-gray-800'
                                    }`}>
                                      <div className="text-sm">{message.content}</div>
                                      {message.timestamp && (
                                        <div className={`text-xs mt-1 ${
                                          message.role === 'user' ? 'text-orange-100' : 'text-gray-500'
                                        }`}>
                                          {formatTimestamp(message.timestamp)}
                                        </div>
                                      )}
                                      
                                      {/* Feedback for user messages */}
                                      {message.role === 'user' && message.feedback && message.feedback.length > 0 && (
                                        <div className="mt-3 space-y-2">
                                          {message.feedback.map((mistake, index) => (
                                            <div key={index} className="bg-white rounded-lg p-3 text-gray-800 shadow-sm">
                                              <div className="flex items-center justify-between mb-2">
                                                <span className="text-xs font-semibold text-gray-600 uppercase">
                                                  {mistake.category} - {mistake.type}
                                                </span>
                                                <span className={`px-2 py-1 rounded-full text-xs font-semibold ${getSeverityColor(mistake.severity)}`}>
                                                  {mistake.severity}
                                                </span>
                                              </div>
                                              <div className="text-sm mb-2">
                                                <span className="line-through text-red-600">{mistake.error}</span>
                                                <span className="mx-2">→</span>
                                                <span className="text-green-600 font-semibold">{mistake.correction}</span>
                                              </div>
                                              <p className="text-xs text-gray-600 mb-2">{mistake.explanation}</p>
                                              {mistake.languageFeatureTags && mistake.languageFeatureTags.length > 0 && (
                                                <div className="flex flex-wrap gap-1">
                                                  {mistake.languageFeatureTags.map((tag, tagIndex) => (
                                                    <span key={tagIndex} className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded-full">
                                                      {tag}
                                                    </span>
                                                  ))}
                                                </div>
                                              )}
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>

                    {/* Action Buttons */}
                    <div className="flex space-x-4">
                      <button
                        onClick={onReturnToDashboard}
                        className="flex-1 bg-orange-500 hover:bg-orange-600 text-white font-bold py-4 px-6 rounded-xl transition-colors shadow-lg border-2 border-orange-300"
                        style={{ 
                          fontFamily: '"Nunito Sans", sans-serif',
                          fontSize: '14px',
                          fontWeight: 700,
                          textShadow: '1px 1px 0 #fb8c00'
                        }}
                      >
                        🏠 Back to Dashboard
                      </button>
                      <button
                        onClick={onClose}
                        className="px-6 py-4 bg-gray-200 hover:bg-gray-300 text-gray-700 font-semibold rounded-xl transition-colors border-2 border-gray-300"
                      >
                        Close
                      </button>
                    </div>
                  </>
                )}
              </Dialog.Panel>
            </Transition.Child>
          </div>
        </div>
      </Dialog>


    </Transition>
  );
} 