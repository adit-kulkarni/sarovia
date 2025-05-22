'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useUser } from './hooks/useUser';
import Auth from './Auth';
import { supabase } from '../supabaseClient';

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

export default function Home() {
  const router = useRouter();
  const [selectedLanguage, setSelectedLanguage] = useState<string | null>(null);
  const [selectedContext, setSelectedContext] = useState<string | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const user = useUser();

  const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];

  if (!user) {
    return <Auth />;
  }

  const handleLanguageSelect = (languageCode: string) => {
    setSelectedLanguage(languageCode);
    setSelectedContext(null);
    setSelectedLevel(null);
    setError(null);
  };

  const handleContextSelect = (contextId: string) => {
    setSelectedContext(contextId);
    setError(null);
  };

  const handleLevelSelect = (level: string) => {
    setSelectedLevel(level);
    setError(null);
  };

  const handleStartConversation = () => {
    if (!selectedContext || !selectedLevel) {
      setError('Please select both a context and a level.');
      return;
    }
    setError(null);
    router.push(`/chat?context=${selectedContext}&language=${selectedLanguage}&level=${selectedLevel}`);
  };

  const handleLogout = async () => {
    await supabase.auth.signOut();
    router.refresh();
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-100 flex flex-col items-center justify-center p-2 relative">
      {user && (
        <button
          onClick={handleLogout}
          className="absolute top-4 right-4 bg-orange-100 hover:bg-orange-200 text-orange-700 font-semibold py-2 px-4 rounded-lg shadow transition-all text-sm z-20"
        >
          Log Out
        </button>
      )}
      <div className="w-full max-w-4xl mx-auto flex flex-col items-center justify-center" style={{ maxHeight: '90vh' }}>
        <div className="text-center mb-4">
          <h1 className="text-3xl font-bold text-gray-800 mb-1">Language Conversation Practice</h1>
          <p className="text-gray-600 text-base">Select a language to begin practicing</p>
        </div>

        {/* Step 1: Select Language */}
        {!selectedLanguage ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {languages.map((language) => (
              <button
                key={language.code}
                onClick={() => handleLanguageSelect(language.code)}
                className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 text-left border border-orange-100 
                         shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-[1.02]
                         hover:border-orange-300 group"
              >
                <div className="text-4xl mb-4 transform group-hover:scale-110 transition-transform duration-300">
                  {language.flag}
                </div>
                <h2 className="text-xl font-semibold text-gray-800 mb-2 group-hover:text-orange-600 transition-colors">
                  {language.name}
                </h2>
              </button>
            ))}
          </div>
        ) : (
          <>
            <div className="text-center mb-2">
              <h2 className="text-2xl font-bold text-gray-800 mb-1">Choose Your Level & Context</h2>
              <p className="text-gray-600 text-base">Practice {languages.find(l => l.code === selectedLanguage)?.name}</p>
            </div>

            {/* Level Selection - compact, above context cards */}
            <div className="flex justify-center mb-2">
              <select
                value={selectedLevel || ''}
                onChange={e => handleLevelSelect(e.target.value)}
                className="rounded-md border-gray-300 shadow-sm focus:border-orange-500 focus:ring-orange-500 px-3 py-1 text-base w-40"
                style={{ minWidth: 100 }}
              >
                <option value="" disabled>Select level</option>
                {levels.map(level => (
                  <option key={level} value={level}>{level}</option>
                ))}
              </select>
            </div>

            {/* Context Cards - 3 columns, 2 rows on desktop */}
            <div className="w-full flex justify-center">
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2 md:gap-4" style={{ maxWidth: 700 }}>
                {contextCards.map((card) => (
                  <button
                    key={card.id}
                    onClick={() => handleContextSelect(card.id)}
                    className={`bg-white/80 backdrop-blur-sm rounded-xl p-4 text-left border ${selectedContext === card.id ? 'border-orange-400' : 'border-orange-100'} 
                             shadow hover:shadow-md transition-all duration-200 hover:scale-[1.01]
                             hover:border-orange-300 group text-sm md:text-base min-h-[110px] flex flex-col justify-center`}
                  >
                    <div className="text-2xl mb-1 md:mb-2 transform group-hover:scale-110 transition-transform duration-200">
                      {card.icon}
                    </div>
                    <h2 className="font-semibold text-gray-800 mb-1 group-hover:text-orange-600 transition-colors text-base">
                      {card.title}
                    </h2>
                    <p className="text-gray-600 text-xs md:text-sm">
                      {card.description}
                    </p>
                  </button>
                ))}
              </div>
            </div>

            {/* Error Feedback */}
            {error && (
              <div className="text-center text-red-600 font-medium mt-2 mb-1">{error}</div>
            )}

            {/* Start Conversation Button */}
            <div className="flex justify-center mt-2">
              <button
                onClick={handleStartConversation}
                className="bg-orange-500 hover:bg-orange-600 text-white font-semibold px-8 py-2 rounded-lg shadow-lg transition-all text-lg"
                style={{ minWidth: 180 }}
              >
                Start Conversation
              </button>
            </div>
          </>
        )}
      </div>
    </main>
  );
} 