// A market row as returned by the /market/* leaderboard endpoints — the shared
// shape SymbolSearch suggestions and Dashboard widgets both render. Endpoint-
// specific extras (Value on leaderboards, MetricValue on extremes) are optional.
export interface MarketRow {
  Symbol: string;
  Sector?: string;
  LTP?: number;
  ChangePct?: number;
  Value?: number;
  MetricValue?: number;
}
