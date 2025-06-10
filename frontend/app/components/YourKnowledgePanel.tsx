import React, { useEffect, useState } from 'react';
import { supabase } from '../../supabaseClient';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

// Helper to rank verbs by strength
function rankVerbs(verbs: Record<string, Record<string, string[]>>) {
  // Score = number of tenses * number of unique persons
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
  'nouns',
  'pronouns',
  'adjectives',
  'verbs',
  'adverbs',
  'prepositions',
  'conjunctions',
  'articles',
  'interjections',
];

// CEFR next-level targets for each part of speech
const NEXT_LEVEL_TARGETS: Record<string, Record<string, number>> = {
  'A1': { nouns: 100, verbs: 60, adjectives: 30, adverbs: 20, prepositions: 20, conjunctions: 10, interjections: 10 },
  'A2': { nouns: 250, verbs: 120, adjectives: 60, adverbs: 40, prepositions: 30, conjunctions: 15, interjections: 15 },
  'B1': { nouns: 400, verbs: 200, adjectives: 100, adverbs: 60, prepositions: 40, conjunctions: 20, interjections: 20 },
  'B2': { nouns: 600, verbs: 300, adjectives: 150, adverbs: 80, prepositions: 50, conjunctions: 25, interjections: 25 },
  'C1': { nouns: 800, verbs: 400, adjectives: 200, adverbs: 100, prepositions: 60, conjunctions: 30, interjections: 30 },
  'C2': { nouns: 1000, verbs: 500, adjectives: 250, adverbs: 120, prepositions: 70, conjunctions: 35, interjections: 35 },
};

function getNextLevel(level: string) {
  const order = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
  const idx = order.indexOf(level);
  return idx >= 0 && idx < order.length - 1 ? order[idx + 1] : 'C2';
}

interface Props {
  language: string;
  level: string;
  refreshTrigger?: number;
}

