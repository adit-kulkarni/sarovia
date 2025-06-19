'use client';

import { FeedbackPanelProps, Feedback, Mistake } from '../types/feedback';
import FeedbackCard from './FeedbackCard';
import { useEffect, useRef, useState } from 'react';

// Define the available categories and their types based on server configuration
const FEEDBACK_CATEGORIES = {
  "grammar": ["verb tense", "verb usage", "subject-verb agreement", "article usage", 
             "preposition usage", "pluralization", "auxiliary verb usage", 
             "modal verb usage", "pronoun agreement", "negation", 
             "comparatives/superlatives", "conditional structures", 
             "passive voice", "question formation", "other"],
  "vocabulary": ["word meaning error", "false friend", "missing word", 
                "extra word", "word form", "other"],
  "syntax": ["word order", "run-on sentence", "fragment/incomplete sentence", "other"],
  "word choice": ["unnatural phrasing", "contextually inappropriate word", 
                 "idiomatic error", "register mismatch", "other"],
  "register/formality": ["informal in formal context", "formal in informal context", "other"]
};

const SEVERITY_LEVELS = ['minor', 'moderate', 'critical'] as const;

interface FilterState {
  severities: Set<string>;
  categories: Set<string>;
  types: Set<string>;
}

const STORAGE_KEY = 'feedbackFilters';

// Helper function to get all types for selected categories
const getAvailableTypes = (selectedCategories: Set<string>): string[] => {
  if (selectedCategories.size === 0) return [];
  
  const types: string[] = [];
  selectedCategories.forEach(category => {
    if (FEEDBACK_CATEGORIES[category as keyof typeof FEEDBACK_CATEGORIES]) {
      types.push(...FEEDBACK_CATEGORIES[category as keyof typeof FEEDBACK_CATEGORIES]);
    }
  });
  return [...new Set(types)]; // Remove duplicates
};

// Helper function to save filters to localStorage
const saveFilters = (filters: FilterState) => {
  try {
    const filterData = {
      severities: Array.from(filters.severities),
      categories: Array.from(filters.categories),
      types: Array.from(filters.types)
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(filterData));
  } catch (error) {
    console.warn('Failed to save filter preferences:', error);
  }
};

// Helper function to load filters from localStorage
const loadFilters = (): FilterState => {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      const filterData = JSON.parse(saved);
      return {
        severities: new Set(filterData.severities || SEVERITY_LEVELS),
        categories: new Set(filterData.categories || Object.keys(FEEDBACK_CATEGORIES)),
        types: new Set(filterData.types || getAvailableTypes(new Set(Object.keys(FEEDBACK_CATEGORIES))))
      };
    }
  } catch (error) {
    console.warn('Failed to load filter preferences:', error);
  }
  
  // Default: everything selected
  const allCategories = new Set(Object.keys(FEEDBACK_CATEGORIES));
  const defaultFilters = {
    severities: new Set(SEVERITY_LEVELS),
    categories: allCategories,
    types: new Set(getAvailableTypes(allCategories))
  };
  

  
  return defaultFilters;
};

// Helper function to filter feedback based on current filters
const filterFeedback = (feedbacks: Feedback[], filters: FilterState): Feedback[] => {
  return feedbacks.map(feedback => {
    // Always keep perfect messages (no mistakes)
    if (!feedback.hasMistakes) return feedback;
    
    const filteredMistakes = feedback.mistakes.filter(mistake => {
      const severityMatch = filters.severities.has(mistake.severity);
      const categoryMatch = filters.categories.has(mistake.category);
      const typeMatch = filters.types.has(mistake.type);
      
      return severityMatch && categoryMatch && typeMatch;
    });
    
    return {
      ...feedback,
      mistakes: filteredMistakes,
      hasMistakes: filteredMistakes.length > 0
    };
  });
  // Note: We don't filter out messages with no mistakes after filtering
  // This ensures perfect messages and filtered-out mistakes still show the message
};

