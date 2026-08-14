import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { Link } from 'react-router-dom';
import { Bell, Lightbulb, Sparkles, TrendingUp, type LucideIcon } from 'lucide-react';
import { AuthContext } from '../../context/AuthContext';
import { Card } from '../ui/Card';
import { DEFAULT_FEED_LIMIT, fetchFeed, type FeedItem, type FeedItemKind } from '../../api/feed';

// #96: idle refresh cadence for the 'for you' feed — behaviour is a 7-day
// rollup, not real-time (#86), so a slow poll surfaces new nudges/alerts
// without hammering the backend. Each tick reloads page 1 only (fresh items
// re-rank to the top anyway); it doesn't preserve a "load more" scroll depth.
const REFRESH_MS = 5 * 60 * 1000;

const KIND_META: Record<FeedItemKind, { label: string; Icon: LucideIcon }> = {
  nudge: { label: 'Strategy', Icon: Lightbulb },
  recommendation: { label: 'For You', Icon: Sparkles },
  watchlist_move: { label: 'Watchlist', Icon: TrendingUp },
  alert: { label: 'Alert', Icon: Bell },
};

function SymbolChip({ symbol }: { symbol: string }) {
  return (
    <Link
      to={`/stock/${symbol}`}
      className="rounded-full border border-[var(--border-color)] px-2 py-0.5 text-xs font-medium text-[var(--accent-blue)] hover:underline"
    >
      {symbol}
    </Link>
  );
}

function FeedCard({ item, revealIndex }: { item: FeedItem; revealIndex: number }) {
  const { label, Icon } = KIND_META[item.kind];
  const symbols = item.symbol ? [item.symbol] : item.symbols;
  return (
    <Card revealIndex={revealIndex}>
      <div className="flex items-center gap-2 text-xs font-medium text-[var(--text-secondary)]">
        <Icon size={14} />
        {label}
      </div>
      <p className="mt-1 text-sm font-semibold text-[var(--text-primary)]">{item.headline}</p>
      <p className="mt-1 text-xs text-[var(--text-secondary)]">{item.reason}</p>
      {symbols.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {symbols.map((s) => (
            <SymbolChip key={s} symbol={s} />
          ))}
        </div>
      )}
    </Card>
  );
}

// #96: the Dashboard's personalized 'for you' surface — composes #93's
// recs/nudges with watchlist moves + alerts via GET /api/feed. Dashboard
// already sits behind PrivateRoute, but AuthProvider resolves `user` async
// (App.tsx gates the route on `token`, not `user`) — this guard just avoids
// firing the request during that brief window before `user` is populated.
export default function HomeFeed({ client }: { client: AxiosInstance }) {
  const { user } = useContext(AuthContext);
  const [items, setItems] = useState<FeedItem[]>([]);
  const [nextOffset, setNextOffset] = useState<number | null>(null);
  const [disclaimer, setDisclaimer] = useState('');
  const [isDefaultProfile, setIsDefaultProfile] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);

  // #96 code-review: the poll (loadFirstPage) and a user-triggered loadMore
  // can race — mirrors useFitScores' cancelled-flag guard against a stale
  // response clobbering fresher state, but as a monotonic id since two
  // different call sites (not one effect) issue requests here. Only the
  // most-recently-*issued* request's response is ever applied.
  const requestIdRef = useRef(0);

  const loadFirstPage = useCallback(() => {
    const id = ++requestIdRef.current;
    setLoading(true);
    fetchFeed(client, DEFAULT_FEED_LIMIT, 0)
      .then((feed) => {
        if (id !== requestIdRef.current) return;
        setItems(feed.items);
        setNextOffset(feed.next_offset);
        setDisclaimer(feed.disclaimer);
        setIsDefaultProfile(feed.is_default_profile);
      })
      .catch(() => {
        /* best-effort — the section just stays empty, like Dashboard's other widgets */
      })
      .finally(() => setLoading(false));
  }, [client]);

  useEffect(() => {
    if (!user) return;
    loadFirstPage();
    const timer = setInterval(loadFirstPage, REFRESH_MS);
    return () => {
      clearInterval(timer);
      requestIdRef.current += 1; // invalidate any response still in flight
    };
  }, [user, loadFirstPage]);

  const loadMore = () => {
    if (nextOffset == null) return;
    const id = ++requestIdRef.current;
    setLoadingMore(true);
    fetchFeed(client, DEFAULT_FEED_LIMIT, nextOffset)
      .then((feed) => {
        if (id !== requestIdRef.current) return;
        setItems((prev) => [...prev, ...feed.items]);
        setNextOffset(feed.next_offset);
      })
      .catch(() => {
        /* best-effort */
      })
      .finally(() => setLoadingMore(false));
  };

  if (!user) return null;

  return (
    <section data-testid="home-feed" className="space-y-3">
      <h2 className="text-lg font-semibold text-[var(--text-primary)]">For You</h2>
      {isDefaultProfile && (
        <p className="text-xs text-[var(--text-secondary)]">
          Complete your profile to personalize your feed.
        </p>
      )}
      {loading ? (
        <p className="text-sm text-[var(--text-secondary)]">Loading your feed…</p>
      ) : items.length === 0 ? (
        <p className="text-sm text-[var(--text-secondary)]">Nothing new right now.</p>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {items.map((item, i) => (
              <FeedCard
                key={`${item.kind}-${item.symbol ?? item.symbols.join(',')}-${i}`}
                item={item}
                revealIndex={i}
              />
            ))}
          </div>
          {nextOffset != null && (
            <button
              type="button"
              onClick={loadMore}
              disabled={loadingMore}
              className="btn-secondary text-xs"
            >
              {loadingMore ? 'Loading…' : 'Load more'}
            </button>
          )}
        </>
      )}
      {disclaimer && <p className="text-xs text-[var(--text-secondary)]">{disclaimer}</p>}
    </section>
  );
}
