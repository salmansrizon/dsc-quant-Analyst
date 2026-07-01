def compute_ema(values: list[float], period: int) -> list[float | None]:
    """Exponential moving average, seeded with the SMA of the first `period` values."""
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result

    k = 2 / (period + 1)
    ema = sum(values[:period]) / period
    result[period - 1] = ema
    for i in range(period, len(values)):
        ema = values[i] * k + ema * (1 - k)
        result[i] = ema
    return result


EMA_PERIODS = (20, 50, 100, 200)


def add_emas(rows: list[dict]) -> list[dict]:
    """Attach EMA20/50/100/200 keys to each row, computed from `Close` in
    chronological (ascending) order — callers must pass rows oldest-first."""
    closes = [r["Close"] for r in rows]
    for period in EMA_PERIODS:
        emas = compute_ema(closes, period)
        for row, ema in zip(rows, emas):
            row[f"EMA{period}"] = ema
    return rows


def compute_macd(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> list[float | None]:
    """MACD histogram (MACD line minus signal line) per point, aligned with
    `closes`, oldest-first. MACD line = EMA(fast) - EMA(slow); signal line =
    EMA(MACD line, signal period)."""
    ema_fast = compute_ema(closes, fast)
    ema_slow = compute_ema(closes, slow)
    macd_line = [
        (f - s) if (f is not None and s is not None) else None
        for f, s in zip(ema_fast, ema_slow)
    ]
    first_valid = next((i for i, v in enumerate(macd_line) if v is not None), len(macd_line))
    signal_tail = compute_ema(macd_line[first_valid:], signal)
    signal_line: list[float | None] = [None] * first_valid + signal_tail
    return [
        (m - s) if (m is not None and s is not None) else None
        for m, s in zip(macd_line, signal_line)
    ]


def compute_stochastic(highs: list[float], lows: list[float], closes: list[float],
                        k_period: int = 14, smooth_k: int = 3) -> list[float | None]:
    """Slow %K per point, aligned with `closes`, oldest-first.
    Raw %K = (Close - LowestLow(k_period)) / (HighestHigh(k_period) - LowestLow(k_period)) * 100,
    smoothed by a `smooth_k`-period SMA."""
    n = len(closes)
    raw_k: list[float | None] = [None] * n
    for i in range(n):
        if i < k_period - 1:
            continue
        window_high = max(highs[i - k_period + 1:i + 1])
        window_low = min(lows[i - k_period + 1:i + 1])
        rng = window_high - window_low
        raw_k[i] = ((closes[i] - window_low) / rng * 100) if rng else 0.0

    slow_k: list[float | None] = [None] * n
    for i in range(n):
        if i < k_period - 1 + smooth_k - 1:
            continue
        window = raw_k[i - smooth_k + 1:i + 1]
        slow_k[i] = sum(window) / smooth_k
    return slow_k
