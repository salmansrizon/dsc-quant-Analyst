import React, { useState, useEffect } from 'react';
import type { AxiosInstance } from 'axios';
import MarketSummary from '../components/MarketSummary/DashboardSummary';
import SectorPerformanceChart from '../components/MarketChart/SectorPerformanceChart';

interface DashboardProps {
  client: AxiosInstance;
}

function Dashboard({ client }: DashboardProps) {
  const [summary, setSummary] = useState<any>(null);

  useEffect(() => {
    client.get('/market/summary').then((res) => {
      setSummary(res.data);
    });
  }, [client]);

  if (!summary) return <div>Loading...</div>;

  return (
    <div data-testid="dashboard-container" className="min-h-96">
      <h1 className="text-2xl font-bold mb-4">Market Dashboard</h1>

      <div className="grid md:grid-cols-2 gap-6">
        <MarketSummary client={client} />
      </div>

      {summary?.sectors?.length > 0 && (
        <div className="mt-8 p-4 bg-gray-50 rounded-lg shadow">
          <SectorPerformanceChart
            chartTitle="Sector Performance"
            data={summary.sectors.map((sector: any) => ({
              sector: sector.name,
              change: sector.change,
              count: sector.count
            }))}
          />
        </div>
      )}
    </div>
  );
}

export default Dashboard;