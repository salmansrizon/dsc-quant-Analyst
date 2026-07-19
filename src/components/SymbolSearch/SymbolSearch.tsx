import { useEffect, useRef, useState } from 'react';
import type { AxiosInstance } from 'axios';
import { Search } from 'lucide-react';
import type { MarketRow } from '../../api/marketTypes';
import PriceChange from '../PriceChange/PriceChange';

export type { MarketRow };

interface SymbolSearchProps {
  client: AxiosInstance;
  value: string;
  onChange: (text: string) => void;
  onSelect?: (row: MarketRow) => void;
  placeholder?: string;
  autoFocus?: boolean;
}

/**
 * Debounced symbol autocomplete (ported from main's SymbolSearch onto the TS
 * trunk, #82). Backed by GET /market/stocks?search= (case-insensitive substring
 * match). Controlled: the parent owns the text; onSelect fires with the full
 * market row when a suggestion is chosen (keyboard or mouse).
 */
export default function SymbolSearch({
  client,
  value,
  onChange,
  onSelect,
  placeholder = 'Search symbol…',
  autoFocus = false,
}: SymbolSearchProps) {
  const [results, setResults] = useState<MarketRow[]>([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const boxRef = useRef<HTMLDivElement>(null);
  const focusedRef = useRef(false);
  const justSelected = useRef(false);

  useEffect(() => {
    const term = (value || '').trim();
    // A selection sets the text to the chosen symbol; don't re-query for it.
    if (justSelected.current) {
      justSelected.current = false;
      return;
    }
    if (!term) {
      setResults([]);
      setLoading(false);
      setOpen(false);
      return;
    }
    setLoading(true);
    const handle = setTimeout(async () => {
      try {
        const res = await client.get(
          `/market/stocks?search=${encodeURIComponent(term)}&limit=8`,
        );
        setResults(Array.isArray(res.data) ? res.data : []);
        if (focusedRef.current) setOpen(true);
        setActiveIndex(-1);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [value, client]);

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const choose = (row: MarketRow) => {
    justSelected.current = true;
    onChange(row.Symbol);
    onSelect?.(row);
    setResults([]);
    setOpen(false);
    setActiveIndex(-1);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (!open || results.length === 0) return;
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => (i + 1) % results.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (e.key === 'Escape') {
      setOpen(false);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      choose(activeIndex >= 0 ? results[activeIndex] : results[0]);
    }
  };

  return (
    <div ref={boxRef} className="relative w-full">
      <Search
        size={16}
        className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 pointer-events-none"
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value.toUpperCase())}
        onKeyDown={onKeyDown}
        onFocus={() => {
          focusedRef.current = true;
          if (results.length > 0) setOpen(true);
        }}
        onBlur={() => {
          focusedRef.current = false;
          setTimeout(() => setOpen(false), 120);
        }}
        placeholder={placeholder}
        autoComplete="off"
        autoFocus={autoFocus}
        className="border p-2 pl-9 rounded w-full"
      />

      {open && (value || '').trim() && (
        <ul
          role="listbox"
          className="absolute z-30 mt-1 left-0 right-0 bg-white border rounded shadow-lg max-h-72 overflow-y-auto"
        >
          {loading && results.length === 0 && (
            <li className="px-3 py-2 text-sm text-gray-500">Searching…</li>
          )}
          {!loading && results.length === 0 && (
            <li className="px-3 py-2 text-sm text-gray-500">No matches for “{value.trim()}”</li>
          )}
          {results.map((r, i) => (
            <li key={r.Symbol} role="option" aria-selected={i === activeIndex}>
              <button
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(r);
                }}
                onMouseEnter={() => setActiveIndex(i)}
                className={`w-full flex items-center justify-between gap-3 px-3 py-2 text-left border-b last:border-b-0 ${
                  i === activeIndex ? 'bg-indigo-50' : 'hover:bg-gray-50'
                }`}
              >
                <span className="min-w-0">
                  <span className="block text-sm font-semibold text-gray-900">{r.Symbol}</span>
                  {r.Sector && (
                    <span className="block text-xs text-gray-500 truncate">{r.Sector}</span>
                  )}
                </span>
                <span className="text-right shrink-0 text-xs">
                  {r.LTP != null && (
                    <span className="block text-sm text-gray-900">৳{Number(r.LTP).toFixed(2)}</span>
                  )}
                  <span className="justify-end">
                    <PriceChange pct={r.ChangePct} size={12} />
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
