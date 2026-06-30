import React, { createContext, useContext, useState, useCallback } from 'react';
import { X, CheckCircle, AlertCircle } from 'lucide-react';
import { colors } from '../design';

const ToastContext = createContext(null);
export const useToast = () => useContext(ToastContext);

let _nextId = 0;

export const ToastProvider = ({ children }) => {
  const [toasts, setToasts] = useState([]);

  const show = useCallback((message, type = 'error') => {
    const id = ++_nextId;
    setToasts(prev => [...prev, { id, message, type }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 4500);
  }, []);

  const dismiss = (id) => setToasts(prev => prev.filter(t => t.id !== id));

  const ctx = {
    error: (msg) => show(msg, 'error'),
    success: (msg) => show(msg, 'success'),
  };

  return (
    <ToastContext.Provider value={ctx}>
      {children}
      <div
        role="status"
        aria-live="polite"
        aria-atomic="false"
        aria-label="Notifications"
        style={{ position: 'fixed', top: 16, right: 16, display: 'flex', flexDirection: 'column', gap: 8, zIndex: 9999, pointerEvents: 'none' }}
      >
        {toasts.map(t => (
          <div
            key={t.id}
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px', borderRadius: 4,
              background: t.type === 'error' ? 'var(--color-toast-error)' : 'var(--color-toast-success)',
              border: `1px solid ${t.type === 'error' ? colors.red : colors.green}`,
              fontSize: 13, minWidth: 240, maxWidth: 360, pointerEvents: 'auto',
              animation: 'slideUp 0.2s ease-out',
            }}
          >
            {t.type === 'error'
              ? <AlertCircle size={15} color={colors.red} aria-hidden="true" />
              : <CheckCircle size={15} color={colors.green} aria-hidden="true" />}
            <span style={{ flex: 1, color: colors.textPrimary, lineHeight: 1.4 }}>{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
              style={{ background: 'none', border: 'none', color: colors.textSecondary, cursor: 'pointer', padding: 4, display: 'flex', borderRadius: 2 }}
            >
              <X size={13} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};
