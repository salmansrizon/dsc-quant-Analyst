import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api/client';
import { Search } from 'lucide-react';

export default function SearchDropdown({ placeholder = "Search symbols...", onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [symbols, setSymbols] = useState([]);
  const [show, setShow] = useState(false);
  const dropdownRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    // Cache symbols list
    api.get('/api/symbols').then(data => setSymbols(data)).catch(console.error);

    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShow(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  useEffect(() => {
    if (query.length > 0) {
      const filtered = symbols
        .filter(s => s.Symbol.toLowerCase().includes(query.toLowerCase()))
        .slice(0, 10);
      setResults(filtered);
      setShow(true);
    } else {
      setResults([]);
      setShow(false);
    }
  }, [query, symbols]);

  const handleSelect = (symbol) => {
    setQuery('');
    setShow(false);
    if (onSelect) {
      onSelect(symbol);
    } else {
      navigate(`/symbol/${symbol}`);
    }
  };

  return (
    <div className="search-dropdown-container" ref={dropdownRef} style={{ position: 'relative', width: '100%' }}>
      <div className="topbar-search" style={{ width: '100%' }}>
        <Search size={16} color="var(--color-text-muted)" />
        <input
          type="text"
          placeholder={placeholder}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query.length > 0 && setShow(true)}
        />
      </div>

      {show && results.length > 0 && (
        <div className="dropdown-results card" style={{
          position: 'absolute',
          top: 'calc(100% + 4px)',
          left: 0,
          right: 0,
          zIndex: 1000,
          padding: '4px',
          maxHeight: '300px',
          overflowY: 'auto',
          boxShadow: 'var(--shadow-lg)',
          background: 'var(--color-bg-card)',
          border: '1px solid var(--color-border)'
        }}>
          {results.map((res, i) => (
            <div
              key={i}
              className="dropdown-item"
              onClick={() => handleSelect(res.Symbol)}
              style={{
                padding: '8px 12px',
                cursor: 'pointer',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--font-size-sm)',
                display: 'flex',
                justifyContent: 'space-between',
                transition: 'background var(--transition-fast)'
              }}
              onMouseEnter={(e) => e.target.style.background = 'var(--color-bg-card-hover)'}
              onMouseLeave={(e) => e.target.style.background = 'transparent'}
            >
              <span style={{ fontWeight: 600 }}>{res.Symbol}</span>
              <span style={{ color: 'var(--color-text-muted)', fontSize: 'var(--font-size-xs)' }}>{res.Sector}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
