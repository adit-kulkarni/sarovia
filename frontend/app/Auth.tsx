import React, { useState } from 'react';
import { supabase } from '../supabaseClient';

const contextAvatars = [
  {
    title: 'Market Trader',
    description: 'Negotiating at a market',
    img: 'https://api.dicebear.com/7.x/micah/svg?seed=market',
  },
  {
    title: 'Waiter',
    description: 'Ordering at a restaurant',
    img: 'https://api.dicebear.com/7.x/micah/svg?seed=waiter',
  },
  {
    title: 'Barista',
    description: 'Asking someone out for drinks',
    img: 'https://api.dicebear.com/7.x/micah/svg?seed=barista',
  },
  {
    title: 'New Acquaintance',
    description: 'Introducing yourself',
    img: 'https://api.dicebear.com/7.x/micah/svg?seed=acquaintance',
  },
  {
    title: 'Karaoke Host',
    description: 'On a karaoke night out',
    img: 'https://api.dicebear.com/7.x/micah/svg?seed=karaoke',
  },
  {
    title: 'City Guide',
    description: 'Finding things to do in the city',
    img: 'https://api.dicebear.com/7.x/micah/svg?seed=cityguide',
  },
];

export default function Auth() {
  const [mode, setMode] = useState<'signup' | 'signin'>('signup');
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
    const { error } = await supabase.auth.signUp({ email, password });
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (mode === 'signup') {
      await handleSignUp();
    } else {
      await handleSignIn();
    }
  };

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-gradient-to-br from-yellow-50 to-orange-100 p-4 relative overflow-x-hidden">
      {/* Avatar cards - desktop: around the auth card, mobile: scrollable row */}
      <div className="hidden md:flex absolute w-full max-w-4xl justify-between top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 pointer-events-none z-0">
        {contextAvatars.map((avatar, idx) => (
          <div key={idx} className="flex flex-col items-center bg-white/90 border border-orange-100 rounded-xl shadow-lg p-3 mx-2 w-32 pointer-events-auto">
            <img src={avatar.img} alt={avatar.title} className="w-16 h-16 rounded-full object-cover border-2 border-orange-200 mb-2" />
            <div className="font-semibold text-orange-700 text-sm text-center">{avatar.title}</div>
            <div className="text-xs text-gray-500 text-center">{avatar.description}</div>
          </div>
        ))}
      </div>
      {/* Mobile: horizontal scroll */}
      <div className="flex md:hidden w-full overflow-x-auto gap-3 mb-6 z-10">
        {contextAvatars.map((avatar, idx) => (
          <div key={idx} className="flex-shrink-0 flex flex-col items-center bg-white/90 border border-orange-100 rounded-xl shadow-lg p-3 w-32">
            <img src={avatar.img} alt={avatar.title} className="w-16 h-16 rounded-full object-cover border-2 border-orange-200 mb-2" />
            <div className="font-semibold text-orange-700 text-sm text-center">{avatar.title}</div>
            <div className="text-xs text-gray-500 text-center">{avatar.description}</div>
          </div>
        ))}
      </div>
      <div className="bg-white/80 backdrop-blur-sm rounded-3xl shadow-2xl p-8 max-w-md w-full flex flex-col items-center border border-orange-100 z-10">
        <h1 className="text-3xl font-bold text-orange-600 mb-2 text-center">Master Languages</h1>
        <p className="text-gray-600 mb-6 text-center">
          {mode === 'signup' ? 'Sign up to unlock immersive language practice and conversation mastery.' : 'Sign in to continue your language journey.'}
        </p>
        <form className="w-full flex flex-col gap-4" onSubmit={handleSubmit}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            className="w-full px-4 py-2 rounded-lg border border-orange-100 focus:outline-none focus:ring-2 focus:ring-orange-200 text-lg bg-white/90"
            autoComplete="email"
            required
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full px-4 py-2 rounded-lg border border-orange-100 focus:outline-none focus:ring-2 focus:ring-orange-200 text-lg bg-white/90"
            autoComplete={mode === 'signup' ? 'new-password' : 'current-password'}
            required
          />
          {mode === 'signup' && (
            <input
              type="password"
              placeholder="Confirm Password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2 rounded-lg border border-orange-100 focus:outline-none focus:ring-2 focus:ring-orange-200 text-lg bg-white/90"
              autoComplete="new-password"
              required
            />
          )}
          <button
            type="submit"
            disabled={loading}
            className="mt-4 w-full bg-orange-500 hover:bg-orange-600 text-white font-semibold py-2 rounded-lg shadow transition-all text-lg disabled:opacity-60"
          >
            {loading ? (mode === 'signup' ? 'Signing Up...' : 'Signing In...') : (mode === 'signup' ? 'Sign Up' : 'Sign In')}
          </button>
        </form>
        <div className="w-full flex items-center my-4">
          <div className="flex-grow border-t border-orange-100"></div>
          <span className="mx-2 text-gray-400">or</span>
          <div className="flex-grow border-t border-orange-100"></div>
        </div>
        <button
          onClick={() => setMode(mode === 'signup' ? 'signin' : 'signup')}
          className="w-full bg-white border border-orange-400 text-orange-700 font-semibold py-2 rounded-lg shadow hover:bg-orange-50 transition-all text-lg"
        >
          {mode === 'signup' ? 'Already have an account? Sign In' : "Don't have an account? Sign Up"}
        </button>
        <button
          onClick={handleGuestSignIn}
          disabled={guestLoading}
          className="w-full mt-4 bg-orange-100 hover:bg-orange-200 text-orange-700 font-semibold py-2 rounded-lg shadow transition-all text-lg disabled:opacity-60"
        >
          {guestLoading ? 'Continuing as Guest...' : 'Continue as Guest'}
        </button>
        {error && <div className="text-red-500 mt-4 text-center">{error}</div>}
        {success && <div className="text-green-600 mt-4 text-center">{success}</div>}
      </div>
      <div className="mt-8 text-center text-gray-400 text-sm max-w-md z-10">
        <span className="font-semibold text-orange-600">Why join?</span> <br />
        Unlock personalized language lessons, real-time conversation practice, and track your progress as you master new languages!
      </div>
    </div>
  );
} 