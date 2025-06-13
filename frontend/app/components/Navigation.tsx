'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { supabase } from '../../supabaseClient';
import { 
  HomeIcon, 
  BookOpenIcon, 
  ChartBarIcon, 
  UserIcon,
  ClockIcon,
  ArrowRightOnRectangleIcon
} from '@heroicons/react/24/outline';

const Navigation = () => {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

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

  return (
    <>
      {/* Desktop Navigation */}
      <nav className="hidden md:flex fixed left-0 top-0 h-full w-64 bg-white border-r border-orange-100 flex-col">
        <div className="p-4">
          <h1 className="text-xl font-bold text-orange-600">Sarovia</h1>
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
        <div className="flex justify-around">
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
        </div>
      </nav>
    </>
  );
};

export default Navigation; 