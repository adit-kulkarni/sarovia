'use client';

import React, { useState, createContext, useContext, ReactNode } from 'react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  message: string;
  type: ToastType;
  duration?: number;
}

interface ToastContextType {
  addToast: (message: string, type: ToastType, duration?: number) => void;
  removeToast: (id: string) => void;
  showConfirm: (message: string, onConfirm: () => void, onCancel?: () => void) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

interface ToastProviderProps {
  children: ReactNode;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [confirmDialog, setConfirmDialog] = useState<{
    message: string;
    onConfirm: () => void;
    onCancel?: () => void;
  } | null>(null);

  const addToast = (message: string, type: ToastType, duration: number = 5000) => {
    const id = Math.random().toString(36).substr(2, 9);
    const toast: Toast = { id, message, type, duration };
    
    setToasts(prev => [...prev, toast]);
    
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id);
      }, duration);
    }
  };

  const removeToast = (id: string) => {
    setToasts(prev => prev.filter(toast => toast.id !== id));
  };

  const showConfirm = (message: string, onConfirm: () => void, onCancel?: () => void) => {
    setConfirmDialog({
      message,
      onConfirm: () => {
        onConfirm();
        setConfirmDialog(null);
      },
      onCancel: onCancel ? () => {
        onCancel();
        setConfirmDialog(null);
      } : () => setConfirmDialog(null)
    });
  };

  const getToastIcon = (type: ToastType) => {
    switch (type) {
      case 'success': return '✅';
      case 'error': return '❌';
      case 'warning': return '⚠️';
      case 'info': return 'ℹ️';
      default: return 'ℹ️';
    }
  };

  const getToastColors = (type: ToastType) => {
    switch (type) {
      case 'success': return 'bg-green-50 border-green-200 text-green-800';
      case 'error': return 'bg-red-50 border-red-200 text-red-800';
      case 'warning': return 'bg-yellow-50 border-yellow-200 text-yellow-800';
      case 'info': return 'bg-blue-50 border-blue-200 text-blue-800';
      default: return 'bg-gray-50 border-gray-200 text-gray-800';
    }
  };

  return (
    <ToastContext.Provider value={{ addToast, removeToast, showConfirm }}>
      {children}
      
      {/* Toast Container */}
      <div className="fixed bottom-4 right-4 z-50 space-y-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`
              flex items-center gap-3 px-4 py-3 rounded-lg border shadow-lg
              min-w-[300px] max-w-[400px]
              transform transition-all duration-300 ease-out
              animate-slide-in-right
              ${getToastColors(toast.type)}
            `}
            style={{
              animation: 'slideInRight 0.3s ease-out forwards'
            }}
          >
            <span className="text-lg flex-shrink-0">
              {getToastIcon(toast.type)}
            </span>
            <p className="flex-1 text-sm font-medium">
              {toast.message}
            </p>
            <button
              onClick={() => removeToast(toast.id)}
              className="flex-shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      {/* Confirmation Dialog */}
      {confirmDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div 
            className="absolute inset-0 bg-black bg-opacity-50"
            onClick={confirmDialog.onCancel}
          />
          
          {/* Dialog */}
          <div className="relative bg-white rounded-lg shadow-xl p-6 m-4 max-w-md w-full">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Confirm Action
              </h3>
              <p className="text-gray-600">
                {confirmDialog.message}
              </p>
            </div>
            
            <div className="flex justify-end gap-3">
              <button
                onClick={confirmDialog.onCancel}
                className="px-4 py-2 text-gray-600 border border-gray-300 rounded-md hover:bg-gray-50 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={confirmDialog.onConfirm}
                className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>
      )}
    </ToastContext.Provider>
  );
}; 