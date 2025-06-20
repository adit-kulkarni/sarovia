'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { supabase } from '../../supabaseClient';
import { useToast } from './Toast';
import { 
  HomeIcon, 
  UserIcon,
  ClockIcon,
  ArrowRightOnRectangleIcon
} from '@heroicons/react/24/outline';

const Navigation = () => {
  const pathname = usePathname();
  const { addToast } = useToast();

  const [debugClicks, setDebugClicks] = useState(0);

  const navigationItems = [
    { name: 'Dashboard', href: '/', icon: HomeIcon },
    { name: 'History', href: '/history', icon: ClockIcon },
    // { name: 'Progress', href: '/progress', icon: ChartBarIcon },
    // { name: 'Curriculum', href: '/curriculum', icon: BookOpenIcon },
    { name: 'Profile', href: '/profile', icon: UserIcon },
  ];

  const handleLogout = async () => {
    try {
      await supabase.auth.signOut();
      // Navigation will be automatically updated via useUser hook
    } catch (error) {
      console.error('Error logging out:', error);
    }
  };

  const handleSentryTest = async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (!session?.access_token) {
        addToast('❌ Not authenticated', 'error');
        return;
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_SERVER_URL || 'http://localhost:8000'}/debug/sentry-test?token=${session.access_token}`);
      const result = await response.json();
      
      if (result.status === 'success') {
        addToast('🎯 Sentry test successful! Check your dashboard.', 'success');
        setDebugClicks(0); // Reset clicks
      } else {
        addToast('❌ Test failed: ' + (result.detail || 'Unknown error'), 'error');
      }
    } catch (error) {
      addToast('❌ Error: ' + (error instanceof Error ? error.message : String(error)), 'error');
    }
  };

  const handleLogoClick = () => {
    setDebugClicks(prev => prev + 1);
    setTimeout(() => setDebugClicks(0), 3000); // Reset after 3 seconds
  };

  return (
    <>
      {/* Desktop Navigation */}
      <nav className="hidden md:flex fixed left-0 top-0 h-full w-48 bg-white border-r border-orange-100 flex-col">
        <div className="p-4 relative group">
          <div 
            className="cursor-pointer"
            onClick={handleLogoClick}
          >
            <h1 className="text-xl font-bold text-orange-600">Sarovia</h1>
          </div>
          
          {/* Secret Debug Button - appears after 5 clicks or on logo hover */}
          {(debugClicks >= 5 || debugClicks > 0) && (
            <button
              onClick={handleSentryTest}
              className="absolute top-2 right-2 w-3 h-3 bg-orange-300 hover:bg-red-500 rounded-full opacity-30 hover:opacity-100 transition-all duration-200"
              title="🧪 Sentry Debug Test"
            />
          )}
          
          {/* Alternative: Always visible but very discrete */}
          <button
            onClick={handleSentryTest}
            className="absolute top-1 right-1 w-2 h-2 bg-gray-200 hover:bg-orange-500 rounded-full opacity-0 group-hover:opacity-50 hover:!opacity-100 transition-all duration-300"
            title="🧪"
          />
        </div>
        <div className="flex-1 px-2 py-4">
          {navigationItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex items-center px-4 py-3 text-sm font-medium rounded-lg mb-2 ${
                  isActive
                    ? 'bg-orange-50 text-orange-600'
                    : 'text-gray-600 hover:bg-orange-50 hover:text-orange-600'
                }`}
              >
                <item.icon className="h-5 w-5 mr-3" />
                {item.name}
              </Link>
            );
          })}
        </div>
        <div className="px-2 pb-4">
          <button
            onClick={handleLogout}
            className="flex items-center w-full px-4 py-3 text-sm font-medium rounded-lg text-gray-600 hover:bg-red-50 hover:text-red-600 transition-colors"
          >
            <ArrowRightOnRectangleIcon className="h-5 w-5 mr-3" />
            Log Out
          </button>
        </div>
      </nav>

      {/* Mobile Navigation */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-orange-100">
        <div className="flex justify-around relative">
          {navigationItems.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.name}
                href={item.href}
                className={`flex flex-col items-center py-2 px-3 ${
                  isActive ? 'text-orange-600' : 'text-gray-600'
                }`}
              >
                <item.icon className="h-6 w-6" />
                <span className="text-xs mt-1">{item.name}</span>
              </Link>
            );
          })}
          <button
            onClick={handleLogout}
            className="flex flex-col items-center py-2 px-3 text-gray-600 hover:text-red-600"
          >
            <ArrowRightOnRectangleIcon className="h-6 w-6" />
            <span className="text-xs mt-1">Log Out</span>
          </button>
          
          {/* Mobile debug button - hidden in corner */}
          <button
            onClick={handleSentryTest}
            className="absolute top-1 right-1 w-2 h-2 bg-gray-100 hover:bg-orange-400 rounded-full opacity-10 hover:opacity-80 transition-all duration-300"
            title="🧪"
          />
        </div>
      </nav>
    </>
  );
};

export default Navigation; 