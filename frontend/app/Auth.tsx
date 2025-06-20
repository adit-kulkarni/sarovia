import React, { useState } from 'react';
import Image from 'next/image';
import { supabase, getURL } from '../supabaseClient';

export default function Auth() {
  const [mode, setMode] = useState<'signup' | 'signin'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [guestLoading, setGuestLoading] = useState(false);

  const handleSignUp = async () => {
    setError(null);
    setSuccess(null);
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setLoading(true);
    const { error } = await supabase.auth.signUp({ 
      email, 
      password,
      options: {
        emailRedirectTo: getURL()
      }
    });
    if (error) {
      setError(error.message);
    } else {
      setSuccess('Sign up successful! Please check your email to confirm your account.');
    }
    setLoading(false);
  };

  const handleSignIn = async () => {
    setError(null);
    setSuccess(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) {
      setError(error.message);
    }
    setLoading(false);
  };

  const handleGuestSignIn = async () => {
    setError(null);
    setSuccess(null);
    setGuestLoading(true);
    const { error } = await supabase.auth.signInAnonymously();
    if (error) {
      setError(error.message);
    }
    setGuestLoading(false);
  };

  const handleGoogleSignIn = async () => {
    setError(null);
    setSuccess(null);
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: getURL()
      }
    });
    if (error) {
      setError(error.message);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'signup') {
      await handleSignUp();
    } else {
      await handleSignIn();
    }
  };

  return (
    <div className="min-h-screen flex">
      {/* Left side - Illustration */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-orange-50 to-orange-100 items-center justify-center p-8">
        <div className="max-w-md text-center">
          {/* Branding at top */}
          <div className="mb-8">
            <h1 className="text-6xl font-bold text-gray-800 mb-3">
              Saro<span className="text-orange-500">|</span>via
            </h1>
            <p className="text-gray-700 text-base font-medium mb-4">
              Learn through conversation. Advance your own way.
            </p>
            <p className="text-xs text-gray-600 italic whitespace-nowrap">
              <span className="font-semibold">Saraswati</span> — Hindu goddess of knowledge, arts, and learning • <span className="font-semibold">Via</span> — Latin for path or road
            </p>
          </div>

          {/* Learning Illustration */}
          <div className="mb-8">
            <Image 
              src="/learning-illustration.png" 
              alt="Person learning with laptop" 
              width={400}
              height={256}
              className="w-full h-64 object-contain"
            />
          </div>
          
          {/* Feature dots */}
          <div className="flex justify-center space-x-2 mt-8">
            <div className="w-2 h-2 bg-orange-500 rounded-full"></div>
            <div className="w-2 h-2 bg-orange-300 rounded-full"></div>
            <div className="w-2 h-2 bg-orange-300 rounded-full"></div>
            <div className="w-2 h-2 bg-orange-300 rounded-full"></div>
          </div>
        </div>
      </div>

      {/* Right side - Login Form */}
      <div className="w-full lg:w-1/2 min-h-screen flex flex-col bg-white">
        <div className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8 overflow-y-auto">
          <div className="w-full max-w-md">
            {/* Mobile logo */}
            <div className="lg:hidden text-center mb-4">
              <h1 className="text-2xl font-bold text-gray-800 mb-2">Sarovia</h1>
              <div className="w-16 h-1 bg-orange-500 mx-auto rounded"></div>
            </div>

            <div className="space-y-3">
              {/* Success/Error messages at top to save space */}
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-600 px-3 py-2 rounded-lg text-sm">
                  {error}
                </div>
              )}
              {success && (
                <div className="bg-green-50 border border-green-200 text-green-600 px-3 py-2 rounded-lg text-sm">
                  {success}
                </div>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Username or email
                </label>
                <input
                  type="email"
                  placeholder="Enter your email"
                  value={email}
                  onChange={e => setEmail(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent text-gray-900 placeholder-gray-400"
                  autoComplete="email"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-600 mb-1">
                  Password
                </label>
                <input
                  type="password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  className="w-full px-4 py-2.5 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent text-gray-900 placeholder-gray-400"
                  autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
                  required
                />
              </div>

              {mode === 'signup' && (
                <div>
                  <label className="block text-sm font-medium text-gray-600 mb-1">
                    Confirm Password
                  </label>
                  <input
                    type="password"
                    placeholder="••••••••••••"
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    className="w-full px-4 py-2.5 rounded-lg border border-gray-200 focus:outline-none focus:ring-2 focus:ring-orange-500 focus:border-transparent text-gray-900 placeholder-gray-400"
                    autoComplete="new-password"
                    required
                  />
                </div>
              )}

              {mode === 'signin' && (
                <div className="text-right">
                  <a href="#" className="text-sm text-orange-600 hover:text-orange-500 font-medium">
                    Forgot password?
                  </a>
                </div>
              )}

              <button
                onClick={handleSubmit}
                disabled={loading}
                className="w-full bg-gray-800 hover:bg-gray-900 text-white font-semibold py-2.5 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (mode === 'signup' ? 'Signing Up...' : 'Signing In...') : (mode === 'signup' ? 'Sign Up' : 'Sign in')}
              </button>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-200"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-4 bg-white text-gray-500">or</span>
                </div>
              </div>

              <button
                onClick={handleGoogleSignIn}
                className="w-full bg-white border border-gray-200 text-gray-700 font-semibold py-2.5 rounded-lg hover:bg-gray-50 transition-colors flex items-center justify-center space-x-2"
              >
                <svg className="w-5 h-5" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                </svg>
                <span>Sign in with Google</span>
              </button>

              <div className="text-center">
                <button
                  onClick={() => setMode(mode === 'signup' ? 'signin' : 'signup')}
                  className="text-gray-600 hover:text-orange-600 font-medium transition-colors"
                >
                  {mode === 'signup' 
                    ? 'Already have an account? Sign in' 
                    : <>Are you new? <span className="text-orange-600 hover:text-orange-500">Create an Account</span></>
                  }
                </button>
              </div>

              {/* Guest access - moved to bottom */}
              <div className="pt-2 border-t border-gray-100">
                <button
                  onClick={handleGuestSignIn}
                  disabled={guestLoading}
                  className="w-full text-gray-500 hover:text-orange-600 font-medium py-2 transition-colors disabled:opacity-50"
                >
                  {guestLoading ? 'Continuing as Guest...' : 'Continue as Guest'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
} 