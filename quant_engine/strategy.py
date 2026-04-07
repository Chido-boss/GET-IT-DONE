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
    inds : output from indicators.compute()
    cfg  : Config instance
    bars_since_exit : bars elapsed since the last position was closed
    """

    price     = inds["price"]
    ema_fast  = inds["ema_fast"]
    ema_slow  = inds["ema_slow"]
    ema_trend = inds["ema_trend"]
    rsi_val   = inds["rsi"]
    atr_pct   = inds["atr_pct"]

    # ── Filter 1: Cooldown ────────────────────────────────────────────────────
    if bars_since_exit < cfg.cooldown_bars:
        return SignalResult(None, f"cooldown ({bars_since_exit}/{cfg.cooldown_bars} bars)")

    # ── Filter 2: Volatility ─────────────────────────────────────────────────
    if atr_pct < cfg.min_atr_pct:
        return SignalResult(
            None,
            f"low volatility (ATR%={atr_pct*100:.3f}% < {cfg.min_atr_pct*100:.3f}%)"
        )

    # ── Long signal ───────────────────────────────────────────────────────────
    long_trend    = price > ema_trend               # above trend EMA
    long_momentum = ema_fast > ema_slow             # fast above slow
    long_rsi      = rsi_val >= cfg.rsi_long_min     # RSI confirms strength

    if long_trend and long_momentum and long_rsi:
        return SignalResult(
            "long",
            f"trend=above_EMA{cfg.ema_trend} "
            f"cross=BULL "
            f"RSI={rsi_val:.1f}>={cfg.rsi_long_min}"
        )

    # ── Short signal ──────────────────────────────────────────────────────────
    short_trend    = price < ema_trend               # below trend EMA
    short_momentum = ema_fast < ema_slow             # fast below slow
    short_rsi      = rsi_val <= cfg.rsi_short_max   # RSI confirms weakness

    if short_trend and short_momentum and short_rsi:
        return SignalResult(
            "short",
            f"trend=below_EMA{cfg.ema_trend} "
            f"cross=BEAR "
            f"RSI={rsi_val:.1f}<={cfg.rsi_short_max}"
        )

    # ── No signal ─────────────────────────────────────────────────────────────
    reasons = []
    if not (long_trend or short_trend):
        reasons.append("price near trend EMA")
    if not (long_momentum or short_momentum):
        reasons.append("no EMA cross")
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
