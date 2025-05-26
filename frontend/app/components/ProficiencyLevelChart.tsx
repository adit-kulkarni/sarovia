'use client';

import { Mistake } from '../types/feedback';
import { useEffect, useState } from 'react';

interface ProficiencyLevelChartProps {
  mistakes: Mistake[];
  originalMessages: string[];
}

interface VocabularyMetrics {
  uniqueVerbs: number;
  uniqueNouns: number;
  uniqueAdjectives: number;
  averageWordLength: number;
  complexSentences: number;
  totalWords: number;
}

interface LevelThreshold {
  level: string;
  minVerbs: number;
  minNouns: number;
  minAdjectives: number;
  minComplexSentences: number;
}

const LEVEL_THRESHOLDS: LevelThreshold[] = [
  { level: 'A0', minVerbs: 0, minNouns: 0, minAdjectives: 0, minComplexSentences: 0 },
  { level: 'A1', minVerbs: 20, minNouns: 50, minAdjectives: 20, minComplexSentences: 5 },
  { level: 'A2', minVerbs: 50, minNouns: 100, minAdjectives: 50, minComplexSentences: 15 },
  { level: 'B1', minVerbs: 100, minNouns: 200, minAdjectives: 100, minComplexSentences: 30 },
  { level: 'B2', minVerbs: 200, minNouns: 400, minAdjectives: 200, minComplexSentences: 60 },
  { level: 'C1', minVerbs: 300, minNouns: 600, minAdjectives: 300, minComplexSentences: 100 },
  { level: 'C2', minVerbs: 400, minNouns: 800, minAdjectives: 400, minComplexSentences: 150 },
];

