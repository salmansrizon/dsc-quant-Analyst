import { useState, useEffect } from 'react';
import api from '../api/client';
import { Users, Trash2, Shield, User } from 'lucide-react';

export default function AdminUsers() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [editUser, setEditUser] = useState(null);

  const fetchUsers = () => {
    setLoading(true);
    api.get('/api/admin/users')
      .then(setUsers)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => { fetchUsers(); }, []);

  const updateRole = async (userId, newRole) => {
    await api.put(`/api/admin/users/${userId}`, { role: newRole });
    fetchUsers();
    setEditUser(null);
  };

  const deleteUser = async (userId) => {
    if (!confirm('Delete this user?')) return;
    await api.delete(`/api/admin/users/${userId}`);
    fetchUsers();
  };

  return (
    <div className="page-content">
      <h1 className="page-title" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <Users size={24} color="var(--color-accent)" /> User Management
      </h1>

      <div className="card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Phone</th>
              <th>Role</th>
              <th>Joined</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u, i) => (
              <tr key={i}>
                <td style={{ fontWeight: 600, fontFamily: 'var(--font-family)' }}>{u.full_name}</td>
                <td style={{ fontFamily: 'var(--font-family)' }}>{u.email}</td>
                <td>{u.phone}</td>
                <td>
                  <span className={`badge ${u.role === 'admin' ? 'badge-warning' : 'badge-accent'}`}>{u.role}</span>
                </td>
                <td style={{ color: 'var(--color-text-muted)', fontFamily: 'var(--font-family)' }}>
                  {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
                </td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button
                      className="btn btn-secondary btn-sm"
                      onClick={() => updateRole(u.id, u.role === 'admin' ? 'user' : 'admin')}
                      title={u.role === 'admin' ? 'Demote to User' : 'Promote to Admin'}
                    >
                      {u.role === 'admin' ? <User size={14} /> : <Shield size={14} />}
                    </button>
                    <button className="btn btn-danger btn-sm" onClick={() => deleteUser(u.id)} title="Delete User">
                      <Trash2 size={14} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
