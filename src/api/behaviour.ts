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
  if (timer) clearInterval(timer);           // a re-init never orphans the prior loop
  timer = setInterval(flush, intervalMs);
  const onHide = () => { if (document.visibilityState === 'hidden') flush(); };
  document.addEventListener('visibilitychange', onHide);
  window.addEventListener('pagehide', flush);   // covers the unload path too
  return () => {
    if (timer) { clearInterval(timer); timer = null; }
    document.removeEventListener('visibilitychange', onHide);
    window.removeEventListener('pagehide', flush);
    client = null;
  };
}

/** Test hook: drop any buffered events + client so cases don't leak into each
 *  other (the buffer/client are module-global singletons). */
export function resetBehaviour(): void {
  buffer = [];
  client = null;
  if (timer) { clearInterval(timer); timer = null; }
}
