import React from 'react';

const Header = () => {
  return (
    <header className="bg-gradient-to-r from-blue-600 to-indigo-700 text-white p-4 shadow-lg">
      <div className="container mx-auto">
        <h1 className="text-2xl font-bold">Voice Chat Assistant</h1>
        <p className="text-sm text-blue-100">Real-time conversation with AI</p>
      </div>
    </header>
  );
};

export default Header; 