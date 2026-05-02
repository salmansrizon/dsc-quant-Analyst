import { useState, useEffect } from 'react';
import api from '../api/client';
import { Settings, RefreshCcw, Database } from 'lucide-react';

export default function AdminPipeline() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStatus = () => {
    setLoading(true);
    api.get('/api/admin/pipeline-status')
      .then(setStatus)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchStatus(); }, []);

  return (
    <div className="page-content">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 'var(--space-6)' }}>
        <h1 className="page-title" style={{ marginBottom: 0, display: 'flex', alignItems: 'center', gap: 12 }}>
          <Settings size={24} color="var(--color-accent)" /> Pipeline Status
        </h1>
        <button className="btn btn-secondary" onClick={fetchStatus}>
          <RefreshCcw size={16} /> Refresh
        </button>
      </div>

      <div className="card-grid">
        {status && Object.entries(status).map(([table, info]) => (
          <div key={table} className="card stat-card accent">
            <div className="card-header">
              <span className="card-title" style={{ textTransform: 'capitalize' }}>
                {table.replace('lankabd_', '').replace('_', ' ')}
              </span>
              <div className="stat-icon accent">
                <Database size={20} />
              </div>
            </div>
            <div className="card-value">{info.row_count.toLocaleString()}</div>
            <div className="stat-label">Total Rows</div>
            <div style={{ marginTop: 'var(--space-2)', fontSize: 'var(--font-size-xs)', color: 'var(--color-text-muted)' }}>
              Last Sync: {info.last_updated ? new Date(info.last_updated).toLocaleString() : 'Never'}
            </div>
          </div>
        ))}
      </div>

      <div className="card" style={{ marginTop: 'var(--space-6)' }}>
        <div className="card-header">
          <span className="card-title">Recent Activity</span>
        </div>
        <div className="empty-state">
           <p>Log streaming coming soon...</p>
        </div>
      </div>
    </div>
  );
}
