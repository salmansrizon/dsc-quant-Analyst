import type { AxiosInstance } from 'axios';

// Implicit-signal capture client (#86). Buffers events and flushes in batches to
// POST /api/behaviour, cutting append volume vs one request per event. Fire-and-
// forget: a dropped flush is fine (behaviour is best-effort signal, not a ledger).
//
// We flush via the axios client (not navigator.sendBeacon) because auth is a
// Bearer header the client's interceptor adds — sendBeacon can't set headers.
// Instead we also flush on visibilitychange 'hidden', the reliable "leaving" cue.
export interface BehaviourEvent {
  event_type: 'view' | 'watchlist_add' | 'watchlist_remove' | 'portfolio'
    | 'screener_run' | 'sector_view';
  symbol?: string;
  sector?: string;
  payload?: Record<string, unknown>;
}

let buffer: BehaviourEvent[] = [];
let client: AxiosInstance | null = null;
let timer: ReturnType<typeof setInterval> | null = null;

export function track(event: BehaviourEvent): void {
  buffer.push(event);
}

export function flush(): void {
  if (!client || buffer.length === 0) return;
  const events = buffer;
  buffer = [];
  client.post('/behaviour', { events }).catch(() => { /* best-effort */ });
}

export function initBehaviour(c: AxiosInstance, intervalMs = 10000): () => void {
  client = c;
  timer = setInterval(flush, intervalMs);
  const onHide = () => { if (document.visibilityState === 'hidden') flush(); };
  document.addEventListener('visibilitychange', onHide);
  return () => {
    if (timer) clearInterval(timer);
    document.removeEventListener('visibilitychange', onHide);
    client = null;
  };
}
