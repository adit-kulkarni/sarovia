'use client';

import React from 'react';

export default function About() {
  return (
    <div className="min-h-screen p-8">
      <div className="max-w-3xl mx-auto bg-white/80 backdrop-blur-sm rounded-3xl shadow-xl border border-orange-100 p-8">
        <h1 className="text-3xl font-bold text-orange-600 mb-6">About Language Practice</h1>
        
        <div className="space-y-6 text-gray-700">
          <section>
            <h2 className="text-xl font-semibold text-orange-700 mb-3">Our Mission</h2>
            <p className="leading-relaxed">
              We&apos;re on a mission to make language learning more accessible, engaging, and effective through
              real-time conversation practice. Our AI-powered platform provides an immersive environment
              where you can practice speaking and listening in your target language with confidence.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-orange-700 mb-3">Key Features</h2>
            <ul className="list-disc list-inside space-y-2">
              <li>Real-time voice conversations with AI tutors</li>
              <li>Multiple language support (English, Italian, Spanish, Portuguese, French, German, Kannada)</li>
              <li>Various conversation contexts (Restaurant, Market, City Guide, etc.)</li>
              <li>Adaptive difficulty levels (A1 to C2)</li>
              <li>Conversation history tracking</li>
              <li>Instant feedback and corrections</li>
            </ul>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-orange-700 mb-3">How It Works</h2>
            <ol className="list-decimal list-inside space-y-2">
              <li>Choose your target language and proficiency level</li>
              <li>Select a conversation context that interests you</li>
              <li>Start speaking with our AI tutor in real-time</li>
              <li>Receive instant feedback and corrections</li>
              <li>Track your progress through conversation history</li>
            </ol>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-orange-700 mb-3">Technology</h2>
            <p className="leading-relaxed">
              Our platform leverages cutting-edge AI technology, including OpenAI&apos;s GPT-4 and real-time
              voice processing capabilities. This allows for natural, fluid conversations while providing
              accurate language feedback and corrections.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-semibold text-orange-700 mb-3">Get Started</h2>
            <p className="leading-relaxed">
              Ready to begin your language learning journey? Simply click on &quot;New Chat&quot; in the sidebar
              and choose your preferred language and context. Our AI tutor will guide you through an
              engaging conversation practice session.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
} 