"""Unit tests for backend.indicators — pure, no BigQuery needed."""
import math

from backend import indicators as ind


# ── SMA / EMA ─────────────────────────────────────────────────────────────────

def test_sma_basic():
    assert ind.sma([1, 2, 3, 4, 5], 5) == 3.0
    assert ind.sma([2, 4, 6], 2) == 5.0  # (4+6)/2


def test_sma_too_short_returns_none():
    assert ind.sma([1, 2], 5) is None


def test_sma_series_sliding_window():
    # windows: [1,2,3]=2, [2,3,4]=3, [3,4,5]=4
    assert ind.sma_series([1, 2, 3, 4, 5], 3) == [2.0, 3.0, 4.0]


def test_ema_series_seeds_with_first_price():
    series = ind.ema_series([10, 20, 30], 2)
    assert series[0] == 10
    # k = 2/3; second = 20*2/3 + 10*1/3 = 16.666...
    assert math.isclose(series[1], 50 / 3, rel_tol=1e-9)


# ── RSI ───────────────────────────────────────────────────────────────────────

def test_rsi_all_gains_is_100():
    prices = list(range(1, 20))  # strictly increasing
    assert ind.rsi(prices, 14) == 100.0


def test_rsi_within_bounds():
    prices = [44, 44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
              45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28]
    val = ind.rsi(prices, 14)
    assert val is not None
    assert 0 <= val <= 100


def test_rsi_too_short():
    assert ind.rsi([1, 2, 3], 14) is None


# ── MACD ──────────────────────────────────────────────────────────────────────

def test_macd_histogram_is_macd_minus_signal():
    prices = [float(x) for x in range(1, 60)]
    res = ind.macd(prices)
    assert res is not None
    assert math.isclose(res["histogram"], res["macd"] - res["signal"], rel_tol=1e-9)


def test_macd_too_short():
    assert ind.macd([1, 2, 3], fast=12, slow=26) is None


# ── Bollinger ─────────────────────────────────────────────────────────────────

def test_bollinger_constant_series_zero_width():
    res = ind.bollinger_bands([10.0] * 20, 20, 2)
    assert res["upper"] == res["lower"] == res["middle"] == 10.0
    assert res["bandwidth"] == 0.0


def test_bollinger_upper_above_lower():
    prices = [float(x) for x in range(1, 21)]
    res = ind.bollinger_bands(prices, 20, 2)
    assert res["upper"] > res["middle"] > res["lower"]
    assert 0 <= res["percent_b"] <= 1


# ── ATR ───────────────────────────────────────────────────────────────────────

def test_atr_constant_range():
    # every bar has high-low = 2, no gaps -> ATR should be 2
    highs = [11.0] * 20
    lows = [9.0] * 20
    closes = [10.0] * 20
    assert math.isclose(ind.atr(highs, lows, closes, 14), 2.0, rel_tol=1e-9)


def test_atr_length_mismatch_returns_none():
    assert ind.atr([1, 2], [1], [1, 2], 14) is None


# ── Volume ────────────────────────────────────────────────────────────────────

def test_obv_accumulation():
    closes = [10, 11, 10, 12]
    vols = [100, 200, 150, 300]
    # +200 (up), -150 (down), +300 (up) = 350
    assert ind.obv(closes, vols) == 350


def test_vwap():
    prices = [10, 20]
    vols = [1, 3]
    # (10*1 + 20*3)/4 = 70/4 = 17.5
    assert ind.vwap(prices, vols) == 17.5


def test_vwap_zero_volume_none():
    assert ind.vwap([10, 20], [0, 0]) is None


def test_volume_ratio_spike():
    vols = [100.0] * 20 + [300.0]  # today 3x the 20-day avg
    assert math.isclose(ind.volume_ratio(vols, 20), 3.0, rel_tol=1e-9)


# ── ADX ───────────────────────────────────────────────────────────────────────

def test_adx_returns_keys_when_enough_data():
    n = 40
    highs = [10 + i * 0.5 for i in range(n)]
    lows = [9 + i * 0.5 for i in range(n)]
    closes = [9.5 + i * 0.5 for i in range(n)]
    res = ind.adx(highs, lows, closes, 14)
    assert res is not None
    assert set(res) == {"adx", "plus_di", "minus_di"}
    assert res["adx"] >= 0


