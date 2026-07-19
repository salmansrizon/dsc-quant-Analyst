import { useEffect, useState } from 'react';
import type { AxiosInstance } from 'axios';

interface AdminUser {
  id: string;
  email: string;
  role: string;
}

const EXPORTS = [
  { key: 'announcements', label: 'Export Announcements', ext: 'csv' },
  { key: 'price_archive', label: 'Export Price Data', ext: 'csv' },
  { key: 'data_grid', label: 'Export Full Dataset', ext: 'json' },
] as const;

export default function AdminPanel({ client }: { client: AxiosInstance }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [editedRole, setEditedRole] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchUsers();
  }, []);

  const fetchUsers = async () => {
    try {
      const res = await client.get('/admin/users');
      setUsers(res.data);
    } catch {
      setError('Failed to load users');
    }
  };

  const handleDeleteUser = async (userId: string) => {
    try {
      await client.delete(`/admin/users/${userId}`);
      setUsers((prev) => prev.filter((u) => u.id !== userId));
    } catch {
      setError('Failed to delete user');
    }
  };

  const handleEditUser = async (userId: string) => {
    if (!['user', 'admin'].includes(editedRole)) {
      setError('Role must be user or admin');
      return;
    }
    try {
      await client.put(`/admin/users/${userId}`, { role: editedRole });
      setSelectedUser(null);
      setError(null);
      fetchUsers();
    } catch {
      setError('Failed to update user');
    }
  };

  const handleExport = async (type: string, ext: string) => {
    try {
      const res = await client.get(`/admin/export/${type}`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data as Blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${type}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      setError('Export failed');
    }
  };

  return (
    <div className="space-y-6 max-w-3xl mx-auto p-4">
      <h1 className="text-2xl font-bold">User Management &amp; Reporting</h1>
      {error && <p className="text-red-500 text-sm">{error}</p>}

      {users.length > 0 ? (
        <table className="w-full divide-y divide-gray-200">
          <thead>
            <tr>
              <th className="px-4 py-3 text-left">Email</th>
              <th className="px-4 py-3 text-left">Role</th>
              <th className="px-4 py-3 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {users.map((user) => (
              <tr key={user.id}>
                <td className="px-4 py-3">{user.email}</td>
                <td className="px-4 py-3">{user.role}</td>
                <td className="px-4 py-3 text-right space-x-2">
                  <button
                    type="button"
                    onClick={() => {
                      setSelectedUser(user);
                      setEditedRole(user.role);
                    }}
                    className="bg-blue-500 text-white px-3 py-1 rounded-lg"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => handleDeleteUser(user.id)}
                    className="bg-red-500 text-white px-3 py-1 rounded-lg"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p className="text-gray-500">No users found</p>
      )}

      {selectedUser && (
        <div className="p-4 border border-gray-200 rounded-lg" role="dialog" aria-modal="true">
          <h3 className="text-lg font-medium mb-3">Edit User</h3>
          <div className="mb-3">
            <label className="block text-sm text-gray-600 mb-1" htmlFor="edit-email">
              Email
            </label>
            <input
              id="edit-email"
              type="text"
              value={selectedUser.email}
              readOnly
              className="w-full p-2 border border-gray-300 rounded-md bg-gray-50"
            />
          </div>
          <div className="mb-3">
            <label className="block text-sm text-gray-600 mb-1" htmlFor="edit-role">
              New Role
            </label>
            <select
              id="edit-role"
              value={editedRole}
              onChange={(e) => setEditedRole(e.target.value)}
              className="w-full p-2 border border-gray-300 rounded-md"
            >
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => handleEditUser(selectedUser.id)}
              className="bg-green-500 text-white px-3 py-2 rounded-lg"
            >
              Save
            </button>
            <button
              type="button"
              onClick={() => setSelectedUser(null)}
              className="bg-gray-500 text-white px-3 py-2 rounded-lg"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      <div className="space-y-4 p-4 bg-gray-100 rounded-lg">
        <h2 className="text-xl font-bold">Data Export</h2>
        <div className="flex flex-wrap gap-3">
          {EXPORTS.map((e) => (
            <button
              key={e.key}
              type="button"
              onClick={() => handleExport(e.key, e.ext)}
              className="bg-indigo-600 text-white px-4 py-2 rounded-lg hover:bg-indigo-700"
            >
              {e.label}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
