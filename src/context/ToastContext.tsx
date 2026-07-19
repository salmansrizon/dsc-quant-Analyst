import React, { createContext, useCallback, useContext, useState } from 'react';
import { AlertCircle, CheckCircle, X } from 'lucide-react';

type ToastType = 'error' | 'success';
interface Toast {
  id: number;
  message: string;
  type: ToastType;
}
interface ToastApi {
  error: (message: string) => void;
  success: (message: string) => void;
}

// Ported from main's Toast (#82). Inline-styled off the index.css CSS variables
// (there is no Tailwind here), fixed top-right, auto-dismiss after 4.5s.
const ToastContext = createContext<ToastApi>({ error: () => {}, success: () => {} });

export const useToast = () => useContext(ToastContext);

let nextId = 0;

export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const show = useCallback((message: string, type: ToastType) => {
    const id = ++nextId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4500);
  }, []);

  const dismiss = (id: number) => setToasts((prev) => prev.filter((t) => t.id !== id));

  const api: ToastApi = {
    error: (msg) => show(msg, 'error'),
    success: (msg) => show(msg, 'success'),
  };

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        role="status"
        aria-live="polite"
        aria-label="Notifications"
        style={{
          position: 'fixed', top: 16, right: 16, display: 'flex',
          flexDirection: 'column', gap: 8, zIndex: 9999, pointerEvents: 'none',
        }}
      >
        {toasts.map((t) => (
          <div
            key={t.id}
            className="slide-up"
            style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
              borderRadius: 8, minWidth: 240, maxWidth: 360, fontSize: 14,
              pointerEvents: 'auto', background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              border: `1px solid ${t.type === 'error' ? 'var(--accent-red)' : 'var(--accent-green)'}`,
              boxShadow: '0 4px 16px rgba(0,0,0,0.15)',
            }}
          >
            {t.type === 'error' ? (
              <AlertCircle size={16} color="var(--accent-red)" aria-hidden="true" />
            ) : (
              <CheckCircle size={16} color="var(--accent-green)" aria-hidden="true" />
            )}
            <span style={{ flex: 1, lineHeight: 1.4 }}>{t.message}</span>
            <button
              type="button"
              onClick={() => dismiss(t.id)}
              aria-label="Dismiss notification"
              style={{
                background: 'none', border: 'none', cursor: 'pointer', padding: 4,
                display: 'flex', color: 'var(--text-secondary)',
              }}
            >
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
