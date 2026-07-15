"""
Technical indicator calculations (spec section 4).

Pure functions operating on plain Python lists of floats, ordered oldest -> newest.
No BigQuery / pandas dependency so they can be unit-tested offline and reused by
the ETL layer or the API layer alike.

Series-returning functions return a list aligned to the *tail* of the input:
the first `period-1` (or warm-up) points that cannot be computed are omitted, so
callers should zip results against `prices[-len(result):]`.
"""
from __future__ import annotations

import math
from typing import Optional


# ── Moving averages ───────────────────────────────────────────────────────────

def sma(prices: list[float], period: int) -> Optional[float]:
    """Simple moving average of the most recent `period` values."""
    if period <= 0 or len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def sma_series(prices: list[float], period: int) -> list[float]:
    """SMA at every point where a full window is available."""
    if period <= 0 or len(prices) < period:
        return []
    out = []
    window_sum = sum(prices[:period])
    out.append(window_sum / period)
    for i in range(period, len(prices)):
        window_sum += prices[i] - prices[i - period]
        out.append(window_sum / period)
    return out


def ema_series(prices: list[float], period: int) -> list[float]:
    """Exponential moving average, seeded with the first price (spec 4.2)."""
    if period <= 0 or len(prices) < period:
        return []
    k = 2 / (period + 1)
    out = [prices[0]]
    for i in range(1, len(prices)):
        out.append(prices[i] * k + out[-1] * (1 - k))
    return out


def ema(prices: list[float], period: int) -> Optional[float]:
    series = ema_series(prices, period)
    return series[-1] if series else None


# ── RSI (Wilder smoothing, spec 4.3) ──────────────────────────────────────────

