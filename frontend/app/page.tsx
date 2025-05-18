'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useUser } from './hooks/useUser';
import Auth from './Auth';

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
  const user = useUser();

  if (!user) {
    return <Auth />;
  }

  const handleLanguageSelect = (languageCode: string) => {
    setSelectedLanguage(languageCode);
  };

  const handleContextSelect = (contextId: string) => {
    if (!selectedLanguage) return;
    setSelectedContext(contextId);
    // Navigate to chat page with the selected context and language
    router.push(`/chat?context=${contextId}&language=${selectedLanguage}`);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-100 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Language Conversation Practice</h1>
          <p className="text-gray-600">Select a language to begin practicing</p>
        </div>

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
            <div className="text-center mb-8">
              <h2 className="text-2xl font-bold text-gray-800 mb-2">Select a Conversation Context</h2>
              <p className="text-gray-600">Choose a scenario to practice {languages.find(l => l.code === selectedLanguage)?.name}</p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {contextCards.map((card) => (
                <button
                  key={card.id}
                  onClick={() => handleContextSelect(card.id)}
                  className="bg-white/80 backdrop-blur-sm rounded-2xl p-6 text-left border border-orange-100 
                           shadow-lg hover:shadow-xl transition-all duration-300 hover:scale-[1.02]
                           hover:border-orange-300 group"
                >
                  <div className="text-4xl mb-4 transform group-hover:scale-110 transition-transform duration-300">
                    {card.icon}
                  </div>
                  <h2 className="text-xl font-semibold text-gray-800 mb-2 group-hover:text-orange-600 transition-colors">
                    {card.title}
                  </h2>
                  <p className="text-gray-600 text-sm">
                    {card.description}
                  </p>
                </button>
              ))}
            </div>
          </>
        )}
      </div>
    </main>
  );
} 