def test_adx_too_short():
    assert ind.adx([1, 2, 3], [1, 2, 3], [1, 2, 3], 14) is None


# ── Cross detection ───────────────────────────────────────────────────────────

def test_golden_cross_detected():
    # fast below slow, then a jump pushes fast above slow on the last bar
    prices = [10.0] * 200 + [10.0]  # start baseline
    # Build a series where SMA(3) crosses above SMA(5)
    series = [5, 5, 5, 5, 5, 5, 5, 20]  # last value spikes
    assert ind.detect_ma_cross(series, fast=3, slow=5) == "GOLDEN_CROSS_BUY"


def test_death_cross_detected():
    series = [20, 20, 20, 20, 20, 20, 20, 1]
    assert ind.detect_ma_cross(series, fast=3, slow=5) == "DEATH_CROSS_SELL"


def test_rsi_signal_thresholds():
    assert ind.rsi_signal(80) == "OVERBOUGHT"
    assert ind.rsi_signal(20) == "OVERSOLD"
    assert ind.rsi_signal(50) == "NEUTRAL"
    assert ind.rsi_signal(None) is None


def test_ema_guard_returns_none_when_short():
    assert ind.ema([1, 2], 26) is None
    assert ind.ema_series([1, 2], 26) == []


def test_ema_cross_buy():
    series = [5.0] * 30 + [50.0]  # sharp jump flips fast EMA above slow
    assert ind.detect_ema_cross(series, fast=12, slow=26) == "BUY"


def test_macd_cross_directions():
    up = [float(x) for x in range(1, 60)]
    down = [float(x) for x in range(60, 1, -1)]
    assert ind.detect_macd_cross(up) in {"BUY", None}
    assert ind.detect_macd_cross(down) in {"SELL", None}


def test_bollinger_signal_breakout():
    bands = {"percent_b": 1.2, "upper": 1, "middle": 1, "lower": 1, "bandwidth": 0}
    assert ind.bollinger_signal(bands) == "BREAKOUT_UP"
    assert ind.bollinger_signal({"percent_b": 0.5}) == "NEUTRAL"
    assert ind.bollinger_signal(None) is None


def test_volume_signal_spike():
    assert ind.volume_signal(2.5) == "SPIKE"
    assert ind.volume_signal(1.0) == "NORMAL"
    assert ind.volume_signal(None) is None


def test_adx_signal_ranging_vs_trend():
    assert ind.adx_signal({"adx": 10, "plus_di": 5, "minus_di": 3}) == "RANGING"
    assert ind.adx_signal({"adx": 30, "plus_di": 20, "minus_di": 10}) == "TREND_UP"
    assert ind.adx_signal({"adx": 30, "plus_di": 10, "minus_di": 20}) == "TREND_DOWN"
    assert ind.adx_signal(None) is None


def test_divergence_detection():
    prices = [float(x) for x in range(20)]          # rising
    ind_down = [float(20 - x) for x in range(20)]   # falling
    assert ind.detect_divergence(prices, ind_down, 14) == "BEARISH_DIVERGENCE"
    assert ind.detect_divergence(ind_down, prices, 14) == "BULLISH_DIVERGENCE"
    assert ind.detect_divergence([1, 2], [1, 2], 14) is None


def test_compute_all_emits_signals_dict():
    closes = [float(x % 7 + x * 0.1) for x in range(60)]
    res = ind.compute_all(closes, [c + 1 for c in closes], [c - 1 for c in closes],
                          [1000.0] * 60)
    assert "signals" in res
    s = res["signals"]
    assert set(s) >= {"ma_cross", "ema_cross", "macd_cross", "rsi", "bollinger",
                      "adx", "volume"}


# ── Bundle ────────────────────────────────────────────────────────────────────

def test_compute_all_shapes():
    closes = [float(x % 7 + x * 0.1) for x in range(60)]
    highs = [c + 1 for c in closes]
    lows = [c - 1 for c in closes]
    vols = [1000.0 + (x % 5) * 10 for x in range(60)]
    res = ind.compute_all(closes, highs, lows, vols)
    assert res["sma_20"] is not None
    assert res["rsi_14"] is not None
    assert res["macd"] is not None
    assert "atr_14" in res and "vwap" in res
    assert res["signal_rsi"] in {"OVERBOUGHT", "OVERSOLD", "NEUTRAL"}