export default function YourKnowledgePanel({ language, level, refreshTrigger }: Props) {
  const [knowledge, setKnowledge] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastFetch, setLastFetch] = useState<Date | null>(null);

  const nextLevel = getNextLevel(level);
  const targets = NEXT_LEVEL_TARGETS[nextLevel] || {};
  const progressParts = ['nouns', 'verbs', 'adjectives', 'adverbs', 'prepositions', 'conjunctions', 'interjections'];

  // Get JWT from supabase
  async function getToken() {
    const { data } = await supabase.auth.getSession();
    return data?.session?.access_token;
  }

  async function fetchKnowledge() {
    setLoading(true);
    setError(null);
    const token = await getToken();
    if (!token) {
      setError('Not authenticated');
      setLoading(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/user_knowledge?language=${language}&token=${token}`);
      const data = await res.json();
      setKnowledge(data.knowledge);
      setLastFetch(new Date());
    } catch (e) {
      setError('Failed to fetch knowledge data');
    } finally {
      setLoading(false);
    }
  }

  async function refreshKnowledge() {
    setRefreshing(true);
    setError(null);
    const token = await getToken();
    if (!token) {
      setError('Not authenticated');
      setRefreshing(false);
      return;
    }
    try {
      // First trigger an incremental update
      const updateRes = await fetch(`${API_BASE}/api/user_knowledge/update?language=${language}&token=${token}`, { method: 'POST' });
      const updateData = await updateRes.json();
      
      if (updateData.updated && updateData.knowledge) {
        setKnowledge(updateData.knowledge);
        setLastFetch(new Date());
      } else {
        // If no update needed, just fetch current data
        await fetchKnowledge();
      }
    } catch (e) {
      setError('Failed to refresh knowledge data');
    } finally {
      setRefreshing(false);
    }
  }

  async function generateKnowledge() {
    setGenerating(true);
    setError(null);
    const token = await getToken();
    if (!token) {
      setError('Not authenticated');
      setGenerating(false);
      return;
    }
    try {
      const res = await fetch(`${API_BASE}/api/user_knowledge?language=${language}&token=${token}`, { method: 'POST' });
      const data = await res.json();
      if (data.knowledge) {
        setKnowledge(data.knowledge);
        setLastFetch(new Date());
      } else {
        setError(data.error || 'Failed to generate knowledge report');
      }
    } catch (e) {
      setError('Failed to generate knowledge report');
    } finally {
      setGenerating(false);
    }
  }

  useEffect(() => {
    fetchKnowledge();
    // eslint-disable-next-line
  }, [language]);

  // Trigger refresh when refreshTrigger changes
  useEffect(() => {
    if (refreshTrigger && refreshTrigger > 0 && knowledge) {
      refreshKnowledge();
    }
    // eslint-disable-next-line
  }, [refreshTrigger]);

  // Auto-refresh knowledge when user returns to the dashboard
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden && lastFetch && knowledge) {
        const timeSinceLastFetch = Date.now() - lastFetch.getTime();
        // Auto-refresh if it's been more than 2 minutes since last fetch
        if (timeSinceLastFetch > 2 * 60 * 1000) {
          refreshKnowledge();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, [lastFetch, knowledge]);

  if (loading) return <div className="p-8">Loading...</div>;

  return (
    <>
      <div className="bg-gray-50 rounded-lg shadow p-6 mb-6 h-[400px] flex flex-col justify-between">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-xl font-semibold">Your Knowledge</h3>
          {knowledge && (
            <button
              className="px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600 disabled:opacity-50 transition-colors"
              onClick={refreshKnowledge}
              disabled={refreshing || loading}
              title="Refresh with latest conversation data"
            >
              {refreshing ? '🔄' : '↻'} Refresh
            </button>
          )}
        </div>
        {error && <div className="text-red-500 mb-4">{error}</div>}
        {!knowledge && (
          <div className="mb-6">
            <button
              className="px-4 py-2 bg-orange-500 text-white rounded font-semibold hover:bg-orange-600 disabled:opacity-50"
              onClick={generateKnowledge}
              disabled={generating}
            >
              {generating ? 'Generating...' : 'Generate Knowledge Report'}
            </button>
          </div>
        )}
        {knowledge && (
          <div className="grid grid-cols-2 gap-4 overflow-y-auto" style={{ maxHeight: '300px' }}>
            {PARTS.map(part => {
              let value = part === 'verbs'
                ? Object.keys(knowledge[part] || {}).length
                : knowledge[part] ? knowledge[part].length : 0;
              let showProgress = progressParts.includes(part);
              let target = targets[part] || 1;
              let percent = Math.min(value / target, 1);
              return (
                <div key={part} className="bg-gray-100 rounded p-4 flex flex-col justify-between h-full">
                  <div>
                    <div className="font-medium capitalize">{part}</div>
                    <div className="text-2xl font-bold">{value}</div>
                  </div>
                  {showProgress && (
                    <div className="mt-3">
                      <div className="w-full h-2 bg-orange-100 rounded-full overflow-hidden">
                        <div
                          className="h-2 rounded-full transition-all"
                          style={{
                            width: `${percent * 100}%`,
                            background: `linear-gradient(90deg, #fb923c, #f59e42)`,
                            opacity: percent < 0.15 ? 0.3 : percent < 0.5 ? 0.6 : 1
                          }}
                        />
                      </div>
                      <div className="text-xs text-gray-500 mt-1">{Math.round(percent * 100)}% to {nextLevel} target ({target})</div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
      <div className="bg-gray-50 rounded-lg shadow p-6 h-[400px] flex flex-col">
        <div className="flex justify-between items-center mb-2">
          <h4 className="text-lg font-semibold">Verb Strength Ranking</h4>
          {lastFetch && (
            <div className="text-xs text-gray-500">
              Updated: {lastFetch.toLocaleTimeString()}
            </div>
          )}
        </div>
        {knowledge && (
          <div className="overflow-y-auto" style={{ maxHeight: '300px' }}>
            <table className="w-full text-left border">
              <thead>
                <tr className="bg-gray-200">
                  <th className="p-2">Verb</th>
                  <th className="p-2"># Tenses</th>
                  <th className="p-2"># Persons</th>
                  <th className="p-2">Score</th>
                  <th className="p-2">Tenses Used</th>
                </tr>
              </thead>
              <tbody>
                {rankVerbs(knowledge.verbs || {}).map(v => (
                  <tr key={v.lemma}>
                    <td className="p-2 font-mono">{v.lemma}</td>
                    <td className="p-2">{v.tenseCount}</td>
                    <td className="p-2">{v.personCount}</td>
                    <td className="p-2">{v.score}</td>
                    <td className="p-2">
                      {Object.entries(v.tenses).map(([tense, persons]) => (
                        <div key={tense}>
                          <span className="font-semibold">{tense}:</span> {persons.join(', ')}
                        </div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
} 