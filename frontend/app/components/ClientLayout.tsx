'use client';

import { usePathname } from 'next/navigation';
import Navigation from './Navigation';
import { useUser } from '../hooks/useUser';
import { ToastProvider } from './Toast';

export default function ClientLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = useUser();
  const pathname = usePathname();
  const showNavigation = !!user;
  const isChatPage = pathname === '/chat';

  return (
    <ToastProvider>
      {showNavigation && <Navigation />}
      <main className={`${showNavigation ? 'md:ml-48' : ''} min-h-screen ${isChatPage ? 'bg-white' : 'bg-gradient-to-br from-orange-50 via-white to-orange-100'}`}>
        {isChatPage ? (
          children
        ) : (
          <div className="p-4 md:p-8">
            {children}
          </div>
        )}
      </main>
    </ToastProvider>
  );
} 