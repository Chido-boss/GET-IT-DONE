"""
strategy.py — Multi-factor signal generation.

Signal hierarchy (all filters must pass):
  1. Volatility filter   — ATR% above minimum threshold (avoid chop)
  2. Trend filter        — price relative to slow EMA (direction bias)
  3. Momentum filter     — EMA fast/slow crossover confirmed
  4. RSI filter          — momentum not exhausted / oversold-overbought
  5. Cooldown gate       — N bars since last exit

Returns: 'long' | 'short' | None
"""

from __future__ import annotations
from typing import Optional
from config import Config


class SignalResult:
    __slots__ = ("direction", "reason")

    def __init__(self, direction: Optional[str], reason: str) -> None:
        self.direction = direction
        self.reason = reason

    def __repr__(self) -> str:
        return f"Signal({self.direction or 'NONE'}: {self.reason})"


def generate(inds: dict, cfg: Config, bars_since_exit: int) -> SignalResult:
    """
    Evaluate all filters and return a signal.

    Parameters
    ----------
    inds : output from indicators.compute(), optionally extended with:
           - htf_ema_trend : float  (4h EMA trend; skipped if absent)
           - prev_rsi      : float  (RSI of previous bar; skipped if absent)
    cfg  : Config instance
    bars_since_exit : bars elapsed since the last position was closed
    """

    price      = inds["price"]
    prev_price = inds.get("prev_price", price)
    ema_fast   = inds["ema_fast"]
    ema_slow   = inds["ema_slow"]
    ema_trend  = inds["ema_trend"]
    rsi_val    = inds["rsi"]
    prev_rsi   = inds.get("prev_rsi", rsi_val)
    atr_pct    = inds["atr_pct"]
    htf_ema    = inds.get("htf_ema_trend")   # None = HTF not available, filter skipped

    # ── Filter 1: Cooldown ────────────────────────────────────────────────────
    if bars_since_exit < cfg.cooldown_bars:
        return SignalResult(None, f"cooldown ({bars_since_exit}/{cfg.cooldown_bars} bars)")

    # ── Filter 2: Volatility ─────────────────────────────────────────────────
    if atr_pct < cfg.min_atr_pct:
        return SignalResult(
            None,
            f"low volatility (ATR%={atr_pct*100:.3f}% < {cfg.min_atr_pct*100:.3f}%)"
        )

    # ── Filter 3: HTF bias (4h EMA) ───────────────────────────────────────────
    htf_allows_long  = (htf_ema is None) or (price > htf_ema)
    htf_allows_short = (htf_ema is None) or (price < htf_ema)

    # ── Long signal ───────────────────────────────────────────────────────────
    long_trend     = price > ema_trend        # LTF trend filter
    long_momentum  = ema_fast > ema_slow      # EMA crossover
    long_expansion = price > prev_price       # price expanding upward
    long_rsi_dir   = rsi_val > prev_rsi       # RSI strengthening

    if htf_allows_long and long_trend and long_momentum and long_expansion and long_rsi_dir:
        htf_tag = f"HTF={'above' if htf_ema else 'skip'} "
        return SignalResult(
            "long",
            f"{htf_tag}trend=above_EMA{cfg.ema_trend} cross=BULL "
            f"expand=YES RSI={prev_rsi:.1f}->{rsi_val:.1f}"
        )

    # ── Short signal ──────────────────────────────────────────────────────────
    short_trend     = price < ema_trend       # LTF trend filter
    short_momentum  = ema_fast < ema_slow     # EMA crossover
    short_expansion = price < prev_price      # price expanding downward
    short_rsi_dir   = rsi_val < prev_rsi      # RSI weakening

    if htf_allows_short and short_trend and short_momentum and short_expansion and short_rsi_dir:
        htf_tag = f"HTF={'below' if htf_ema else 'skip'} "
        return SignalResult(
            "short",
            f"{htf_tag}trend=below_EMA{cfg.ema_trend} cross=BEAR "
            f"expand=YES RSI={prev_rsi:.1f}->{rsi_val:.1f}"
        )

    # ── No signal ─────────────────────────────────────────────────────────────
    reasons = []
    if not (long_trend or short_trend):
        reasons.append("price near trend EMA")
    if not (long_momentum or short_momentum):
        reasons.append("no EMA cross")
    if not (long_expansion or short_expansion):
        reasons.append("no price expansion")
    if not (long_rsi_dir or short_rsi_dir):
        reasons.append("RSI flat/reversing")
    if htf_ema is not None and not (htf_allows_long or htf_allows_short):
        reasons.append("HTF bias blocked")
    if not reasons:
        reasons.append("filters misaligned")

    return SignalResult(None, " | ".join(reasons))


def check_exit(position: dict, current_price: float, signal: SignalResult) -> tuple[bool, str]:
    """
    Determine whether an open position should be exited.

    Returns (should_exit: bool, reason: str)

    Checks (in priority order):
      1. Stop loss hit
      2. Take profit hit
      3. Opposite signal
    """
    direction = position["direction"]
    sl = position["stop_loss"]
    tp = position["take_profit"]

    if direction == "long":
        if current_price <= sl:
            return True, "stop_loss"
        if current_price >= tp:
            return True, "take_profit"
        if signal.direction == "short":
            return True, "opposite_signal"

    elif direction == "short":
        if current_price >= sl:
            return True, "stop_loss"
        if current_price <= tp:
            return True, "take_profit"
        if signal.direction == "long":
            return True, "opposite_signal"

    return False, ""