export default function FeedbackPanel({ feedbacks, onFeedbackClick }: FeedbackPanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [activeTab, setActiveTab] = useState<'filtered' | 'all'>('filtered');
  const [filters, setFilters] = useState<FilterState>(loadFilters);
  const [showFilters, setShowFilters] = useState(false);



  // Auto-scroll to bottom when new feedback arrives
  useEffect(() => {
    if (panelRef.current) {
      panelRef.current.scrollTop = panelRef.current.scrollHeight;
    }
  }, [feedbacks]);

  // Save filters when they change
  useEffect(() => {
    saveFilters(filters);
  }, [filters]);

  // Get available types based on selected categories
  const availableTypes = getAvailableTypes(filters.categories);

  // Handle severity filter changes
  const handleSeverityChange = (severity: string, checked: boolean) => {
    const newSeverities = new Set(filters.severities);
    if (checked) {
      newSeverities.add(severity);
    } else {
      newSeverities.delete(severity);
    }
    setFilters(prev => ({ ...prev, severities: newSeverities }));
  };

  // Handle category filter changes
  const handleCategoryChange = (category: string, checked: boolean) => {
    const newCategories = new Set(filters.categories);
    const newTypes = new Set(filters.types);
    
    if (checked) {
      newCategories.add(category);
      // Add all types for this category
      const categoryTypes = FEEDBACK_CATEGORIES[category as keyof typeof FEEDBACK_CATEGORIES] || [];
      categoryTypes.forEach(type => newTypes.add(type));
    } else {
      newCategories.delete(category);
      // Remove all types for this category
      const categoryTypes = FEEDBACK_CATEGORIES[category as keyof typeof FEEDBACK_CATEGORIES] || [];
      categoryTypes.forEach(type => newTypes.delete(type));
    }
    
    setFilters(prev => ({ 
      ...prev, 
      categories: newCategories, 
      types: newTypes 
    }));
  };

  // Handle type filter changes
  const handleTypeChange = (type: string, checked: boolean) => {
    const newTypes = new Set(filters.types);
    if (checked) {
      newTypes.add(type);
    } else {
      newTypes.delete(type);
    }
    setFilters(prev => ({ ...prev, types: newTypes }));
  };

  // Reset filters to default (everything selected)
  const resetFilters = () => {
    const allCategories = new Set(Object.keys(FEEDBACK_CATEGORIES));
    const newFilters = {
      severities: new Set(SEVERITY_LEVELS),
      categories: allCategories,
      types: new Set(getAvailableTypes(allCategories))
    };
    setFilters(newFilters);
  };

  // Get feedbacks based on active tab
  const displayFeedbacks = activeTab === 'all' ? feedbacks : filterFeedback(feedbacks, filters);
  




  return (
    <div className="flex flex-col h-full">
      {/* Tab Headers */}
      <div className="flex border-b border-gray-200 mb-4">
        <button
          onClick={() => setActiveTab('filtered')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'filtered'
              ? 'border-orange-500 text-orange-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          Filtered View
        </button>
        <button
          onClick={() => setActiveTab('all')}
          className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
            activeTab === 'all'
              ? 'border-orange-500 text-orange-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          }`}
        >
          All Feedback
        </button>
      </div>

      {/* Filter Controls (only show on filtered tab) */}
      {activeTab === 'filtered' && (
        <div className="mb-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-medium text-gray-700">Filters</h4>
            <div className="flex gap-2">
              <button
                onClick={() => setShowFilters(!showFilters)}
                className="text-xs px-2 py-1 bg-gray-100 hover:bg-gray-200 rounded text-gray-600"
              >
                {showFilters ? 'Hide' : 'Show'} Filters
              </button>
              <button
                onClick={resetFilters}
                className="text-xs px-2 py-1 bg-orange-100 hover:bg-orange-200 rounded text-orange-600"
              >
                Reset
              </button>
            </div>
          </div>

          {showFilters && (
            <div className="bg-gray-50 rounded-lg p-3 space-y-3 text-xs">
              {/* Severity Filters */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Severity</label>
                <div className="flex flex-wrap gap-2">
                  {SEVERITY_LEVELS.map(severity => (
                    <label key={severity} className="flex items-center space-x-1">
                      <input
                        type="checkbox"
                        checked={filters.severities.has(severity)}
                        onChange={(e) => handleSeverityChange(severity, e.target.checked)}
                        className="w-3 h-3 text-orange-600 rounded border-gray-300 focus:ring-orange-500"
                      />
                      <span className="capitalize">{severity}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Category Filters */}
              <div>
                <label className="block text-xs font-medium text-gray-700 mb-1">Categories</label>
                <div className="flex flex-wrap gap-2">
                  {Object.keys(FEEDBACK_CATEGORIES).map(category => (
                    <label key={category} className="flex items-center space-x-1">
                      <input
                        type="checkbox"
                        checked={filters.categories.has(category)}
                        onChange={(e) => handleCategoryChange(category, e.target.checked)}
                        className="w-3 h-3 text-orange-600 rounded border-gray-300 focus:ring-orange-500"
                      />
                      <span className="capitalize">{category}</span>
                    </label>
                  ))}
                </div>
              </div>

              {/* Type Filters (only show types for selected categories) */}
              {availableTypes.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">Types</label>
                  <div className="flex flex-wrap gap-2 max-h-20 overflow-y-auto">
                    {availableTypes.map(type => (
                      <label key={type} className="flex items-center space-x-1">
                        <input
                          type="checkbox"
                          checked={filters.types.has(type)}
                          onChange={(e) => handleTypeChange(type, e.target.checked)}
                          className="w-3 h-3 text-orange-600 rounded border-gray-300 focus:ring-orange-500"
                        />
                        <span>{type}</span>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Feedback List */}
      <div 
        ref={panelRef}
        className="flex-1 overflow-y-auto space-y-2"
      >
        {displayFeedbacks.length === 0 ? (
          <div className="text-center text-gray-500 py-4">
            {activeTab === 'all' ? 'No feedback yet' : 'No feedback matches current filters'}
          </div>
        ) : (
          displayFeedbacks.map((feedback) => (
            <FeedbackCard
              key={feedback.messageId}
              feedback={feedback}
              onFeedbackClick={onFeedbackClick}
            />
          ))
        )}
      </div>
    </div>
  );
} 