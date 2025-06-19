'use client';

import { useState, useEffect } from 'react';
import { useUser } from '../hooks/useUser';
import { supabase } from '../../supabaseClient';

interface SelectedInterest {
  parent_interest: string;
  child_interest: string | null;
  context: string;
}

const ProfilePage = () => {
  const user = useUser();
  const [selectedInterests, setSelectedInterests] = useState<SelectedInterest[]>([]);
  const [overlayInterest, setOverlayInterest] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState<string | null>(null);
  const [showClearModal, setShowClearModal] = useState(false);
  const [clearing, setClearing] = useState(false);

  const openOverlay = (interest: string) => {
    setOverlayInterest(interest);
  };

  const closeOverlay = () => {
    setOverlayInterest(null);
  };

  // Updated interest data with more modern/relevant categories
  const interestCategories = {
    "Travel": [
      "South East Asia", 
      "Europe", 
      "Hiking", 
      "Beach", 
      "City Breaks", 
      "Cultural Sites", 
      "Digital Nomad Life", 
      "Vanlife", 
      "Hostel Culture", 
      "Travel Hacking"
    ],
    "Cooking & Food": [
      "Italian", 
      "Asian", 
      "Baking", 
      "Vegetarian", 
      "Fine Dining", 
      "Street Food", 
      "Viral Recipes", 
      "Meal Prepping", 
      "Air Fryer Experiments", 
      "Food TikTok"
    ],
    "Sports & Fitness": [
      "Football", 
      "Basketball", 
      "Tennis", 
      "Swimming", 
      "Running", 
      "Cycling", 
      "Gym Life", 
      "Pilates", 
      "Hot Girl Walks", 
      "eSports"
    ],
    "Arts & Creativity": [
      "Painting", 
      "Music", 
      "Theater", 
      "Photography", 
      "Dance", 
      "Street Art", 
      "Content Creation", 
      "Aesthetic Design", 
      "Film Photography", 
      "Zine Making"
    ],
    "Technology & Gaming": [
      "Programming", 
      "AI/ML", 
      "Gadgets", 
      "Startups", 
      "Mobile Apps", 
      "Twitch Streaming", 
      "VR/AR", 
      "Cozy Games", 
      "Speedrunning", 
      "Tech TikTok"
    ],
    "Literature & Media": [
      "Fiction", 
      "Non-fiction", 
      "Poetry", 
      "Biographies", 
      "Sci-Fi", 
      "Mystery", 
      "BookTok", 
      "Fanfiction", 
      "Manga", 
      "Zodiac Memes"
    ],
    "Health & Wellness": [
      "Fitness", 
      "Yoga", 
      "Meditation", 
      "Nutrition", 
      "Mental Health", 
      "Wellness", 
      "Self-Care Sundays", 
      "Sleep Hygiene", 
      "Therapy Talk", 
      "Gut Health"
    ],
    "Business & Hustle": [
      "Entrepreneurship", 
      "Marketing", 
      "Finance", 
      "Leadership", 
      "Innovation", 
      "E-commerce", 
      "Side Hustles", 
      "Crypto", 
      "Creator Economy", 
      "Drop Shipping"
    ],
    "Internet Culture": [
      "TikTok Trends", 
      "Memes", 
      "Twitter Drama", 
      "Reddit Deep Dives", 
      "NPC Content", 
      "YouTube Commentary", 
      "Reaction Videos", 
      "Influencer Tea", 
      "Internet Challenges", 
      "Emoji Speak"
    ],
    "Pop Culture & Fandoms": [
      "K-pop", 
      "Anime", 
      "Marvel/DC", 
      "Reality TV", 
      "Drag Race", 
      "Euphoria", 
      "Stan Culture", 
      "Fan Edits", 
      "Concerts", 
      "Festival Season"
    ],
    "Aesthetics & Lifestyle": [
      "Cottagecore", 
      "Clean Girl Aesthetic", 
      "Streetwear", 
      "Tiny Homes", 
      "Thrifting", 
      "Slow Living", 
      "Matcha Culture", 
      "Bullet Journaling", 
      "Plant Parenting", 
      "Interior Vibes"
    ],
    "Relationships & Identity": [
      "Dating Apps", 
      "Love Languages", 
      "Astrology", 
      "Situationships", 
      "Friendship Drama", 
      "Coming Out Stories", 
      "Therapy Speak", 
      "Attachment Styles", 
      "Text Etiquette", 
      "Vibe Checks"
    ],
    "Music & Sound": [
      "Hyperpop", 
      "Indie Sleaze", 
      "Lo-fi", 
      "Trap", 
      "DJ Culture", 
      "Spotify Wrapped", 
      "Vinyl Collecting", 
      "Concert Vibes", 
      "Festival Playlists", 
      "Music Memes"
    ],
    "Consumer Trends": [
      "Skincare Routines", 
      "Amazon Finds", 
      "Dupes", 
      "Unboxings", 
      "Influencer Merch", 
      "Stanley Cups", 
      "Etsy Finds", 
      "Hype Drops", 
      "SHEIN Hauls", 
      "Subscription Boxes"
    ],
    "Identity & Social Topics": [
      "Feminism", 
      "LGBTQ+ Topics", 
      "Cultural Identity", 
      "Neurodiversity", 
      "Sustainability", 
      "Climate Anxiety", 
      "Social Justice Movements", 
      "DEI", 
      "Allyship", 
      "Eco-Activism"
    ],
    "Education & Career": [
      "Study Hacks", 
      "Productivity Tools", 
      "Digital Planners", 
      "College Life", 
      "Career Aspirations", 
      "Remote Work", 
      "Internships", 
      "Freelancing", 
      "Time Management", 
      "LinkedIn Culture"
    ],
    "DIY & Skills": [
      "Coding", 
      "Graphic Design", 
      "Language Learning", 
      "Knitting", 
      "Woodworking", 
      "Home Improvement", 
      "3D Printing", 
      "Sewing & Upcycling", 
      "Resin Art", 
      "Crafting"
    ],
    "Sustainability & Green Living": [
      "Zero Waste", 
      "Upcycling", 
      "Veganism", 
      "Composting", 
      "Plant-Based Eating", 
      "Eco-Friendly Swaps", 
      "Minimalism", 
      "Thrifting", 
      "Plastic-Free Living", 
      "Climate Action"
    ],
    "Philosophy & Deep Thoughts": [
      "Stoicism", 
      "Existentialism", 
      "Mindfulness", 
      "Spirituality", 
      "Dream Interpretation", 
      "Journal Prompts", 
      "Shower Thoughts", 
      "Online Discourse", 
      "Mental Clarity", 
      "Emotional Intelligence"
    ],
    "Media Consumption": [
      "YouTube Rabbit Holes", 
      "True Crime Podcasts", 
      "Netflix Bingeing", 
      "ASMR", 
      "Vlogs", 
      "Rewatch Podcasts", 
      "TikTok Compilations", 
      "Documentaries", 
      "Streamer Drama", 
      "Watch Parties"
    ]
  };

  // Get category icons
  const getCategoryIcon = (category: string) => {
    const icons: Record<string, string> = {
      "Travel": "✈️",
      "Cooking & Food": "🍳",
      "Sports & Fitness": "🏃‍♀️",
      "Arts & Creativity": "🎨",
      "Technology & Gaming": "💻",
      "Literature & Media": "📚",
      "Health & Wellness": "🧘‍♀️",
      "Business & Hustle": "💼",
      "Internet Culture": "📱",
      "Pop Culture & Fandoms": "🎭",
      "Aesthetics & Lifestyle": "✨",
      "Relationships & Identity": "💕",
      "Music & Sound": "🎵",
      "Consumer Trends": "🛍️",
      "Identity & Social Topics": "🌍",
      "Education & Career": "🎓",
      "DIY & Skills": "🔨",
      "Sustainability & Green Living": "🌱",
      "Philosophy & Deep Thoughts": "🤔",
      "Media Consumption": "📺"
    };
    return icons[category] || "🏷️";
  };

  // Fetch JWT token on mount
  useEffect(() => {
    const fetchToken = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        setToken(session.access_token);
      }
      setLoading(false);
    };
    fetchToken();
  }, [user]);

  // Load existing interests
  useEffect(() => {
    if (token) {
      loadInterests();
    }
  }, [token]);

  const loadInterests = async () => {
    if (!token) return;

    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${API_BASE}/api/user_interests?token=${token}`);
      
      if (response.ok) {
        const data = await response.json();
        
        // Convert grouped interests back to flat array
        const interests: SelectedInterest[] = [];
        Object.entries(data.interests).forEach(([parentInterest, children]) => {
          const childrenArray = children as any[];
          childrenArray.forEach((child: any) => {
            interests.push({
              parent_interest: parentInterest,
              child_interest: child.child_interest,
              context: child.context
            });
          });
        });
        
        setSelectedInterests(interests);
      }
    } catch (error) {
      console.error('Error loading interests:', error);
    }
  };

  const handleCategorySelect = (category: string) => {
    // Check if this parent category is already selected
    const hasParentInterest = selectedInterests.some(
      interest => interest.parent_interest === category && interest.child_interest === null
    );
    
    if (!hasParentInterest) {
      // Add the parent category
      const newInterest: SelectedInterest = {
        parent_interest: category,
        child_interest: null,
        context: `interested in ${category.toLowerCase()}`
      };
      setSelectedInterests(prev => [...prev, newInterest]);
    }
  };

  const handleChildInterestSelect = (parentCategory: string, childInterest: string) => {
    // Check if this specific child interest is already selected
    const hasChildInterest = selectedInterests.some(
      interest => interest.parent_interest === parentCategory && interest.child_interest === childInterest
    );
    
    if (!hasChildInterest) {
      const newInterest: SelectedInterest = {
        parent_interest: parentCategory,
        child_interest: childInterest,
        context: `interested in ${childInterest.toLowerCase()} (${parentCategory.toLowerCase()})`
      };
      setSelectedInterests(prev => [...prev, newInterest]);
    }
  };

  const removeInterest = (parentInterest: string, childInterest: string | null) => {
    setSelectedInterests(prev => 
      prev.filter(interest => 
        !(interest.parent_interest === parentInterest && interest.child_interest === childInterest)
      )
    );
  };

  const saveInterests = async () => {
    if (!token) return;

    setSaving(true);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      const response = await fetch(`${API_BASE}/api/user_interests?token=${token}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          interests: selectedInterests
        })
      });

      if (response.ok) {
        alert('Interests saved successfully! Your personalized conversation contexts are being generated in the background. They will appear in the "Start Conversation" modal within a few minutes.');
      } else {
        throw new Error('Failed to save interests');
      }
    } catch (error) {
      console.error('Error saving interests:', error);
      alert('Failed to save interests. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const clearAllInterests = async () => {
    if (!token) return;

    setClearing(true);
    try {
      const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';
      
      // Use the new clear all endpoint
      const response = await fetch(`${API_BASE}/api/user_interests?token=${token}`, {
        method: 'DELETE'
      });
      
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to clear interests: ${errorText}`);
      }

      const result = await response.json();

      // Clear local state
      setSelectedInterests([]);
      setShowClearModal(false);
      
      alert(`All interests cleared successfully! Removed ${result.deleted_interests} interests and ${result.deleted_contexts} personalized contexts.`);
    } catch (error) {
      console.error('Error clearing interests:', error);
      alert('Failed to clear interests. Please try again.');
    } finally {
      setClearing(false);
    }
  };

  const isParentSelected = (category: string) => {
    return selectedInterests.some(
      interest => interest.parent_interest === category && interest.child_interest === null
    );
  };

  const isChildSelected = (parentCategory: string, childInterest: string) => {
    return selectedInterests.some(
      interest => interest.parent_interest === parentCategory && interest.child_interest === childInterest
    );
  };

  const getSelectedChildrenForParent = (parentCategory: string) => {
    return selectedInterests.filter(
      interest => interest.parent_interest === parentCategory && interest.child_interest !== null
    );
  };

  if (loading) {
  return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 to-orange-100">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-orange-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user || !token) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-orange-50 to-orange-100">
        <div className="text-center">
          <p className="text-gray-600">Please log in to manage your interests.</p>
                </div>
              </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6 min-h-screen">
      {/* Header */}
      <div className="text-center mb-8">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">
          Build Your Interest Profile
        </h1>
        <p className="text-gray-600">
          Select topics you're passionate about to personalize your learning experience
        </p>
      </div>

      {/* Selected Interests Section */}
      {selectedInterests.length > 0 && (
        <div className="mb-8 bg-white rounded-lg shadow-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-800">Your Selected Interests</h2>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowClearModal(true)}
                disabled={saving || clearing}
                className="px-3 py-1.5 text-sm bg-transparent border border-red-300 text-red-600 rounded-md hover:bg-red-50 hover:border-red-400 transition-colors disabled:opacity-50"
              >
                Clear All
              </button>
              <button
                onClick={saveInterests}
                disabled={saving}
                className="px-4 py-1.5 text-sm bg-transparent border border-orange-300 text-gray-700 rounded-md hover:bg-orange-50 hover:border-orange-400 transition-colors disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Interests'}
              </button>
            </div>
            </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.keys(interestCategories).map(category => {
              const parentSelected = isParentSelected(category);
              const childInterests = getSelectedChildrenForParent(category);
              
              if (!parentSelected && childInterests.length === 0) return null;
              
              return (
                <div key={category} className="border border-gray-200 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-xl">{getCategoryIcon(category)}</span>
                      <span className="font-semibold text-gray-800">{category}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      {parentSelected && (
                        <button
                          onClick={() => openOverlay(category)}
                          className="text-orange-500 hover:text-orange-700 text-sm px-2 py-1 rounded"
                          title="Add specific interests"
                        >
                          +
                        </button>
                      )}
                      {parentSelected && (
                        <button
                          onClick={() => removeInterest(category, null)}
                          className="text-red-500 hover:text-red-700 text-sm"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  </div>
                  
                  {/* Selected child interests - compact display */}
                  {childInterests.length > 0 && (
                    <div className="ml-6 mt-2">
                      <div className="flex flex-wrap gap-1">
                        {childInterests.slice(0, 3).map(interest => (
                          <div
                            key={interest.child_interest}
                            className="inline-flex items-center gap-1 bg-orange-100 text-orange-800 px-2 py-1 rounded text-xs"
                          >
                            <span>{interest.child_interest}</span>
                            <button
                              onClick={() => removeInterest(category, interest.child_interest)}
                              className="text-orange-600 hover:text-orange-800"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                        {childInterests.length > 3 && (
                          <span className="text-xs text-gray-500 px-2 py-1">
                            +{childInterests.length - 3} more
                          </span>
                        )}
                      </div>
                    </div>
                  )}


                </div>
              );
            })}
                  </div>
                </div>
              )}

      {/* Bubble Overlay for Child Interest Selection */}
      {overlayInterest && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black bg-opacity-50"
            onClick={closeOverlay}
          ></div>
          
          {/* Bubble */}
          <div className="relative bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 transform transition-all duration-200 scale-100">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xl">{getCategoryIcon(overlayInterest)}</span>
                <h3 className="text-lg font-semibold text-gray-800">{overlayInterest}</h3>
              </div>
              <button
                onClick={closeOverlay}
                className="text-gray-400 hover:text-gray-600 text-xl font-bold"
              >
                ×
              </button>
            </div>
            
            {/* Child Interests */}
            <div className="space-y-3">
              <p className="text-sm text-gray-600">Select specific interests:</p>
              <div className="flex flex-wrap gap-2">
                {interestCategories[overlayInterest as keyof typeof interestCategories]
                  .filter(childInterest => !isChildSelected(overlayInterest, childInterest))
                  .map(childInterest => (
                  <button
                    key={childInterest}
                    onClick={() => {
                      handleChildInterestSelect(overlayInterest, childInterest);
                    }}
                    className="px-3 py-2 rounded-full border border-gray-200 bg-gray-50 hover:border-orange-300 hover:bg-orange-50 text-sm text-gray-700 transition-colors"
                  >
                    {childInterest}
                  </button>
                ))}
              </div>
              
              {/* Currently Selected Child Interests */}
              {getSelectedChildrenForParent(overlayInterest).length > 0 && (
                <div className="mt-4 pt-4 border-t border-gray-100">
                  <p className="text-sm text-gray-600 mb-2">Currently selected:</p>
                  <div className="flex flex-wrap gap-2">
                    {getSelectedChildrenForParent(overlayInterest).map(interest => (
                      <div
                        key={interest.child_interest}
                        className="inline-flex items-center gap-1 bg-orange-100 text-orange-800 px-3 py-2 rounded-full text-sm"
                      >
                        <span>{interest.child_interest}</span>
                        <button
                          onClick={() => removeInterest(overlayInterest, interest.child_interest)}
                          className="text-orange-600 hover:text-orange-800"
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Interest Categories Grid - Compact Tags */}
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-gray-800 mb-3">Choose Your Interests</h2>
        <div className="flex flex-wrap gap-2">
          {Object.keys(interestCategories).map(category => (
            <button
              key={category}
              onClick={() => handleCategorySelect(category)}
              className={`px-3 py-2 rounded-full border transition-all duration-200 ${
                isParentSelected(category)
                  ? 'border-orange-500 bg-orange-50 text-orange-800 shadow-md'
                  : 'border-gray-200 bg-white text-gray-700 hover:border-orange-300 hover:bg-orange-50'
              }`}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm">{getCategoryIcon(category)}</span>
                <span className="font-medium text-sm">{category}</span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* Clear All Interests Confirmation Modal */}
      {showClearModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black bg-opacity-50"
            onClick={() => !clearing && setShowClearModal(false)}
          ></div>
          
          {/* Modal */}
          <div className="relative bg-white rounded-xl shadow-2xl p-6 max-w-md w-full mx-4 transform transition-all duration-200 scale-100">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-2xl">⚠️</span>
                <h3 className="text-lg font-semibold text-gray-800">Clear All Interests</h3>
              </div>
              {!clearing && (
                <button
                  onClick={() => setShowClearModal(false)}
                  className="text-gray-400 hover:text-gray-600 text-xl font-bold"
                >
                  ×
                </button>
              )}
            </div>
            
            {/* Content */}
            <div className="mb-6">
              <p className="text-gray-600 mb-3">
                Are you sure you want to clear all your interests? This will:
              </p>
              <ul className="text-sm text-gray-600 list-disc list-inside space-y-1 mb-4">
                <li>Remove all your selected interests</li>
                <li>Delete all your personalized conversation contexts</li>
                <li>Reset your profile to the default state</li>
              </ul>
              <p className="text-sm text-red-600 font-medium">
                This action cannot be undone.
              </p>
            </div>
            
            {/* Buttons */}
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowClearModal(false)}
                disabled={clearing}
                className="px-4 py-2 text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={clearAllInterests}
                disabled={clearing}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors disabled:opacity-50 flex items-center gap-2"
              >
                {clearing && (
                  <div className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white"></div>
                )}
                {clearing ? 'Clearing...' : 'Delete All'}
              </button>
            </div>
          </div>
        </div>
      )}
      
    </div>
  );
};

export default ProfilePage; 