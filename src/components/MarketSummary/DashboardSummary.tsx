import React, { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';

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
    return <div className="text-red-500">Error loading market data: {error}</div>;
  }
  if (!data) {
    return <div className="text-gray-500">Loading...</div>;
  }

  return (
    <div data-testid="market-summary">
      <h1 className="text-2xl font-bold">Market Summary</h1>
      <p className="text-lg">LTP: {data?.summary?.ltp ?? '—'}</p>
      <p className="text-lg">Change: {data?.summary?.change ?? '—'}</p>
      <h2 className="mt-4 text-xl font-medium">Sectors Dashboard</h2>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {(data.sectors ?? []).map((sector) => {
          const up = sector.change >= 0;
          const bgClass = up ? 'bg-green-100' : 'bg-red-100';
          const textColor = up ? 'text-green-800' : 'text-red-800';
          return (
            <div key={sector.name} className={`p-4 rounded-sm ${bgClass} border border-gray-200`}>
              <p className={`${textColor} font-medium text-sm`}>{sector.name}</p>
              <p className="text-sm">{sector.count} stocks</p>
              <p className="text-xs">{sector.change.toFixed(2)}% change</p>
              </div>
            );
        })}
      </div>
    </div>
  );
}