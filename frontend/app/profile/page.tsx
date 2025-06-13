'use client';

import { useState, useEffect } from 'react';
import { useUser } from '../hooks/useUser';

const ProfilePage = () => {
  const user = useUser();
  const [selectedInterests, setSelectedInterests] = useState<string[]>([]);

  // Conversation and personal interests
  const interests = [
    'Travel', 'Cooking', 'Music', 'Movies', 'Books', 'Sports',
    'Art', 'Photography', 'Technology', 'History', 'Science', 'Nature',
    'Food & Dining', 'Fashion', 'Gaming', 'Fitness', 'Business', 'Culture',
    'Politics', 'Philosophy', 'Literature', 'Architecture', 'Dancing', 'Theater',
    'Volunteering', 'Gardening', 'Pets', 'Family', 'Career', 'Education',
    'Health & Wellness', 'Environment', 'Social Issues', 'Economics', 'Psychology'
  ];

  const toggleInterest = (interest: string) => {
    setSelectedInterests(prev => 
      prev.includes(interest) 
        ? prev.filter(i => i !== interest)
        : [...prev, interest]
    );
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-orange-50 to-orange-100 p-4">
      <div className="max-w-3xl mx-auto">
        <h1 className="text-2xl font-bold mb-4 text-center text-gray-800">Profile Settings</h1>

        <div className="bg-white/80 backdrop-blur-md rounded-xl shadow-lg border border-orange-200 overflow-hidden">
          <div className="p-4 space-y-4">
            
            {/* User Email Section */}
            <div className="bg-orange-50 rounded-lg p-4 border border-orange-200">
              <h2 className="text-lg font-bold mb-2 text-orange-700">Account Information</h2>
              <div>
                <label className="block text-xs font-semibold text-gray-700 mb-1">
                  Email Address
                </label>
                <div className="bg-white rounded-lg border border-orange-200 px-3 py-2 text-gray-800 text-sm">
                  {user?.email || 'Not available'}
                </div>
              </div>
            </div>

            {/* Interests Section */}
            <div className="bg-orange-50 rounded-lg p-4 border border-orange-200">
              <h2 className="text-lg font-bold mb-2 text-orange-700">Your Interests</h2>
              <p className="text-gray-600 mb-3 text-sm">
                Select topics you're interested in discussing. This helps personalize your conversation practice.
              </p>
              
              <div className="flex flex-wrap gap-2">
                {interests.map((interest) => (
                  <button
                    key={interest}
                    onClick={() => toggleInterest(interest)}
                    className={`px-3 py-1 rounded-full border font-medium text-xs transition-all duration-200 ${
                      selectedInterests.includes(interest)
                        ? 'bg-orange-500 text-white border-orange-500 shadow-md'
                        : 'bg-white text-gray-700 border-orange-200 hover:border-orange-400 hover:bg-orange-50'
                    }`}
                  >
                    {interest}
                  </button>
                ))}
              </div>
              
              {selectedInterests.length > 0 && (
                <div className="mt-3 p-3 bg-white rounded-lg border border-orange-200">
                  <p className="text-xs text-gray-600 mb-2">
                    <span className="font-semibold">{selectedInterests.length}</span> interests selected:
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {selectedInterests.map((interest) => (
                      <span
                        key={interest}
                        className="px-2 py-1 bg-orange-100 text-orange-700 rounded-full text-xs font-medium"
                      >
                        {interest}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Save Button */}
            <div className="pt-2">
              <button
                type="button"
                className="w-full rounded-lg bg-orange-500 px-4 py-3 text-base font-bold text-white shadow-md hover:bg-orange-600 focus:outline-none focus:ring-2 focus:ring-orange-300 transition-all duration-200"
              >
                Save Changes
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProfilePage; 