import React, { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { VARIANT_COLOR_VAR } from '../ui/Badge';

interface MarketSummaryData {
  summary: {
    ltp: string;
    change: string;
    sectors: number;
    topStocks?: number;
  };
  sectors: {
    name: string;
    count: number;
    change: number;
  }[];
}

export default function MarketSummary({ client }: { client: AxiosInstance }) {
  const [data, setData] = useState<MarketSummaryData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    client.get('/market/summary').then((res) => {
      setData(res.data);
    }).catch((err) => {
      setError(err.message);
    });
  }, [client]);

  if (error) {
    return <div style={{ color: VARIANT_COLOR_VAR.negative }}>Error loading market data: {error}</div>;
  }
  if (!data) {
    return <div className="text-[var(--text-secondary)]">Loading...</div>;
  }

  return (
    <div data-testid="market-summary">
      <h1 className="text-2xl font-bold text-[var(--text-primary)]">Market Summary</h1>
      <p className="text-lg tabular-nums text-[var(--text-primary)]">LTP: {data?.summary?.ltp ?? '—'}</p>
      <p className="text-lg tabular-nums text-[var(--text-primary)]">
        Change: {data?.summary?.change ?? '—'}
      </p>
      <h2 className="mt-4 text-xl font-medium text-[var(--text-primary)]">Sectors Dashboard</h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(data.sectors ?? []).map((sector) => {
          const up = sector.change >= 0;
          const color = up ? VARIANT_COLOR_VAR.positive : VARIANT_COLOR_VAR.negative;
          return (
            <div
              key={sector.name}
              className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-secondary)] p-4"
            >
              <p className="text-sm font-medium" style={{ color }}>{sector.name}</p>
              <p className="text-sm text-[var(--text-secondary)]">{sector.count} stocks</p>
              <p className="text-xs tabular-nums" style={{ color }}>{sector.change.toFixed(2)}% change</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}