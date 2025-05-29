import React, { useEffect, useState } from 'react';

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

export default function ProgressPage() {
  const [knowledge, setKnowledge] = useState<any>(null);
  const [language, setLanguage] = useState('en'); // or 'es', etc.
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    // For demo: load from public/ directory. In production, fetch from API.
    fetch(`/user_knowledge_llm_summary_${language}.json`)
      .then(res => res.json())
      .then(data => {
        setKnowledge(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [language]);

  if (loading) return <div className="p-8">Loading...</div>;
  if (!knowledge) return <div className="p-8">No knowledge data found.</div>;

  // Verb ranking
  const verbRanking = knowledge.verbs ? rankVerbs(knowledge.verbs) : [];

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-3xl font-bold mb-6">Your Progress</h1>
      <div className="mb-8">
        <label className="font-semibold mr-2">Language:</label>
        <select value={language} onChange={e => setLanguage(e.target.value)} className="border rounded px-2 py-1">
          <option value="en">English</option>
          <option value="es">Spanish</option>
        </select>
      </div>
      <section className="mb-10">
        <h2 className="text-2xl font-semibold mb-4">Your Knowledge</h2>
        <div className="grid grid-cols-2 gap-4 mb-6">
          {PARTS.map(part => (
            <div key={part} className="bg-gray-100 rounded p-4">
              <div className="font-medium capitalize">{part}</div>
              <div className="text-2xl font-bold">{knowledge[part] ? knowledge[part].length : 0}</div>
            </div>
          ))}
        </div>
        <h3 className="text-xl font-semibold mt-8 mb-2">Verb Strength Ranking</h3>
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
            {verbRanking.map(v => (
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
      </section>
    </div>
  );
} 