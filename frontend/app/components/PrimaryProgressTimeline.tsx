'use client';

import React, { useState, useEffect, useMemo } from 'react';
import { useUser } from '../hooks/useUser';
import { supabase } from '../../supabaseClient';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

interface TimelineDataPoint {
  date: string;
  verbs_total?: number;
  accuracy_rate?: number;
}

interface ProgressMetricResponse {
  timeline_data: TimelineDataPoint[];
  total_snapshots: number;
  unique_dates: number;
  date_range: {
    start: string | null;
    end: string | null;
  };
  metric_type: string;
}

const MetricConfig = {
  verbs_total: {
    label: 'Verbs Learned',
    color: 'rgb(59, 130, 246)', // blue-500
    suffix: ' verbs',
    description: 'Total number of different verbs you know',
    reverse: false
  },
  accuracy_rate: {
    label: 'Accuracy Rate',
    color: 'rgb(34, 197, 94)', // green-500
    suffix: '%',
    description: 'Percentage of messages with no mistakes',
    reverse: false
  }
};

const TimePeriodConfig = {
  week: {
    label: '1 Week',
    historicalDays: 7,
    futureDays: 1,
    groupBy: 'day'
  },
  month: {
    label: '1 Month', 
    historicalDays: 30,
    futureDays: 3,
    groupBy: 'day'
  },
  year: {
    label: '1 Year',
    historicalDays: 365,
    futureDays: 13, // ~3 months in weeks
    groupBy: 'week'
  }
};

interface PrimaryProgressTimelineProps {
  selectedCurriculum: {
    id: string;
    language: string;
  } | null;
}

