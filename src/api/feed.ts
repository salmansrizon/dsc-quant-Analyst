import type { AxiosInstance } from 'axios';

export type FeedItemKind = 'nudge' | 'recommendation' | 'watchlist_move' | 'alert';

export interface FeedItem {
  kind: FeedItemKind;
  headline: string;
  reason: string;
  symbol?: string | null;
  symbols: string[];
  sources: string[];
}

export interface Feed {
  items: FeedItem[];
  next_offset: number | null;
  is_default_profile: boolean;
  disclaimer: string;
}

export const DEFAULT_FEED_LIMIT = 20;

// #96: the composed 'for you' home feed — GET /api/feed?limit&offset.
export async function fetchFeed(
  client: AxiosInstance,
  limit = DEFAULT_FEED_LIMIT,
  offset = 0,
): Promise<Feed> {
  const { data } = await client.get<Feed>('/feed', { params: { limit, offset } });
  return data;
}
