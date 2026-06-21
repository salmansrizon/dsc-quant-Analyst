import React from 'react';
import { useAuth } from '../context/AuthContext';
import { ChevronDown } from 'lucide-react';

export const Topbar = () => {
  const { user, logout } = useAuth();

  return (
    <header className="flex items-center justify-between h-16 bg-white shadow-md px-6">
      <div className="flex-1 flex justify-center">
        <form className="relative w-full max-w-xl">
          <input
            type="text"
            placeholder="Search symbols..."
            className="w-full p-3 pr-10 rounded-lg border focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <svg className="absolute inset-y-0 right-3 h-5 w-5 text-gray-400 pointer-events-none" viewBox="0 0 24 24">
            <path d="M15.5 14h-.79l-.28-.27a6.47 6.47 0 001.48-5.34c0-3.59-2.91-6.5-6.5-6.5s-6.5 2.91-6.5 6.5A6.47 6.47 0 004.79 11l-.28.27A8.2 8.2 0 009 18.21V20h2v-1.79a8.2 8.2 0 004.21-5.81zM9 18c4.97 0 9-4.03 9-9s-4.03-9-9-9-9 4.03-9 9 4.03 9 9 9z" fill="currentColor" />
          </svg>
        </form>
      </div>
      <div className="flex items-center gap-4">
        {user && (
          <div className="relative">
            <img src="https://ui-avatars.com/api/?name=${user.full_name}&background=random" alt="Avatar" className="h-10 w-10 rounded-full border-2 border-white" />
            <div className="absolute -right-2 -bottom-2 w-3 h-3 bg-green-500 rounded-full border-2 border-white"></div>
            <span className="ml-3 cursor-pointer">{user.full_name}</span>
          </div>
        )}
        {user && (
          <button onClick={logout} className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600">
            Logout
          </button>
        )}
      </div>
    </header>
  );
};