export default function PrimaryProgressTimeline({ selectedCurriculum }: PrimaryProgressTimelineProps) {
  const [selectedMetric, setSelectedMetric] = useState<keyof typeof MetricConfig>('accuracy_rate');
  const [selectedPeriod, setSelectedPeriod] = useState<keyof typeof TimePeriodConfig>('month');
  const [timelineData, setTimelineData] = useState<TimelineDataPoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const user = useUser();

  // Get JWT from supabase
  async function getToken() {
    const { data } = await supabase.auth.getSession();
    return data?.session?.access_token;
  }

  // Fetch knowledge snapshots data
  useEffect(() => {
    const fetchKnowledgeSnapshots = async () => {
      if (!user?.id || !selectedCurriculum?.id) {
        return;
      }
      
      setLoading(true);
      setError(null);
      
      try {
        const token = await getToken();
        if (!token) {
          throw new Error('Authentication required - please log in');
        }

        const response = await fetch(
          `${API_BASE}/api/progress_metrics?metric_type=${encodeURIComponent(selectedMetric)}&language=${encodeURIComponent(selectedCurriculum.language)}&curriculum_id=${encodeURIComponent(selectedCurriculum.id)}&limit=100&token=${encodeURIComponent(token)}`
        );
        
        if (!response.ok) {
          if (response.status === 401) {
            throw new Error('Session expired - please refresh and try again');
          } else if (response.status === 404) {
            throw new Error('Verb progress data not found');
          } else if (response.status >= 500) {
            throw new Error('Server error - please try again later');
          } else {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `Failed to fetch verb progress (${response.status})`);
          }
        }
        
        const data: ProgressMetricResponse = await response.json();
        
        if (!data.timeline_data || data.timeline_data.length === 0) {
          setError('No progress data found yet. Complete some lessons to see your growth!');
          return;
        }
        
        setTimelineData(data.timeline_data);
        
      } catch (err) {
        console.error('Error fetching verb progress:', err);
        setError(err instanceof Error ? err.message : 'Failed to load timeline data');
      } finally {
        setLoading(false);
      }
    };

    fetchKnowledgeSnapshots();
  }, [user?.id, selectedCurriculum?.id, selectedCurriculum?.language, selectedMetric]);

  const chartData = useMemo(() => {
    const selectedConfig = MetricConfig[selectedMetric];
    const periodConfig = TimePeriodConfig[selectedPeriod];
    
    const today = new Date();
    const chartWidth = 680; // Available chart width (740 - 60)
    
    if (periodConfig.groupBy === 'day') {
      // Day-based view (week/month)
      const dateRange: string[] = [];
      
      // Add historical days (including today)
      for (let i = periodConfig.historicalDays - 1; i >= 0; i--) {
        const date = new Date(today);
        date.setDate(today.getDate() - i);
        dateRange.push(date.toISOString().split('T')[0]);
      }
      
      // Add future days
      for (let i = 1; i <= periodConfig.futureDays; i++) {
        const date = new Date(today);
        date.setDate(today.getDate() + i);
        dateRange.push(date.toISOString().split('T')[0]);
      }

      // Create a map of actual data points
      const dataMap = new Map<string, number>();
      timelineData.forEach(point => {
        const value = selectedMetric === 'verbs_total' ? point.verbs_total : point.accuracy_rate;
        if (value !== undefined) {
          dataMap.set(point.date, value);
        }
      });

      // Create chart points only for dates that have data
      const chartPoints: Array<{ date: string; value: number; x: number; label: string }> = [];
      
      // Position data points within the full date range
      dateRange.forEach((date, index) => {
        if (dataMap.has(date)) {
          const x = 60 + (index / (dateRange.length - 1)) * chartWidth;
          chartPoints.push({
            date,
            value: dataMap.get(date)!,
            x,
            label: new Date(date).toLocaleDateString('en-US', { 
              month: 'short', 
              day: 'numeric' 
            })
          });
        }
      });

      if (chartPoints.length === 0) return null;

      // Calculate value range and trend
      const values = chartPoints.map(p => p.value);
      const maxValue = Math.max(...values, 1);
      const minValue = Math.min(...values, 0);
      const range = maxValue - minValue || 1;

      const recentValue = chartPoints[chartPoints.length - 1]?.value || 0;
      const oldValue = chartPoints.length > 1 ? chartPoints[0]?.value || 0 : 0;
      const trendPercentage = oldValue !== 0 ? ((recentValue - oldValue) / oldValue) * 100 : 0;
      const isImproving = selectedConfig.reverse ? trendPercentage < 0 : trendPercentage > 0;

      return {
        selectedConfig,
        chartPoints,
        dateRange,
        maxValue,
        minValue,
        range,
        recentValue,
        trendPercentage,
        isImproving,
        periodConfig
      };
      
    } else {
      // Week-based view (year)
      const weekRanges: Array<{ startDate: string; endDate: string; weekLabel: string }> = [];
      
      // Add historical weeks (including current week)
      for (let i = periodConfig.historicalDays / 7 - 1; i >= 0; i--) {
        const weekStart = new Date(today);
        weekStart.setDate(today.getDate() - (i * 7) - (today.getDay() || 7) + 1); // Start of week (Monday)
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6); // End of week (Sunday)
        
        weekRanges.push({
          startDate: weekStart.toISOString().split('T')[0],
          endDate: weekEnd.toISOString().split('T')[0],
          weekLabel: weekStart.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric' 
          })
        });
      }
      
      // Add future weeks
      for (let i = 1; i <= periodConfig.futureDays; i++) {
        const weekStart = new Date(today);
        weekStart.setDate(today.getDate() + (i * 7) - (today.getDay() || 7) + 1);
        const weekEnd = new Date(weekStart);
        weekEnd.setDate(weekStart.getDate() + 6);
        
        weekRanges.push({
          startDate: weekStart.toISOString().split('T')[0],
          endDate: weekEnd.toISOString().split('T')[0],
          weekLabel: weekStart.toLocaleDateString('en-US', { 
            month: 'short', 
            day: 'numeric' 
          })
        });
      }

      // Group data by weeks and take the maximum value for each week
      const weeklyData = new Map<string, number>();
      timelineData.forEach(point => {
        const pointDate = point.date;
        for (const week of weekRanges) {
          if (pointDate >= week.startDate && pointDate <= week.endDate) {
            const currentMax = weeklyData.get(week.startDate) || 0;
            const value = selectedMetric === 'verbs_total' ? point.verbs_total : point.accuracy_rate;
            if (value !== undefined) {
              weeklyData.set(week.startDate, Math.max(currentMax, value));
            }
            break;
          }
        }
      });

      // Create chart points for weeks that have data
      const chartPoints: Array<{ date: string; value: number; x: number; label: string }> = [];
      
      weekRanges.forEach((week, index) => {
        if (weeklyData.has(week.startDate)) {
          const x = 60 + (index / (weekRanges.length - 1)) * chartWidth;
          chartPoints.push({
            date: week.startDate,
            value: weeklyData.get(week.startDate)!,
            x,
            label: week.weekLabel
          });
        }
      });

      if (chartPoints.length === 0) return null;

      // Calculate value range and trend
      const values = chartPoints.map(p => p.value);
      const maxValue = Math.max(...values, 1);
      const minValue = Math.min(...values, 0);
      const range = maxValue - minValue || 1;

      const recentValue = chartPoints[chartPoints.length - 1]?.value || 0;
      const oldValue = chartPoints.length > 1 ? chartPoints[0]?.value || 0 : 0;
      const trendPercentage = oldValue !== 0 ? ((recentValue - oldValue) / oldValue) * 100 : 0;
      const isImproving = selectedConfig.reverse ? trendPercentage < 0 : trendPercentage > 0;

      return {
        selectedConfig,
        chartPoints,
        dateRange: weekRanges.map(w => w.startDate),
        maxValue,
        minValue,
        range,
        recentValue,
        trendPercentage,
        isImproving,
        periodConfig
      };
    }
  }, [timelineData, selectedMetric, selectedPeriod]);

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your progress timeline...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center text-red-500">
        <div className="text-center">
          <div className="text-4xl mb-4">⚠️</div>
          <h3 className="text-lg font-medium mb-2">Error Loading Timeline</h3>
          <p className="text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!timelineData.length) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <div className="text-4xl mb-4">📈</div>
          <h3 className="text-lg font-medium mb-2">No Progress Data Yet</h3>
          <p className="text-sm">Start practicing to see your improvement over time!</p>
        </div>
      </div>
    );
  }

  if (!chartData) return null;

  const { selectedConfig, recentValue, trendPercentage, isImproving, minValue, range } = chartData;

  return (
    <div className="h-full flex flex-col">
      {/* Header with Metric Selector */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-xl font-bold text-gray-800">Your Learning Journey</h3>
            <p className="text-sm text-gray-600">{selectedConfig.description}</p>
          </div>
          
          {/* Current Value & Trend */}
          <div className="text-right">
            <div className="text-2xl font-bold" style={{ color: selectedConfig.color }}>
              {recentValue.toFixed(1)}{selectedConfig.suffix}
            </div>
            <div className={`text-sm font-medium ${isImproving ? 'text-green-600' : 'text-red-500'}`}>
              {isImproving ? '↗' : '↘'} {Math.abs(trendPercentage).toFixed(1)}% vs {chartData.periodConfig.label.toLowerCase()} ago
            </div>
          </div>
        </div>

        {/* Time Period Selector */}
        <div className="flex flex-wrap gap-2 mb-3">
          {Object.entries(TimePeriodConfig).map(([key, config]) => (
            <button
              key={key}
              onClick={() => setSelectedPeriod(key as keyof typeof TimePeriodConfig)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-all ${
                selectedPeriod === key
                  ? 'bg-blue-500 text-white shadow-md'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {config.label}
            </button>
          ))}
        </div>

        {/* Metric Selector */}
        <div className="flex flex-wrap gap-2">
          {Object.entries(MetricConfig).map(([key, config]) => (
            <button
              key={key}
              onClick={() => setSelectedMetric(key as keyof typeof MetricConfig)}
              className={`px-4 py-2 rounded-full text-sm font-medium transition-all ${
                selectedMetric === key
                  ? 'text-white shadow-lg'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
              style={{
                backgroundColor: selectedMetric === key ? config.color : undefined
              }}
            >
              {config.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chart Area */}
      <div className="flex-1 relative">
        <svg
          width="100%"
          height="100%"
          viewBox="0 0 800 350"
          className="overflow-hidden"
        >
          {/* Grid Lines */}
          {/* Horizontal grid lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
            <line
              key={`h-${ratio}`}
              x1="60"
              y1={60 + (200 * ratio)}
              x2="740"
              y2={60 + (200 * ratio)}
              stroke="#f3f4f6"
              strokeWidth="1"
            />
          ))}
          
          {/* Vertical grid lines */}
          {chartData.dateRange.map((date, index) => {
            const x = 60 + (index / (chartData.dateRange.length - 1)) * 680;
            return (
              <line
                key={`v-${date}`}
                x1={x}
                y1="60"
                x2={x}
                y2="260"
                stroke="#f3f4f6"
                strokeWidth="1"
              />
            );
          })}

          {/* Y-axis labels */}
          {[1, 0.75, 0.5, 0.25, 0].map((ratio) => {
            const value = minValue + (range * ratio);
            return (
              <text
                key={ratio}
                x="50"
                y={65 + (200 * (1 - ratio))}
                textAnchor="end"
                className="text-xs fill-gray-500"
              >
                {Math.round(value)}{selectedConfig.suffix}
              </text>
            );
          })}

          {/* X-axis date labels */}
          {chartData.dateRange.map((date, index) => {
            // Adjust label frequency based on time period
            let labelInterval = 1;
            if (chartData.periodConfig.groupBy === 'day') {
              labelInterval = chartData.periodConfig.historicalDays <= 7 ? 1 : 
                            chartData.periodConfig.historicalDays <= 30 ? 5 : 7;
            } else {
              labelInterval = 4; // Show every 4th week for year view
            }
            
            if (index % labelInterval !== 0) return null;
            
            const x = 60 + (index / (chartData.dateRange.length - 1)) * 680;
            const displayDate = new Date(date).toLocaleDateString('en-US', { 
              month: 'short', 
              day: 'numeric' 
            });
            
            return (
              <text
                key={date}
                x={x}
                y="320"
                textAnchor="middle"
                className="text-xs fill-gray-500"
              >
                {displayDate}
              </text>
            );
          })}

          {/* Chart Line - only connect actual data points */}
          {chartData.chartPoints.length > 1 && (
            <path
              d={chartData.chartPoints.map((point, index) => {
                const normalizedValue = (point.value - minValue) / range;
                const y = 260 - (normalizedValue * 200);
                return `${index === 0 ? 'M' : 'L'} ${point.x} ${y}`;
              }).join(' ')}
              fill="none"
              stroke={selectedConfig.color}
              strokeWidth="3"
              className="drop-shadow-sm"
            />
          )}

          {/* Data Points - only show where data exists */}
          {chartData.chartPoints.map((point, index) => {
            const normalizedValue = (point.value - minValue) / range;
            const y = 260 - (normalizedValue * 200);
            
            return (
              <g key={`${point.date}-${index}`}>
                <circle
                  cx={point.x}
                  cy={y}
                  r="5"
                  fill={selectedConfig.color}
                  className="drop-shadow-sm"
                />
                
                {/* Hover tooltip */}
                <g className="opacity-0 hover:opacity-100 transition-opacity">
                  <rect
                    x={point.x - 40}
                    y={y - 50}
                    width="80"
                    height="40"
                    fill="rgba(0,0,0,0.8)"
                    rx="4"
                  />
                  <text
                    x={point.x}
                    y={y - 35}
                    textAnchor="middle"
                    className="text-xs fill-white"
                  >
                    {point.label}
                  </text>
                  <text
                    x={point.x}
                    y={y - 20}
                    textAnchor="middle"
                    className="text-xs fill-white font-medium"
                  >
                    {Math.round(point.value)}{selectedConfig.suffix}
                  </text>
                </g>
              </g>
            );
          })}
        </svg>
      </div>


    </div>
  );
} 