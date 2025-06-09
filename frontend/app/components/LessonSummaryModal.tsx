'use client';

import { Fragment, useState } from 'react';
import { Dialog, Transition } from '@headlessui/react';
import { XMarkIcon, TrophyIcon, StarIcon } from '@heroicons/react/24/solid';

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

interface LessonSummaryModalProps {
  isOpen: boolean;
  onClose: () => void;
  onReturnToDashboard: () => void;
  summaryData: LessonSummaryData | null;
  loading?: boolean;
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
  loading = false 
}: LessonSummaryModalProps) {
  const [currentView, setCurrentView] = useState<'achievements' | 'mistakes'>('achievements');

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
                          style={{ fontFamily: '"Press Start 2P", monospace' }}
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
                        <div className="text-2xl font-bold text-green-600">{summaryData.newVocabulary.length}</div>
                        <div className="text-sm text-gray-600 font-medium">New Vocabulary</div>
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
                                  className={`bg-white rounded-xl p-4 shadow-lg border-2 relative overflow-hidden ${
                                    achievement.type === 'new' 
                                      ? 'border-yellow-300 bg-gradient-to-r from-yellow-50 to-orange-50' 
                                      : achievement.type === 'improved'
                                      ? 'border-blue-300 bg-gradient-to-r from-blue-50 to-indigo-50'
                                      : 'border-purple-300 bg-gradient-to-r from-purple-50 to-pink-50'
                                  }`}
                                >
                                  {achievement.type === 'new' && (
                                    <div className="absolute top-2 right-2 bg-yellow-500 text-white text-xs font-bold px-2 py-1 rounded-full">
                                      NEW!
                                    </div>
                                  )}
                                  <div className="flex items-start space-x-3">
                                    <div className="text-3xl">{achievement.icon}</div>
                                    <div className="flex-1">
                                      <h4 className="font-bold text-gray-800">{achievement.title}</h4>
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
                    </div>

                    {/* Action Buttons */}
                    <div className="flex space-x-4">
                      <button
                        onClick={onReturnToDashboard}
                        className="flex-1 bg-orange-500 hover:bg-orange-600 text-white font-bold py-4 px-6 rounded-xl transition-colors shadow-lg border-2 border-orange-300"
                        style={{ 
                          fontFamily: '"Press Start 2P", monospace',
                          fontSize: '14px',
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