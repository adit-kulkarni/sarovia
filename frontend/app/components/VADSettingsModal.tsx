'use client';

import React, { useState } from 'react';

interface VADSettingsModalProps {
  isOpen: boolean;
  onConfirm: (settings: VADSettings) => void;
  onCancel: () => void;
}

export interface VADSettings {
  type: 'semantic' | 'disabled';
  eagerness?: 'low' | 'medium' | 'high';
}

const VADSettingsModal: React.FC<VADSettingsModalProps> = ({
  isOpen,
  onConfirm,
  onCancel
}) => {
  const [vadType, setVadType] = useState<'semantic' | 'disabled'>('semantic');
  const [eagerness, setEagerness] = useState<'low' | 'medium' | 'high'>('low');

  if (!isOpen) return null;

  const handleConfirm = () => {
    const settings: VADSettings = {
      type: vadType,
      ...(vadType === 'semantic' && { eagerness })
    };
    onConfirm(settings);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[9999]">
      <div className="bg-white/95 backdrop-blur-sm rounded-xl shadow-lg p-8 max-w-lg w-full mx-4 border border-orange-100">
        <h2 className="text-2xl font-bold mb-6 text-gray-800">Conversation Settings</h2>
        
        <div className="space-y-6">
          <div>
            <label className="block text-sm font-semibold text-gray-700 mb-3">
              Response Mode
            </label>
            <div className="space-y-3">
              <label className="flex items-center p-3 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50 transition-colors cursor-pointer">
                <input
                  type="radio"
                  name="vadType"
                  value="semantic"
                  checked={vadType === 'semantic'}
                  onChange={(e) => setVadType(e.target.value as 'semantic')}
                  className="mr-3 text-orange-500 focus:ring-orange-500"
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-800">Smart Detection</div>
                </div>
                <div className="relative group">
                  <div className="w-5 h-5 bg-gray-300 rounded-full flex items-center justify-center text-xs text-white cursor-help">
                    i
                  </div>
                  <div className="absolute right-0 top-6 w-64 p-2 bg-gray-800 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    AI understands when you&apos;re done speaking and responds naturally
                  </div>
                </div>
              </label>
              
              <label className="flex items-center p-3 rounded-lg border border-gray-200 hover:border-orange-300 hover:bg-orange-50 transition-colors cursor-pointer">
                <input
                  type="radio"
                  name="vadType"
                  value="disabled"
                  checked={vadType === 'disabled'}
                  onChange={(e) => setVadType(e.target.value as 'disabled')}
                  className="mr-3 text-orange-500 focus:ring-orange-500"
                />
                <div className="flex-1">
                  <div className="font-medium text-gray-800">Manual Control</div>
                </div>
                <div className="relative group">
                  <div className="w-5 h-5 bg-gray-300 rounded-full flex items-center justify-center text-xs text-white cursor-help">
                    i
                  </div>
                  <div className="absolute right-0 top-6 w-64 p-2 bg-gray-800 text-white text-sm rounded-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10">
                    Press a button when you want to send your message
                  </div>
                </div>
              </label>
            </div>
          </div>

          {vadType === 'semantic' && (
            <div className="bg-orange-50 rounded-lg p-4 border border-orange-200">
              <label className="block text-sm font-semibold text-gray-700 mb-3">
                Response Speed
              </label>
              <select
                value={eagerness}
                onChange={(e) => setEagerness(e.target.value as 'low' | 'medium' | 'high')}
                className="w-full p-3 border border-orange-200 rounded-lg bg-white focus:ring-2 focus:ring-orange-500 focus:border-orange-500"
              >
                <option value="low">Patient</option>
                <option value="medium">Balanced</option>
                <option value="high">Quick</option>
              </select>
            </div>
          )}
        </div>

        <div className="flex justify-end space-x-3 mt-8">
          <button
            onClick={onCancel}
            className="px-6 py-3 text-gray-600 border border-gray-300 rounded-full hover:bg-gray-50 transition-colors font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleConfirm}
            className="px-8 py-3 bg-orange-500 text-white rounded-full hover:bg-orange-600 transition-colors font-medium"
          >
            Start Conversation
          </button>
        </div>
      </div>
    </div>
  );
};

export default VADSettingsModal; 