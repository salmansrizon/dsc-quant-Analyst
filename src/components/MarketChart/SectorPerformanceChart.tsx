import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

export interface SectorChange {
  sector: string;
  change: number;
  count: number;
}

export interface ChartProps {
  chartTitle: string;
  data: SectorChange[];
}

export default function SectorPerformanceChart({ chartTitle, data }: ChartProps) {
  return (
    <div className="bg-white shadow p-4 rounded" data-testid="sector-performance-chart">
      {chartTitle && <h2 className="text-sm mb-2 text-gray-600">{chartTitle}</h2>}
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={data}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="sector" tick={{ fontSize: 11 }} interval={0} angle={-30} textAnchor="end" height={60} />
          <YAxis tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(value) => [`${value}%`, 'Change'] as [string, string]} />
          <Bar dataKey="change" radius={[4, 4, 0, 0]}>
            {data.map((entry) => (
              <Cell key={entry.sector} fill={entry.change >= 0 ? '#16a34a' : '#dc2626'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
