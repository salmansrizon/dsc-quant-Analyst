from backend.indicators import compute_ema, add_emas, compute_macd, compute_stochastic


def test_compute_ema_matches_hand_calculated_values():
    # period=3, k=2/(3+1)=0.5. First EMA seeded as SMA([1,2,3])=2.0.
    # EMA[3] = 4*0.5 + 2.0*0.5 = 3.0
    # EMA[4] = 5*0.5 + 3.0*0.5 = 4.0
    result = compute_ema([1, 2, 3, 4, 5], period=3)
    assert result == [None, None, 2.0, 3.0, 4.0]


def test_add_emas_attaches_ema20_50_100_200_keys_to_rows():
    rows = [{"Close": float(i)} for i in range(1, 250)]
    enriched = add_emas(rows)
    assert len(enriched) == len(rows)
    # not enough history yet for EMA200 at the very first row
    assert enriched[0]["EMA200"] is None
    # by the last row, all four EMAs should be populated floats
    last = enriched[-1]
    assert isinstance(last["EMA20"], float)
    assert isinstance(last["EMA50"], float)
    assert isinstance(last["EMA100"], float)
    assert isinstance(last["EMA200"], float)


def test_compute_macd_histogram_is_zero_for_a_linear_price_series():
    # fast=3 (k=0.5), slow=5 (k=1/3) on a straight line [1..10]: EMA of a
    # linear series trails the price by a constant offset, so EMA3-EMA5
    # settles to a constant MACD line of 1.0 once both are seeded (idx 4).
    # The signal line (EMA2 of a constant 1.0 series) is also constant 1.0
    # once seeded (idx 5), so the histogram (MACD - signal) is 0.0 from there.
    closes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    result = compute_macd(closes, fast=3, slow=5, signal=2)
    assert result == [None, None, None, None, None, 0.0, 0.0, 0.0, 0.0, 0.0]


def test_compute_macd_histogram_turns_positive_on_a_price_jump():
    # Same warm-up as above, but the series jumps from 10 to 20 at the end.
    # EMA3 (k=0.5) reacts faster than EMA5 (k=1/3), so the MACD line jumps
    # from a steady 1.0 to 2.5, and since the signal line (EMA2, k=2/3) was
    # still tracking the steady 1.0, it only partially catches up to 2.0 —
    # leaving a positive histogram of 2.5 - 2.0 = 0.5.
    closes = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20]
    result = compute_macd(closes, fast=3, slow=5, signal=2)
    assert result[-1] == 0.5


def test_compute_stochastic_slow_k_matches_hand_calculated_values():
    # k_period=3, smooth_k=2.
    # idx2: window H=[10,12,11]->12, L=[8,9,10]->8, range=4, C=10 -> raw%K=(10-8)/4*100=50.0
    # idx3: window H=[12,11,13]->13, L=[9,10,11]->9, range=4, C=12 -> raw%K=(12-9)/4*100=75.0
    # idx4: window H=[11,13,14]->14, L=[10,11,12]->10, range=4, C=13 -> raw%K=(13-10)/4*100=75.0
    # slow%K[3] = avg(raw%K[2], raw%K[3]) = avg(50.0, 75.0) = 62.5
    # slow%K[4] = avg(raw%K[3], raw%K[4]) = avg(75.0, 75.0) = 75.0
    highs = [10, 12, 11, 13, 14]
    lows = [8, 9, 10, 11, 12]
    closes = [9, 11, 10, 12, 13]
    result = compute_stochastic(highs, lows, closes, k_period=3, smooth_k=2)
    assert result == [None, None, None, 62.5, 75.0]
