"""Sector comparison (#92, spine #84): a stock vs its sector's median, for the
4 metrics #88's cohort machinery already computes. Reuses fit_service's
peer_metrics/sector_of — one bulk read per data source, never a per-symbol
fan-out, the same house rule #88 already set.

Unlike the fit engine (#88), a thin sector is NOT filled from the market-wide
distribution: this widget's whole premise is sector-specific, so a metric
with too few peers is marked `comparable: False` instead of silently
comparing against the wrong cohort.
"""
import statistics

from . import fit_service

MIN_COHORT = fit_service.MIN_COHORT  # same threshold, same reasoning as #88

# (peer_metrics' internal key, the metric id this service exposes, its label).
# "yield_" is peer_metrics' own key (a bare `yield` reads oddly); the response
# always uses the clean "yield".
_METRICS = [
    ("pe", "pe", "P/E"),
    ("pb", "pb", "P/B"),
    ("yield_", "yield", "Dividend Yield %"),
    ("growth", "growth", "EPS Growth %/yr"),
]


def compare(symbol: str) -> dict:
    symbol = symbol.upper()
    sector = fit_service.sector_of(symbol)
    peers = fit_service.peer_metrics(sector) if sector else {}
    subject = peers.get(symbol, {})

    metrics = []
    for peer_key, metric_id, label in _METRICS:
        values = [m[peer_key] for s, m in peers.items()
                  if s != symbol and m.get(peer_key) is not None]
        comparable = len(values) >= MIN_COHORT
        metrics.append({
            "metric": metric_id,
            "label": label,
            "subject_value": subject.get(peer_key),
            "sector_median": statistics.median(values) if comparable else None,
            "peer_count": len(values),
            "comparable": comparable,
        })
    return {"symbol": symbol, "sector": sector, "metrics": metrics}