def rsi_series(prices: list[float], period: int = 14) -> list[float]:
    if period <= 0 or len(prices) < period + 1:
        return []
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(0.0, c) for c in changes]
    losses = [max(0.0, -c) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = []

    def _rsi(ag: float, al: float) -> float:
        if al == 0:
            return 100.0
        rs = ag / al
        return 100 - (100 / (1 + rs))

    out.append(_rsi(avg_gain, avg_loss))
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(_rsi(avg_gain, avg_loss))
    return out


def rsi(prices: list[float], period: int = 14) -> Optional[float]:
    series = rsi_series(prices, period)
    return series[-1] if series else None


# ── MACD (spec 4.4) ───────────────────────────────────────────────────────────

def macd(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    """Return the latest {macd, signal, histogram} triple, or None if too short."""
    if len(prices) < slow:
        return None
    ema_fast = ema_series(prices, fast)
    ema_slow = ema_series(prices, slow)
    n = min(len(ema_fast), len(ema_slow))
    macd_line = [f - s for f, s in zip(ema_fast[-n:], ema_slow[-n:])]
    signal_line = ema_series(macd_line, signal)
    if not signal_line:
        return None
    m = min(len(macd_line), len(signal_line))
    macd_val = macd_line[-1]
    signal_val = signal_line[-1]
    return {
        "macd": macd_val,
        "signal": signal_val,
        "histogram": macd_val - signal_val,
    }


# ── Bollinger Bands (spec 4.5) ────────────────────────────────────────────────

def bollinger_bands(prices: list[float], period: int = 20, std_dev: float = 2) -> Optional[dict]:
    if len(prices) < period:
        return None
    recent = prices[-period:]
    mean = sum(recent) / period
    variance = sum((p - mean) ** 2 for p in recent) / period
    std = math.sqrt(variance)
    upper = mean + std_dev * std
    lower = mean - std_dev * std
    last = prices[-1]
    percent_b = (last - lower) / (upper - lower) if upper != lower else 0.5
    bandwidth = (upper - lower) / mean if mean != 0 else 0.0
    return {
        "upper": upper,
        "middle": mean,
        "lower": lower,
        "percent_b": percent_b,
        "bandwidth": bandwidth,
    }


# ── ATR (Wilder, spec 4.6) ────────────────────────────────────────────────────

def _true_ranges(highs: list[float], lows: list[float], closes: list[float]) -> list[float]:
    tr = []
    for i in range(1, len(highs)):
        tr.append(max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        ))
    return tr


def atr_series(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> list[float]:
    if not (len(highs) == len(lows) == len(closes)) or len(highs) < period + 1:
        return []
    tr = _true_ranges(highs, lows, closes)
    out = [sum(tr[:period]) / period]
    for i in range(period, len(tr)):
        out.append((out[-1] * (period - 1) + tr[i]) / period)
    return out


def atr(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Optional[float]:
    series = atr_series(highs, lows, closes, period)
    return series[-1] if series else None


# ── Volume analysis (spec 4.7) ────────────────────────────────────────────────

def obv(closes: list[float], volumes: list[float]) -> Optional[float]:
    if len(closes) != len(volumes) or len(closes) < 2:
        return None
    total = 0.0
    for i in range(1, len(closes)):
        if closes[i] > closes[i - 1]:
            total += volumes[i]
        elif closes[i] < closes[i - 1]:
            total -= volumes[i]
    return total


def vwap(prices: list[float], volumes: list[float]) -> Optional[float]:
    if len(prices) != len(volumes) or not prices:
        return None
    denom = sum(volumes)
    if denom == 0:
        return None
    return sum(p * v for p, v in zip(prices, volumes)) / denom


def volume_ratio(volumes: list[float], period: int = 20) -> Optional[float]:
    if len(volumes) < period + 1:
        return None
    avg = sum(volumes[-period - 1:-1]) / period
    if avg == 0:
        return None
    return volumes[-1] / avg


# ── ADX (spec 4.8) ────────────────────────────────────────────────────────────

def adx(highs: list[float], lows: list[float], closes: list[float], period: int = 14) -> Optional[dict]:
    """Return latest {adx, plus_di, minus_di} using Wilder smoothing."""
    n = len(highs)
    if not (n == len(lows) == len(closes)) or n < 2 * period + 1:
        return None

    tr = _true_ranges(highs, lows, closes)
    plus_dm, minus_dm = [], []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)

    # Wilder smoothed sums
    def _wilder(values: list[float]) -> list[float]:
        sm = [sum(values[:period])]
        for i in range(period, len(values)):
            sm.append(sm[-1] - sm[-1] / period + values[i])
        return sm

    tr_s = _wilder(tr)
    plus_s = _wilder(plus_dm)
    minus_s = _wilder(minus_dm)

    dx = []
    for tr_v, p_v, m_v in zip(tr_s, plus_s, minus_s):
        if tr_v == 0:
            dx.append(0.0)
            continue
        plus_di = 100 * p_v / tr_v
        minus_di = 100 * m_v / tr_v
        denom = plus_di + minus_di
        dx.append(100 * abs(plus_di - minus_di) / denom if denom != 0 else 0.0)

    if len(dx) < period:
        return None
    adx_val = sum(dx[:period]) / period
    for i in range(period, len(dx)):
        adx_val = (adx_val * (period - 1) + dx[i]) / period

    tr_last, p_last, m_last = tr_s[-1], plus_s[-1], minus_s[-1]
    plus_di_last = 100 * p_last / tr_last if tr_last else 0.0
    minus_di_last = 100 * m_last / tr_last if tr_last else 0.0
    return {"adx": adx_val, "plus_di": plus_di_last, "minus_di": minus_di_last}


# ── Cross-over signal detection (spec 4.1 / 4.4) ──────────────────────────────

def detect_ma_cross(prices: list[float], fast: int = 50, slow: int = 200) -> Optional[str]:
    """Golden/Death cross on SMA(fast) vs SMA(slow)."""
    if len(prices) < slow + 1:
        return None
    fast_now, slow_now = sma(prices, fast), sma(prices, slow)
    fast_prev, slow_prev = sma(prices[:-1], fast), sma(prices[:-1], slow)
    if None in (fast_now, slow_now, fast_prev, slow_prev):
        return None
    if fast_prev <= slow_prev and fast_now > slow_now:
        return "GOLDEN_CROSS_BUY"
    if fast_prev >= slow_prev and fast_now < slow_now:
        return "DEATH_CROSS_SELL"
    return None


def rsi_signal(value: Optional[float], overbought: float = 70, oversold: float = 30) -> Optional[str]:
    if value is None:
        return None
    if value >= overbought:
        return "OVERBOUGHT"
    if value <= oversold:
        return "OVERSOLD"
    return "NEUTRAL"


def detect_ema_cross(prices: list[float], fast: int = 12, slow: int = 26) -> Optional[str]:
    """EMA(fast) vs EMA(slow) crossover on the last bar (spec 4.2)."""
    if len(prices) < slow + 1:
        return None
    fast_now, slow_now = ema(prices, fast), ema(prices, slow)
    fast_prev, slow_prev = ema(prices[:-1], fast), ema(prices[:-1], slow)
    if None in (fast_now, slow_now, fast_prev, slow_prev):
        return None
    if fast_prev <= slow_prev and fast_now > slow_now:
        return "BUY"
    if fast_prev >= slow_prev and fast_now < slow_now:
        return "SELL"
    return None


def detect_macd_cross(prices: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[str]:
    """MACD line vs signal line crossover on the last bar (spec 4.4)."""
    now = macd(prices, fast, slow, signal)
    prev = macd(prices[:-1], fast, slow, signal) if len(prices) > slow else None
    if now is None or prev is None:
        return None
    if prev["histogram"] <= 0 and now["histogram"] > 0:
        return "BUY"
    if prev["histogram"] >= 0 and now["histogram"] < 0:
        return "SELL"
    return None


def bollinger_signal(bands: Optional[dict]) -> Optional[str]:
    """Position of price within the bands via %B (spec 4.5)."""
    if not bands:
        return None
    pb = bands["percent_b"]
    if pb >= 1:
        return "BREAKOUT_UP"
    if pb <= 0:
        return "BREAKDOWN"
    if pb >= 0.8:
        return "OVERBOUGHT"
    if pb <= 0.2:
        return "OVERSOLD"
    return "NEUTRAL"


def volume_signal(ratio: Optional[float], spike: float = 2.0) -> Optional[str]:
    """Volume-spike detection vs the 20-day average (spec 4.7)."""
    if ratio is None:
        return None
    return "SPIKE" if ratio >= spike else "NORMAL"


def adx_signal(a: Optional[dict], strong: float = 25) -> Optional[str]:
    """Trend strength + direction from ADX / +DI / -DI (spec 4.8)."""
    if not a:
        return None
    if a["adx"] < strong:
        return "RANGING"
    return "TREND_UP" if a["plus_di"] >= a["minus_di"] else "TREND_DOWN"


def detect_divergence(prices: list[float], indicator: list[float], lookback: int = 14) -> Optional[str]:
    """Basic v1 divergence: compare price direction vs an indicator's direction
    over `lookback` bars (spec 4.3 / 4.4). A fuller swing-pivot detector is
    deferred — this flags the coarse price-up/indicator-down disagreement only.
    """
    if len(prices) <= lookback or len(indicator) <= lookback:
        return None
    price_delta = prices[-1] - prices[-1 - lookback]
    ind_delta = indicator[-1] - indicator[-1 - lookback]
    if price_delta < 0 and ind_delta > 0:
        return "BULLISH_DIVERGENCE"
    if price_delta > 0 and ind_delta < 0:
        return "BEARISH_DIVERGENCE"
    return None


def compute_all(
    closes: list[float],
    highs: Optional[list[float]] = None,
    lows: Optional[list[float]] = None,
    volumes: Optional[list[float]] = None,
) -> dict:
    """Bundle the full v1 indicator set for a single symbol's price series."""
    result: dict = {
        "sma_20": sma(closes, 20),
        "sma_50": sma(closes, 50),
        "sma_100": sma(closes, 100),
        "sma_200": sma(closes, 200),
        "ema_12": ema(closes, 12),
        "ema_26": ema(closes, 26),
        "rsi_14": rsi(closes, 14),
        "macd": macd(closes),
        "bollinger": bollinger_bands(closes),
        "ma_cross": detect_ma_cross(closes),
    }
    # Signals (spec 4.x tables). Computed per-request against the latest bar;
    # not persisted — historical signal logging is out of the v1 on-read design.
    signals = {
        "ma_cross": result["ma_cross"],
        "ema_cross": detect_ema_cross(closes),
        "macd_cross": detect_macd_cross(closes),
        "rsi": rsi_signal(result["rsi_14"]),
        "bollinger": bollinger_signal(result["bollinger"]),
    }
    rsi_hist = rsi_series(closes, 14)
    if rsi_hist:
        signals["rsi_divergence"] = detect_divergence(closes[-len(rsi_hist):], rsi_hist)

    if highs and lows:
        result["atr_14"] = atr(highs, lows, closes, 14)
        adx_val = adx(highs, lows, closes, 14)
        result["adx"] = adx_val
        signals["adx"] = adx_signal(adx_val)
    if volumes:
        result["obv"] = obv(closes, volumes)
        result["vwap"] = vwap(closes, volumes)
        vr = volume_ratio(volumes, 20)
        result["volume_ratio"] = vr
        signals["volume"] = volume_signal(vr)

    result["signals"] = signals
    result["signal_rsi"] = signals["rsi"]  # kept for backwards compatibility
    return result
