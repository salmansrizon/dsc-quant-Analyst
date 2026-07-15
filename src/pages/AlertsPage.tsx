import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { AlertCircle, Bell, CheckCircle, XCircle } from 'lucide-react';

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
    const res = await client.get('/alerts');
    setAlerts(res.data);
    setLoading(false);
  };

  const handleCreate = async () => {
    if (!newAlert.symbol || newAlert.target_price <= 0) {
      setFormError('Provide a valid symbol and price');
      return;
    }
    setFormError(null);
    const res = await client.post('/alerts', newAlert);
    setAlerts(prev => [...prev, res.data]);
    setNewAlert({ symbol: '', target_price: 0, direction: 'above' });
  };

  const handleDelete = async (id: string) => {
    await client.delete(`/alerts/${id}`);
    setAlerts(prev => prev.filter(a => a.id !== id));
  };

  if (loading) return <div className="text-center py-8">Loading alerts...</div>;

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold flex items-center gap-2">
        <Bell size={24} /> Your Alerts
      </h1>
      {formError && <p className="text-red-500 text-sm">{formError}</p>}

        {/* New Alert Form */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 border rounded-lg bg-gray-50">
          <input
            type="text"
            placeholder="Symbol"
            value={newAlert.symbol}
            onChange={e => setNewAlert({ ...newAlert, symbol: e.target.value.toUpperCase() })}
            className="border p-2 rounded"
          />
          <input
            type="number"
            placeholder="Target Price"
            value={newAlert.target_price || ''}
            onChange={e => setNewAlert({ ...newAlert, target_price: Number(e.target.value) })}
            className="border p-2 rounded"
          />
          <select
            value={newAlert.direction}
            onChange={e => setNewAlert({ ...newAlert, direction: e.target.value as any })}
            className="border p-2 rounded"
          >
            <option value="above">Above</option>
            <option value="below">Below</option>
          </select>
          <button
            onClick={handleCreate}
            className="col-span-3 bg-blue-600 text-white py-2 rounded hover:bg-blue-700"
          >
            Add Alert
          </button>
        </div>

        {/* Alerts List */}
        {alerts.length === 0 ? (
          <p className="text-gray-500">No alerts set.</p>
        ) : (
          <table className="w-full divide-y divide-gray-200">
            <thead>
              <tr>
                <th className="px-4 py-2 text-left">Symbol</th>
                <th className="px-4 py-2 text-left">Target</th>
                <th className="px-4 py-2 text-left">Direction</th>
                <th className="px-4 py-2 text-left">Status</th>
                <th className="px-4 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {alerts.map(alert => (
                <tr key={alert.id} className="hover:bg-gray-100">
                  <td className="px-4 py-2">{alert.symbol}</td>
                  <td className="px-4 py-2">${alert.target_price.toFixed(2)}</td>
                  <td className="px-4 py-2 capitalize">{alert.direction}</td>
                  <td className="px-4 py-2">
                    {alert.is_triggered ? (
                      <span className="flex items-center text-green-600">
                        <CheckCircle size={16} /> Triggered
                      </span>
                    ) : (
                      <span className="flex items-center text-yellow-600">
                        <AlertCircle size={16} /> Pending
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-2">
                    <button
                      onClick={() => handleDelete(alert.id)}
                      className="text-red-600 hover:underline"
                    >
                      <XCircle size={16} /> Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
      )}
    </div>
  );
}