export default function ProficiencyLevelChart({ mistakes, originalMessages }: ProficiencyLevelChartProps) {
  const [metrics, setMetrics] = useState<VocabularyMetrics>({
    uniqueVerbs: 0,
    uniqueNouns: 0,
    uniqueAdjectives: 0,
    averageWordLength: 0,
    complexSentences: 0,
    totalWords: 0,
  });

  const [currentLevel, setCurrentLevel] = useState<string>('A0');
  const [nextLevel, setNextLevel] = useState<string>('A1');
  const [progress, setProgress] = useState<number>(0);

  useEffect(() => {
    // Analyze vocabulary depth from original messages
    const analyzeVocabulary = () => {
      const uniqueVerbs = new Set<string>();
      const uniqueNouns = new Set<string>();
      const uniqueAdjectives = new Set<string>();
      let totalWordLength = 0;
      let wordCount = 0;
      let complexSentenceCount = 0;

      originalMessages.forEach(message => {
        if (typeof message !== 'string' || !message.trim()) return;
        // Simple word analysis (in a real app, this would use NLP)
        const words = message.toLowerCase().split(/\s+/);
        words.forEach(word => {
          // This is a simplified example - in reality, you'd use proper NLP
          if (word.endsWith('ar') || word.endsWith('er') || word.endsWith('ir')) {
            uniqueVerbs.add(word);
          } else if (word.endsWith('o') || word.endsWith('a')) {
            uniqueNouns.add(word);
          } else if (word.endsWith('e') || word.endsWith('is')) {
            uniqueAdjectives.add(word);
          }
          totalWordLength += word.length;
          wordCount++;
        });

        // Count complex sentences (sentences with multiple clauses)
        if (message.includes(',') || message.includes(';')) {
          complexSentenceCount++;
        }
      });

      const newMetrics = {
        uniqueVerbs: uniqueVerbs.size,
        uniqueNouns: uniqueNouns.size,
        uniqueAdjectives: uniqueAdjectives.size,
        averageWordLength: wordCount > 0 ? totalWordLength / wordCount : 0,
        complexSentences: complexSentenceCount,
        totalWords: wordCount,
      };

      setMetrics(newMetrics);
      calculateLevel(newMetrics);
    };

    analyzeVocabulary();
  }, [originalMessages]);

  const calculateLevel = (metrics: VocabularyMetrics) => {
    // Find current level and next level
    let currentLevelIndex = 0;
    for (let i = LEVEL_THRESHOLDS.length - 1; i >= 0; i--) {
      const threshold = LEVEL_THRESHOLDS[i];
      if (
        metrics.uniqueVerbs >= threshold.minVerbs &&
        metrics.uniqueNouns >= threshold.minNouns &&
        metrics.uniqueAdjectives >= threshold.minAdjectives &&
        metrics.complexSentences >= threshold.minComplexSentences
      ) {
        currentLevelIndex = i;
        break;
      }
    }

    setCurrentLevel(LEVEL_THRESHOLDS[currentLevelIndex].level);
    setNextLevel(LEVEL_THRESHOLDS[Math.min(currentLevelIndex + 1, LEVEL_THRESHOLDS.length - 1)].level);

    // Calculate progress to next level
    const currentThreshold = LEVEL_THRESHOLDS[currentLevelIndex];
    const nextThreshold = LEVEL_THRESHOLDS[Math.min(currentLevelIndex + 1, LEVEL_THRESHOLDS.length - 1)];

    const verbProgress = (metrics.uniqueVerbs - currentThreshold.minVerbs) / 
      (nextThreshold.minVerbs - currentThreshold.minVerbs);
    const nounProgress = (metrics.uniqueNouns - currentThreshold.minNouns) / 
      (nextThreshold.minNouns - currentThreshold.minNouns);
    const adjProgress = (metrics.uniqueAdjectives - currentThreshold.minAdjectives) / 
      (nextThreshold.minAdjectives - currentThreshold.minAdjectives);
    const sentenceProgress = (metrics.complexSentences - currentThreshold.minComplexSentences) / 
      (nextThreshold.minComplexSentences - currentThreshold.minComplexSentences);

    const overallProgress = Math.min(100, Math.max(0, 
      (verbProgress + nounProgress + adjProgress + sentenceProgress) * 25
    ));

    setProgress(overallProgress);
  };

  return (
    <div className="space-y-6">
      {/* Current Level Display */}
      <div className="text-center">
        <div className="text-4xl font-bold text-orange-500 mb-2">{currentLevel}</div>
        <div className="text-sm text-gray-500">Current Proficiency Level</div>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm">
          <span className="text-gray-600">Progress to {nextLevel}</span>
          <span className="text-gray-600">{Math.round(progress)}%</span>
        </div>
        <div className="h-4 bg-gray-200 rounded-full overflow-hidden">
          <div 
            className="h-full bg-orange-500 transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <div className="text-sm text-gray-500">Unique Verbs</div>
          <div className="text-2xl font-bold text-gray-900">{metrics.uniqueVerbs}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <div className="text-sm text-gray-500">Unique Nouns</div>
          <div className="text-2xl font-bold text-gray-900">{metrics.uniqueNouns}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <div className="text-sm text-gray-500">Unique Adjectives</div>
          <div className="text-2xl font-bold text-gray-900">{metrics.uniqueAdjectives}</div>
        </div>
        <div className="bg-white p-4 rounded-lg border border-gray-200">
          <div className="text-sm text-gray-500">Complex Sentences</div>
          <div className="text-2xl font-bold text-gray-900">{metrics.complexSentences}</div>
        </div>
      </div>

      {/* Next Level Requirements */}
      <div className="bg-gray-50 p-4 rounded-lg">
        <h4 className="text-sm font-medium text-gray-700 mb-2">Requirements for {nextLevel}</h4>
        <div className="space-y-2">
          {LEVEL_THRESHOLDS.find(t => t.level === nextLevel) && (
            <>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Verbs</span>
                <span className="text-gray-900">{metrics.uniqueVerbs} / {LEVEL_THRESHOLDS.find(t => t.level === nextLevel)?.minVerbs}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Nouns</span>
                <span className="text-gray-900">{metrics.uniqueNouns} / {LEVEL_THRESHOLDS.find(t => t.level === nextLevel)?.minNouns}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Adjectives</span>
                <span className="text-gray-900">{metrics.uniqueAdjectives} / {LEVEL_THRESHOLDS.find(t => t.level === nextLevel)?.minAdjectives}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Complex Sentences</span>
                <span className="text-gray-900">{metrics.complexSentences} / {LEVEL_THRESHOLDS.find(t => t.level === nextLevel)?.minComplexSentences}</span>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
} 