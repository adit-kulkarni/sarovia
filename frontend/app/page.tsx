'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

interface ContextCard {
  id: string;
  title: string;
  description: string;
  icon: string;
}

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
  const [selectedContext, setSelectedContext] = useState<string | null>(null);

  const handleContextSelect = (contextId: string) => {
    setSelectedContext(contextId);
    // Navigate to chat page with the selected context
    router.push(`/chat?context=${contextId}`);
  };

  return (
    <main className="min-h-screen bg-gradient-to-br from-yellow-50 to-orange-100 flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-4xl mx-auto">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-gray-800 mb-2">Spanish Conversation Practice</h1>
          <p className="text-gray-600">Select a conversation context to begin practicing</p>
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
      </div>
    </main>
  );
} 