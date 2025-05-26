'use client';

import { Mistake } from '../types/feedback';

interface LanguageFeaturesHeatmapProps {
  mistakes: Mistake[];
}

interface FeatureStats {
  total: number;
  minor: number;
  moderate: number;
  critical: number;
}

export default function LanguageFeaturesHeatmap({ mistakes }: LanguageFeaturesHeatmapProps) {
  // Group mistakes by language feature and count severities
  const featureStats = mistakes.reduce((acc, mistake) => {
    const features = mistake.languageFeatureTags || ['untagged'];
    
    features.forEach(feature => {
      if (!acc[feature]) {
        acc[feature] = { total: 0, minor: 0, moderate: 0, critical: 0 };
      }
      acc[feature].total++;
      acc[feature][mistake.severity]++;
    });
    
    return acc;
  }, {} as Record<string, FeatureStats>);

  // Sort features by total mistakes (descending)
  const sortedFeatures = Object.entries(featureStats)
    .sort(([, a], [, b]) => b.total - a.total);

  // Calculate max values for color scaling
  const maxTotal = Math.max(...Object.values(featureStats).map(s => s.total));

  // Helper function to get background color intensity
  const getBackgroundColor = (count: number, severity: 'minor' | 'moderate' | 'critical') => {
    const intensity = Math.max(0.1, count / maxTotal);
    switch (severity) {
      case 'minor':
        return `rgba(255, 206, 86, ${intensity})`; // Yellow
      case 'moderate':
        return `rgba(255, 159, 64, ${intensity})`; // Orange
      case 'critical':
        return `rgba(255, 99, 132, ${intensity})`; // Red
      default:
        return 'transparent';
    }
  };

  // Format feature name for display
  const formatFeatureName = (feature: string) => {
    return feature
      .replace(/_/g, ' ')
      .split(' ')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(' ');
  };

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full">
        <thead>
          <tr>
            <th className="px-4 py-2 text-left text-sm font-medium text-gray-700">Language Feature</th>
            <th className="px-4 py-2 text-center text-sm font-medium text-gray-700">Total</th>
            <th className="px-4 py-2 text-center text-sm font-medium text-gray-700">Minor</th>
            <th className="px-4 py-2 text-center text-sm font-medium text-gray-700">Moderate</th>
            <th className="px-4 py-2 text-center text-sm font-medium text-gray-700">Critical</th>
          </tr>
        </thead>
        <tbody>
          {sortedFeatures.map(([feature, stats]) => (
            <tr key={feature} className="hover:bg-gray-50">
              <td className="px-4 py-2 text-sm font-medium text-gray-900">
                {formatFeatureName(feature)}
              </td>
              <td className="px-4 py-2 text-center">
                <div className="text-sm font-medium text-gray-900">{stats.total}</div>
              </td>
              <td className="px-4 py-2">
                <div 
                  className="mx-auto w-12 h-8 rounded flex items-center justify-center text-sm"
                  style={{ backgroundColor: getBackgroundColor(stats.minor, 'minor') }}
                >
                  {stats.minor}
                </div>
              </td>
              <td className="px-4 py-2">
                <div 
                  className="mx-auto w-12 h-8 rounded flex items-center justify-center text-sm"
                  style={{ backgroundColor: getBackgroundColor(stats.moderate, 'moderate') }}
                >
                  {stats.moderate}
                </div>
              </td>
              <td className="px-4 py-2">
                <div 
                  className="mx-auto w-12 h-8 rounded flex items-center justify-center text-sm"
                  style={{ backgroundColor: getBackgroundColor(stats.critical, 'critical') }}
                >
                  {stats.critical}
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {sortedFeatures.length === 0 && (
        <div className="text-center text-gray-500 py-4">
          No language feature data available
        </div>
      )}
    </div>
  );
} 