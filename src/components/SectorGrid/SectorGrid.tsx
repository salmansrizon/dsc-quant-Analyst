import React from 'react';

export interface Sector {
  sector: string;
  count: number;
  change: number;
}

export interface SectorGridProps {
  sectors: Sector[];
}

export default function SectorGrid({ sectors }: SectorGridProps) {
  if (!sectors || sectors.length === 0) {
    return <div className="text-gray-500 text-center py-4">No sector data</div>;
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {sectors.map((s) => (
        <div
          key={s.sector}
          className="bg-white rounded-lg shadow p-4 border border-gray-200"
        >
          <h3 className="text-lg font-semibold mb-2">{s.sector}</h3>
          <p className="text-gray-600 mb-1">{s.count} stocks</p>
          <p
            className={`text-sm font-medium ${
              s.change >= 0 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {s.change.toFixed(2)}%
          </p>
        </div>
      ))}
    </div>
  );
}