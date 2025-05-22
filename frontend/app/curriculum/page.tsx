'use client';

import { useState } from 'react';

const CurriculumPage = () => {
  const [selectedLevel, setSelectedLevel] = useState('all');
  const [selectedTopic, setSelectedTopic] = useState('all');

  const levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2'];
  const topics = ['Daily Life', 'Business', 'Travel', 'Culture', 'Academic'];

  // Placeholder agents data
  const agents = [
    {
      id: 1,
      name: 'Marco',
      specialization: 'Italian Culture',
      level: 'B1',
      topic: 'Culture',
      description: 'Learn about Italian culture and traditions through engaging conversations.',
    },
    {
      id: 2,
      name: 'Sophie',
      specialization: 'Business French',
      level: 'B2',
      topic: 'Business',
      description: 'Master business French with a focus on professional communication.',
    },
    // Add more agents as needed
  ];

  return (
    <div className="max-w-7xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Language Curriculum</h1>
      
      {/* Filters */}
      <div className="mb-8 flex flex-wrap gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Level</label>
          <select
            value={selectedLevel}
            onChange={(e) => setSelectedLevel(e.target.value)}
            className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="all">All Levels</option>
            {levels.map((level) => (
              <option key={level} value={level}>{level}</option>
            ))}
          </select>
        </div>
        
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Topic</label>
          <select
            value={selectedTopic}
            onChange={(e) => setSelectedTopic(e.target.value)}
            className="rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
          >
            <option value="all">All Topics</option>
            {topics.map((topic) => (
              <option key={topic} value={topic}>{topic}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Agents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {agents.map((agent) => (
          <div
            key={agent.id}
            className="bg-white rounded-lg shadow-md p-6 hover:shadow-lg transition-shadow"
          >
            <div className="flex items-center mb-4">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 font-bold text-xl">
                {agent.name[0]}
              </div>
              <div className="ml-4">
                <h3 className="text-lg font-semibold">{agent.name}</h3>
                <p className="text-sm text-gray-600">{agent.specialization}</p>
              </div>
            </div>
            <p className="text-gray-600 mb-4">{agent.description}</p>
            <div className="flex items-center justify-between">
              <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-sm">
                {agent.level}
              </span>
              <span className="px-2 py-1 bg-gray-100 text-gray-800 rounded-full text-sm">
                {agent.topic}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default CurriculumPage; 