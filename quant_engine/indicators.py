"""
indicators.py — Pure Python technical indicator implementations.

All functions take plain lists of floats and return plain lists.
Index i of the output corresponds to candle i.
Values before the indicator has enough data are None.
"""

from __future__ import annotations
from typing import Optional


# ── Primitive functions ────────────────────────────────────────────────────────

def sma(values: list[float], period: int) -> list[Optional[float]]:
    """Simple Moving Average."""
    n = len(values)
    result: list[Optional[float]] = [None] * n
    for i in range(period - 1, n):
        result[i] = sum(values[i - period + 1 : i + 1]) / period
    return result


def ema(values: list[float], period: int) -> list[Optional[float]]:
    """Exponential Moving Average (standard 2/(n+1) smoothing)."""
    k = 2.0 / (period + 1)
    n = len(values)
    result: list[Optional[float]] = [None] * n
    if n < period:
        return result
    # Seed with SMA of first `period` values
    result[period - 1] = sum(values[:period]) / period
    for i in range(period, n):
        result[i] = values[i] * k + result[i - 1] * (1.0 - k)  # type: ignore[operator]
    return result


def rsi(closes: list[float], period: int = 14) -> list[Optional[float]]:
    """
    Relative Strength Index using Wilder's smoothing.
    Returns values in [0, 100].
    """
    n = len(closes)
    result: list[Optional[float]] = [None] * n
    if n < period + 1:
        return result

    gains: list[float] = []
    losses: list[float] = []
    for i in range(1, n):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0.0))
        losses.append(max(-diff, 0.0))

    # First averages (simple mean over first `period` changes)
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def _rsi_from(ag: float, al: float) -> float:
        if al == 0.0:
            return 100.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    result[period] = _rsi_from(avg_gain, avg_loss)

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result[i + 1] = _rsi_from(avg_gain, avg_loss)

    return result


def atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int = 14,
) -> list[Optional[float]]:
    """Average True Range using Wilder's smoothing."""
    n = len(closes)
    result: list[Optional[float]] = [None] * n
    if n < period:
        return result

    trs: list[float] = [highs[0] - lows[0]]
    for i in range(1, n):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)

    # Seed
    result[period - 1] = sum(trs[:period]) / period
    for i in range(period, n):
        result[i] = (result[i - 1] * (period - 1) + trs[i]) / period  # type: ignore[operator]

    return result


# ── Composite indicator snapshot ───────────────────────────────────────────────

def compute(candles: list[dict], cfg) -> Optional[dict]:
    """
    Compute all indicators on the full candle series and return
    a snapshot dict of the LATEST bar values only.

    Returns None if there are insufficient candles.
    """
    if not candles:
        return None

    closes = [c["close"] for c in candles]
    highs  = [c["high"]  for c in candles]
    lows   = [c["low"]   for c in candles]

    min_required = max(cfg.ema_trend, cfg.ema_slow, cfg.rsi_period, cfg.atr_period) + 2
    if len(candles) < min_required:
        return None

    ema_f_series  = ema(closes, cfg.ema_fast)
    ema_s_series  = ema(closes, cfg.ema_slow)
    ema_t_series  = ema(closes, cfg.ema_trend)
    rsi_series    = rsi(closes, cfg.rsi_period)
    atr_series    = atr(highs, lows, closes, cfg.atr_period)

    # Take last bar
    i = len(candles) - 1
    # Also take second-to-last for crossover detection
    j = i - 1

    ev_f  = ema_f_series[i]
    ev_s  = ema_s_series[i]
    ev_t  = ema_t_series[i]
    ev_r  = rsi_series[i]
    ev_a  = atr_series[i]

    pv_f  = ema_f_series[j]
    pv_s  = ema_s_series[j]
    pv_r  = rsi_series[j]   # previous RSI for direction check

    if any(v is None for v in [ev_f, ev_s, ev_t, ev_r, ev_a, pv_f, pv_s]):
        return None

    price = closes[i]
    prev_price = closes[j]

    return {
        "price":      price,
        "prev_price": prev_price,
        "ema_fast":   ev_f,
        "ema_slow":   ev_s,
        "ema_trend":  ev_t,
        "rsi":        ev_r,
        "prev_rsi":   pv_r,   # None-safe: strategy.generate uses .get("prev_rsi", rsi_val)
        "atr":        ev_a,
        "atr_pct":   ev_a / price if price > 0 else 0.0,
        # Crossover flags (current vs previous bar)
        "ema_cross_up":   (pv_f <= pv_s) and (ev_f > ev_s),  # type: ignore
        "ema_cross_down": (pv_f >= pv_s) and (ev_f < ev_s),  # type: ignore
        "timestamp": candles[i]["timestamp"],
        "candle_idx": i,
    }
