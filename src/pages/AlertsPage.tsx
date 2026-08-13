import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { AlertCircle, Bell, CheckCircle, XCircle } from 'lucide-react';
import { errorMessage } from '../api/errorMessage';
import SymbolSearch from '../components/SymbolSearch/SymbolSearch';
import { Card } from '../components/ui/Card';
import { VARIANT_COLOR_VAR } from '../components/ui/Badge';

interface Alert {
  id: string;
  symbol: string;
  target_price: number;
  direction: 'above' | 'below';
  is_triggered: boolean;
  triggered_at?: string;
  created_at?: string;
}

export default function AlertsPage({ client }: { client: AxiosInstance }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [newAlert, setNewAlert] = useState<{ symbol: string; target_price: number; direction: 'above' | 'below' }>(
    { symbol: '', target_price: 0, direction: 'above' },
  );
  const [loading, setLoading] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = async () => {
    try {
      const res = await client.get('/alerts');
      setAlerts(res.data);
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to load alerts'));
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async () => {
    if (!newAlert.symbol || newAlert.target_price <= 0) {
      setFormError('Provide a valid symbol and price');
      return;
    }
    setFormError(null);
    try {
      const res = await client.post('/alerts', newAlert);
      setAlerts(prev => [...prev, res.data]);
      setNewAlert({ symbol: '', target_price: 0, direction: 'above' });
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to create alert'));
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await client.delete(`/alerts/${id}`);
      setAlerts(prev => prev.filter(a => a.id !== id));
    } catch (err) {
      setFormError(errorMessage(err, 'Failed to delete alert'));
    }
  };

  if (loading) {
    return <div className="py-8 text-center text-[var(--text-secondary)]">Loading alerts...</div>;
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="flex items-center gap-2 text-2xl font-bold text-[var(--text-primary)]">
        <Bell size={24} /> Your Alerts
      </h1>
      {formError && <p className="text-sm" style={{ color: VARIANT_COLOR_VAR.negative }}>{formError}</p>}

      {/* New Alert Form */}
      <Card revealIndex={0}>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <SymbolSearch
            client={client}
            value={newAlert.symbol}
            onChange={symbol => setNewAlert(prev => ({ ...prev, symbol }))}
            onSelect={row => setNewAlert(prev => ({
              ...prev,
              symbol: row.Symbol,
              // Seed the target with the live price so the user edits from a
              // sensible anchor rather than 0 (main's useMarketPrice, inlined).
              target_price: row.LTP != null ? Number(row.LTP) : prev.target_price,
            }))}
            placeholder="Symbol"
          />
          <input
            type="number"
            placeholder="Target Price"
            value={newAlert.target_price || ''}
            onChange={e => setNewAlert({ ...newAlert, target_price: Number(e.target.value) })}
            className="rounded border border-[var(--border-color)] bg-[var(--bg-primary)] p-2 text-[var(--text-primary)]"
          />
          <select
            value={newAlert.direction}
            onChange={e => setNewAlert({ ...newAlert, direction: e.target.value as 'above' | 'below' })}
            className="rounded border border-[var(--border-color)] bg-[var(--bg-primary)] p-2 text-[var(--text-primary)]"
          >
            <option value="above">Above</option>
            <option value="below">Below</option>
          </select>
          <button onClick={handleCreate} className="btn-primary col-span-3 justify-center">
            Add Alert
          </button>
        </div>
      </Card>

      {/* Alerts List */}
      {alerts.length === 0 ? (
        <p className="text-[var(--text-secondary)]">No alerts set.</p>
      ) : (
        <Card revealIndex={1}>
          <div className="overflow-x-auto">
            <table className="w-full divide-y divide-[var(--border-color)] text-sm">
              <thead>
                <tr className="text-left text-[var(--text-secondary)]">
                  <th className="px-4 py-2">Symbol</th>
                  <th className="px-4 py-2">Target</th>
                  <th className="px-4 py-2">Direction</th>
                  <th className="px-4 py-2">Status</th>
                  <th className="px-4 py-2">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]">
                {alerts.map(alert => (
                  <tr key={alert.id}>
                    <td className="px-4 py-2 font-medium text-[var(--text-primary)]">{alert.symbol}</td>
                    <td className="px-4 py-2 tabular-nums text-[var(--text-primary)]">
                      ${alert.target_price.toFixed(2)}
                    </td>
                    <td className="px-4 py-2 capitalize text-[var(--text-primary)]">{alert.direction}</td>
                    <td className="px-4 py-2">
                      {alert.is_triggered ? (
                        <span className="flex items-center gap-1" style={{ color: VARIANT_COLOR_VAR.positive }}>
                          <CheckCircle size={16} /> Triggered
                        </span>
                      ) : (
                        <span className="flex items-center gap-1" style={{ color: VARIANT_COLOR_VAR.warning }}>
                          <AlertCircle size={16} /> Pending
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2">
                      <button
                        onClick={() => handleDelete(alert.id)}
                        className="flex items-center gap-1 hover:underline"
                        style={{ color: VARIANT_COLOR_VAR.negative }}
                      >
                        <XCircle size={16} /> Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
