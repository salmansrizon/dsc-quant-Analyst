import React, { useState, useEffect, useRef } from 'react';
import { Search, TrendingUp, TrendingDown } from 'lucide-react';
import { colors } from '../design';
import apiClient from '../api/client';

/**
 * Reusable symbol search input with a live, debounced autocomplete dropdown.
 * Backed by GET /api/market/stocks?search=… (case-insensitive substring match).
 *
 * Props:
 *   value, onChange        – controlled text value
 *   onSelect(row)          – called with the full market row when a suggestion is chosen
 *   onSubmitRaw(text)      – optional: Enter with no suggestion chosen (e.g. open drawer for typed text)
 *   placeholder, showIcon, autoFocus, inputRef, inputStyle
 */
export const SymbolSearch = ({
  value,
  onChange,
  onSelect,
  onSubmitRaw,
  placeholder = 'Search symbol…',
  showIcon = true,
  autoFocus = false,
  inputRef,
  inputStyle = {},
}) => {
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const boxRef = useRef(null);
  const focusedRef = useRef(false);
  const justSelected = useRef(false);

  // Debounced lookup
  useEffect(() => {
    const term = (value || '').trim();
    if (justSelected.current) { justSelected.current = false; return; }
    if (!term) { setResults([]); setLoading(false); setOpen(false); return; }
    setLoading(true);
    const handle = setTimeout(async () => {
      try {
        const rows = await apiClient.get(`/market/stocks?search=${encodeURIComponent(term)}&limit=8`);
        setResults(Array.isArray(rows) ? rows : []);
        if (focusedRef.current) setOpen(true);
        setActiveIndex(-1);
      } catch {
        setResults([]);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [value]);

  // Close when clicking outside
  useEffect(() => {
    const onClick = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, []);

  const choose = (row) => {
    justSelected.current = true;
    onChange?.(row.Symbol);
    onSelect?.(row);
    setResults([]);
    setOpen(false);
    setActiveIndex(-1);
  };

  const onKeyDown = (e) => {
    if (open && results.length > 0) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setActiveIndex(i => (i + 1) % results.length); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setActiveIndex(i => (i <= 0 ? results.length - 1 : i - 1)); return; }
      if (e.key === 'Escape') { setOpen(false); return; }
      if (e.key === 'Enter') {
        e.preventDefault();
        choose(activeIndex >= 0 && results[activeIndex] ? results[activeIndex] : results[0]);
        return;
      }
    }
    if (e.key === 'Enter' && onSubmitRaw) { e.preventDefault(); onSubmitRaw(value); }
  };

  const baseInput = {
    background: colors.surface2, border: `1px solid ${colors.border}`, borderRadius: 3,
    color: colors.textPrimary, padding: showIcon ? '6px 10px 6px 30px' : '6px 10px',
    fontSize: 13, outline: 'none', width: '100%',
  };

  return (
    <div ref={boxRef} style={{ position: 'relative', width: '100%' }}>
      {showIcon && (
        <Search size={14} style={{ position: 'absolute', left: 10, top: 'calc(50% - 7px)', color: colors.textSecondary, pointerEvents: 'none' }} />
      )}
      <input
        ref={inputRef}
        value={value}
        onChange={e => onChange?.(e.target.value)}
        onKeyDown={onKeyDown}
        onFocus={() => { focusedRef.current = true; if (results.length > 0) setOpen(true); }}
        onBlur={() => { focusedRef.current = false; setTimeout(() => setOpen(false), 120); }}
        placeholder={placeholder}
        autoComplete="off"
        autoFocus={autoFocus}
        style={{ ...baseInput, ...inputStyle }}
      />

      {open && (value || '').trim() && (
        <div style={{
          position: 'absolute', top: 'calc(100% + 4px)', left: 0, right: 0,
          background: colors.surface, border: `1px solid ${colors.border}`, borderRadius: 4,
          boxShadow: '0 8px 24px rgba(0,0,0,0.5)', zIndex: 300, overflow: 'hidden', maxHeight: 300, overflowY: 'auto',
        }}>
          {loading && results.length === 0 && (
            <div style={{ padding: '10px 12px', color: colors.textSecondary, fontSize: 13 }}>Searching…</div>
          )}
          {!loading && results.length === 0 && (
            <div style={{ padding: '10px 12px', color: colors.textSecondary, fontSize: 13 }}>No matches for “{value.trim()}”</div>
          )}
          {results.map((r, i) => {
            const pct = r.ChangePct != null ? parseFloat(r.ChangePct) : null;
            const isUp = pct != null && pct >= 0;
            return (
              <button
                key={r.Symbol}
                type="button"
                onMouseDown={(e) => { e.preventDefault(); choose(r); }}
                onMouseEnter={() => setActiveIndex(i)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
                  width: '100%', textAlign: 'left', border: 'none', cursor: 'pointer',
                  background: i === activeIndex ? colors.surface2 : 'transparent',
                  padding: '8px 12px', borderBottom: `1px solid ${colors.border}`,
                }}
              >
                <div style={{ minWidth: 0 }}>
                  <div style={{ color: colors.textPrimary, fontSize: 13, fontWeight: 600 }}>{r.Symbol}</div>
                  {r.Sector && <div style={{ color: colors.textSecondary, fontSize: 11, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.Sector}</div>}
                </div>
                <div style={{ textAlign: 'right', flexShrink: 0 }}>
                  {r.LTP != null && <div style={{ color: colors.textPrimary, fontSize: 13 }}>৳{parseFloat(r.LTP).toFixed(2)}</div>}
                  {pct != null && (
                    <div style={{ color: isUp ? colors.green : colors.red, fontSize: 11, display: 'flex', alignItems: 'center', gap: 2, justifyContent: 'flex-end' }}>
                      {isUp ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                      {isUp ? '+' : ''}{pct.toFixed(2)}%
                    </div>
                  )}
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

/**
 * Fetches the latest market price (LTP) for an exact symbol, debounced.
 * Returns null while empty/unknown/loading. Used to suggest the current
 * market price in buy-price / target-price inputs.
 */
export const useMarketPrice = (symbol) => {
  const [price, setPrice] = useState(null);
  useEffect(() => {
    const sym = (symbol || '').trim().toUpperCase();
    if (!sym) { setPrice(null); return; }
    let cancelled = false;
    const handle = setTimeout(() => {
      apiClient.get(`/market/stocks/${encodeURIComponent(sym)}`)
        .then(d => { if (!cancelled) setPrice(d && d.LTP != null ? parseFloat(d.LTP) : null); })
        .catch(() => { if (!cancelled) setPrice(null); });
    }, 350);
    return () => { cancelled = true; clearTimeout(handle); };
  }, [symbol]);
  return price;
};
