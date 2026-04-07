#!/bin/bash
set -euo pipefail
mkdir -p quant_engine && cd quant_engine

cat > config.py << 'PYEOF'
"""
config.py — Single source of truth for all system parameters.
Override anything via environment variables: QE_SYMBOL=ETHUSDT python engine.py
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field


def _env(key: str, default):
    val = os.environ.get(f"QE_{key.upper()}")
    if val is None:
        return default
    try:
        return type(default)(val)
    except (ValueError, TypeError):
        return default


@dataclass
class Config:
    # ── Market Data ───────────────────────────────────────────────────────────
    symbol: str          = "BTCUSDT"
    interval: str        = "1h"      # Binance interval: 1m 5m 15m 1h 4h 1d
    candle_limit: int    = 200       # candles fetched per API call

    # ── Indicators ────────────────────────────────────────────────────────────
    ema_fast:  int = 12
    ema_slow:  int = 26
    ema_trend: int = 50
    rsi_period: int = 14
    atr_period: int = 14

    # ── Signal Thresholds ─────────────────────────────────────────────────────
    rsi_long_min:   float = 52.0   # RSI must be above this for longs
    rsi_short_max:  float = 48.0   # RSI must be below this for shorts
    min_atr_pct:    float = 0.003  # ATR/price floor — skip if < 0.3% (chop)

    # ── Execution ─────────────────────────────────────────────────────────────
    sl_atr_mult: float = 2.0   # stop-loss = ATR × this
    tp_atr_mult: float = 3.0   # take-profit = ATR × this
    cooldown_bars: int = 3     # bars to sit out after any exit

    # ── Risk ──────────────────────────────────────────────────────────────────
    risk_per_trade:  float = 0.01   # 1% of equity risked per trade
    max_position_pct: float = 0.20  # never allocate more than 20% of equity
    max_daily_loss:  float = 0.03   # kill-switch at 3% daily drawdown

    # ── System ────────────────────────────────────────────────────────────────
    starting_equity: float = 10_000.0
    loop_sleep:      int   = 60        # seconds between main-loop ticks
    state_file:      str   = "state.json"
    log_file:        str   = "quant.log"
    paper_mode:      bool  = True

    # ── Backtest ──────────────────────────────────────────────────────────────
    backtest_candles: int   = 1_000   # historical candles to fetch
    slippage_pct:     float = 0.001   # 0.1% per side
    commission_pct:   float = 0.001   # 0.1% per side


def load_config() -> Config:
    c = Config()
    c.symbol        = _env("symbol",        c.symbol)
    c.interval      = _env("interval",      c.interval)
    c.candle_limit  = _env("candle_limit",  c.candle_limit)
    c.ema_fast      = _env("ema_fast",      c.ema_fast)
    c.ema_slow      = _env("ema_slow",      c.ema_slow)
    c.ema_trend     = _env("ema_trend",     c.ema_trend)
    c.rsi_period    = _env("rsi_period",    c.rsi_period)
    c.atr_period    = _env("atr_period",    c.atr_period)
    c.sl_atr_mult   = _env("sl_atr_mult",   c.sl_atr_mult)
    c.tp_atr_mult   = _env("tp_atr_mult",   c.tp_atr_mult)
    c.cooldown_bars = _env("cooldown_bars", c.cooldown_bars)
    c.risk_per_trade= _env("risk_per_trade",c.risk_per_trade)
    c.max_daily_loss= _env("max_daily_loss",c.max_daily_loss)
    c.starting_equity=_env("starting_equity",c.starting_equity)
    c.paper_mode    = _env("paper_mode",    c.paper_mode)
    return c


cfg = load_config()
PYEOF

cat > data.py << 'PYEOF'
"""
data.py — Market data ingestion from Binance public REST API.
No API key required. Returns standardised OHLCV dicts.
"""

from __future__ import annotations
import time
from typing import Optional
import urllib.request
import urllib.parse
import json

BINANCE_BASE = "https://api.binance.com"


def _get(url: str, params: dict) -> list:
    full_url = url + "?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                full_url,
                headers={"User-Agent": "quant-engine/1.0"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"Binance API failed after 4 attempts: {exc}") from exc
            time.sleep(2 ** attempt)
    return []


def fetch_candles(
    symbol: str,
    interval: str,
    limit: int = 200,
    start_time_ms: Optional[int] = None,
) -> list[dict]:
    """
    Fetch OHLCV candles from Binance.

    Returns list of dicts with keys:
        timestamp (int ms), open, high, low, close, volume (all float)
    """
    params: dict = {"symbol": symbol, "interval": interval, "limit": limit}
    if start_time_ms is not None:
        params["startTime"] = start_time_ms

    raw = _get(f"{BINANCE_BASE}/api/v3/klines", params)

    candles = []
    for k in raw:
        candles.append({
            "timestamp": int(k[0]),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        })
    return candles


def fetch_candles_since(
    symbol: str,
    interval: str,
    n_candles: int,
) -> list[dict]:
    """
    Fetch up to n_candles by paginating backwards from now.
    Binance caps each call at 1000 candles.
    """
    all_candles: list[dict] = []
    batch = 1000
    end_ts: Optional[int] = None

    while len(all_candles) < n_candles:
        params: dict = {
            "symbol": symbol,
            "interval": interval,
            "limit": min(batch, n_candles - len(all_candles)),
        }
        if end_ts is not None:
            params["endTime"] = end_ts

        raw = _get(f"{BINANCE_BASE}/api/v3/klines", params)
        if not raw:
            break

        batch_candles = [{
            "timestamp": int(k[0]),
            "open":   float(k[1]),
            "high":   float(k[2]),
            "low":    float(k[3]),
            "close":  float(k[4]),
            "volume": float(k[5]),
        } for k in raw]

        all_candles = batch_candles + all_candles
        end_ts = batch_candles[0]["timestamp"] - 1

        if len(raw) < batch:
            break

    return all_candles[-n_candles:]


def latest_price(symbol: str) -> float:
    """Current best-bid/ask mid from Binance ticker."""
    raw = _get(f"{BINANCE_BASE}/api/v3/ticker/price", {"symbol": symbol})
    return float(raw.get("price", 0))
PYEOF

cat > indicators.py << 'PYEOF'
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

    if any(v is None for v in [ev_f, ev_s, ev_t, ev_r, ev_a, pv_f, pv_s]):
        return None

    price = closes[i]
    prev_price = closes[j]

    return {
        "price":     price,
        "prev_price": prev_price,
        "ema_fast":  ev_f,
        "ema_slow":  ev_s,
        "ema_trend": ev_t,
        "rsi":       ev_r,
        "atr":       ev_a,
        "atr_pct":   ev_a / price if price > 0 else 0.0,
        # Crossover flags (current vs previous bar)
        "ema_cross_up":   (pv_f <= pv_s) and (ev_f > ev_s),  # type: ignore
        "ema_cross_down": (pv_f >= pv_s) and (ev_f < ev_s),  # type: ignore
        "timestamp": candles[i]["timestamp"],
        "candle_idx": i,
    }
PYEOF

cat > strategy.py << 'PYEOF'
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
PYEOF

cat > risk.py << 'PYEOF'
"""
risk.py — Position sizing, daily loss gate, and risk checks.

Position sizing logic:
  risk_amount  = equity × risk_per_trade          (e.g. $100 on $10k at 1%)
  stop_dist    = ATR × sl_atr_mult / entry_price  (fractional price move)
  position_usd = risk_amount / stop_dist           (so a full stop = risk_amount)
  capped at max_position_pct of equity
"""

from __future__ import annotations
from config import Config


class RiskManager:
    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg

    # ── Position sizing ────────────────────────────────────────────────────────

    def position_size_usd(
        self,
        equity: float,
        entry_price: float,
        atr: float,
    ) -> float:
        """
        Return USD value of the position such that a full stop-loss hit
        loses exactly risk_per_trade × equity.
        """
        if entry_price <= 0 or atr <= 0:
            return 0.0

        risk_amount = equity * self.cfg.risk_per_trade
        stop_dist_pct = (self.cfg.sl_atr_mult * atr) / entry_price
        if stop_dist_pct <= 0:
            return 0.0

        size = risk_amount / stop_dist_pct
        max_size = equity * self.cfg.max_position_pct
        return min(size, max_size)

    def base_quantity(self, size_usd: float, price: float) -> float:
        """Convert USD position value to base-currency units."""
        if price <= 0:
            return 0.0
        return size_usd / price

    # ── Stop / take-profit levels ─────────────────────────────────────────────

    def stop_loss(self, direction: str, entry_price: float, atr: float) -> float:
        dist = atr * self.cfg.sl_atr_mult
        if direction == "long":
            return entry_price - dist
        return entry_price + dist

    def take_profit(self, direction: str, entry_price: float, atr: float) -> float:
        dist = atr * self.cfg.tp_atr_mult
        if direction == "long":
            return entry_price + dist
        return entry_price - dist

    # ── Daily loss gate ────────────────────────────────────────────────────────

    def daily_loss_exceeded(
        self,
        current_equity: float,
        day_start_equity: float,
    ) -> bool:
        """Returns True if today's loss exceeds the max_daily_loss threshold."""
        if day_start_equity <= 0:
            return False
        loss_pct = (day_start_equity - current_equity) / day_start_equity
        return loss_pct >= self.cfg.max_daily_loss

    # ── PnL calculations ──────────────────────────────────────────────────────

    def unrealized_pnl(
        self,
        direction: str,
        entry_price: float,
        current_price: float,
        size_usd: float,
    ) -> float:
        """Unrealized PnL in USD for an open position."""
        if entry_price <= 0:
            return 0.0
        price_return = (current_price - entry_price) / entry_price
        if direction == "short":
            price_return = -price_return
        return size_usd * price_return

    def realized_pnl(
        self,
        direction: str,
        entry_price: float,
        exit_price: float,
        size_usd: float,
        slippage_pct: float = 0.0,
        commission_pct: float = 0.0,
    ) -> float:
        """
        Realized PnL after slippage and commission.
        slippage and commission are applied symmetrically on both legs.
        """
        if entry_price <= 0:
            return 0.0

        # Adjust exit price for slippage (adverse)
        if direction == "long":
            effective_exit = exit_price * (1.0 - slippage_pct)
        else:
            effective_exit = exit_price * (1.0 + slippage_pct)

        price_return = (effective_exit - entry_price) / entry_price
        if direction == "short":
            price_return = -price_return

        gross = size_usd * price_return
        costs = size_usd * commission_pct * 2  # entry + exit commission
        return gross - costs
PYEOF

cat > execution.py << 'PYEOF'
"""
execution.py — Position lifecycle management.

Tracks exactly one position at a time (long or short).
All PnL arithmetic is in USD.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional
from config import Config
from risk import RiskManager


class Position:
    """
    Represents a single open trade.

    Attributes (all public for serialisation):
      direction   : 'long' | 'short'
      entry_price : float   — price at which we entered
      size_usd    : float   — USD value allocated
      size_base   : float   — base currency units (size_usd / entry_price)
      stop_loss   : float
      take_profit : float
      entry_time  : str (ISO)
      entry_bar   : int     — global bar index at entry
    """

    def __init__(
        self,
        direction: str,
        entry_price: float,
        size_usd: float,
        stop_loss: float,
        take_profit: float,
        entry_bar: int,
        symbol: str,
    ) -> None:
        self.direction   = direction
        self.entry_price = entry_price
        self.size_usd    = size_usd
        self.size_base   = size_usd / entry_price if entry_price > 0 else 0.0
        self.stop_loss   = stop_loss
        self.take_profit = take_profit
        self.entry_bar   = entry_bar
        self.symbol      = symbol
        self.entry_time  = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        return {
            "direction":   self.direction,
            "entry_price": self.entry_price,
            "size_usd":    self.size_usd,
            "size_base":   self.size_base,
            "stop_loss":   self.stop_loss,
            "take_profit": self.take_profit,
            "entry_bar":   self.entry_bar,
            "symbol":      self.symbol,
            "entry_time":  self.entry_time,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Position":
        pos = cls(
            direction   = d["direction"],
            entry_price = d["entry_price"],
            size_usd    = d["size_usd"],
            stop_loss   = d["stop_loss"],
            take_profit = d["take_profit"],
            entry_bar   = d["entry_bar"],
            symbol      = d["symbol"],
        )
        pos.entry_time = d.get("entry_time", pos.entry_time)
        return pos


class ExecutionEngine:
    """
    Manages open position lifecycle.
    Works in paper mode only (no exchange API calls).
    """

    def __init__(self, cfg: Config, risk: RiskManager) -> None:
        self.cfg  = cfg
        self.risk = risk
        self._position: Optional[Position] = None

    # ── State ─────────────────────────────────────────────────────────────────

    @property
    def has_position(self) -> bool:
        return self._position is not None

    @property
    def position(self) -> Optional[Position]:
        return self._position

    def load_position(self, pos_dict: Optional[dict]) -> None:
        """Restore position from persisted state."""
        if pos_dict:
            self._position = Position.from_dict(pos_dict)
        else:
            self._position = None

    def dump_position(self) -> Optional[dict]:
        return self._position.to_dict() if self._position else None

    # ── Entry ─────────────────────────────────────────────────────────────────

    def open_position(
        self,
        direction: str,
        price: float,
        atr: float,
        equity: float,
        bar_idx: int,
        symbol: str,
    ) -> Position:
        """
        Open a new position. Raises if one is already open.
        Applies entry slippage in paper mode.
        """
        if self._position is not None:
            raise RuntimeError("Cannot open position: one already open")

        # Apply entry slippage (adverse)
        if self.cfg.paper_mode:
            if direction == "long":
                effective_price = price * (1.0 + self.cfg.slippage_pct)
            else:
                effective_price = price * (1.0 - self.cfg.slippage_pct)
        else:
            effective_price = price

        size_usd = self.risk.position_size_usd(equity, effective_price, atr)
        sl = self.risk.stop_loss(direction, effective_price, atr)
        tp = self.risk.take_profit(direction, effective_price, atr)

        self._position = Position(
            direction   = direction,
            entry_price = effective_price,
            size_usd    = size_usd,
            stop_loss   = sl,
            take_profit = tp,
            entry_bar   = bar_idx,
            symbol      = symbol,
        )
        return self._position

    # ── Exit ──────────────────────────────────────────────────────────────────

    def close_position(
        self,
        price: float,
        reason: str,
    ) -> dict:
        """
        Close the open position and return a trade-result dict.
        Applies exit slippage in paper mode.
        """
        if self._position is None:
            raise RuntimeError("No position to close")

        pos = self._position

        # Apply exit slippage (adverse)
        if self.cfg.paper_mode:
            if pos.direction == "long":
                effective_exit = price * (1.0 - self.cfg.slippage_pct)
            else:
                effective_exit = price * (1.0 + self.cfg.slippage_pct)
        else:
            effective_exit = price

        pnl = self.risk.realized_pnl(
            direction      = pos.direction,
            entry_price    = pos.entry_price,
            exit_price     = effective_exit,
            size_usd       = pos.size_usd,
            slippage_pct   = 0.0,            # already applied above
            commission_pct = self.cfg.commission_pct,
        )
        pnl_pct = pnl / pos.size_usd * 100 if pos.size_usd > 0 else 0.0

        result = {
            **pos.to_dict(),
            "exit_price":    effective_exit,
            "exit_time":     datetime.now(timezone.utc).isoformat(),
            "reason":        reason,
            "pnl":           round(pnl, 4),
            "pnl_pct":       round(pnl_pct, 4),
        }

        self._position = None
        return result

    # ── Mark-to-market ────────────────────────────────────────────────────────

    def unrealized_pnl(self, current_price: float) -> float:
        if self._position is None:
            return 0.0
        return self.risk.unrealized_pnl(
            self._position.direction,
            self._position.entry_price,
            current_price,
            self._position.size_usd,
        )
PYEOF

cat > state.py << 'PYEOF'
"""
state.py — Persistent state management via a JSON file.

Schema:
{
  "equity":            float,
  "realized_pnl":      float,   # cumulative all-time
  "day_start_equity":  float,
  "day_date":          str,      # "YYYY-MM-DD"
  "position":          dict|null,
  "bars_since_exit":   int,
  "bar_count":         int,
  "last_candle_ts":    int,      # ms timestamp of last processed candle
  "trade_history":     list[dict],
  "daily_pnl_history": list[dict]
}
"""

from __future__ import annotations
import json
import os
from datetime import date, datetime, timezone
from typing import Any, Optional
from config import cfg


def _default_state() -> dict:
    return {
        "equity":            cfg.starting_equity,
        "realized_pnl":      0.0,
        "day_start_equity":  cfg.starting_equity,
        "day_date":          str(date.today()),
        "position":          None,
        "bars_since_exit":   9999,   # start ready to trade
        "bar_count":         0,
        "last_candle_ts":    0,
        "trade_history":     [],
        "daily_pnl_history": [],
    }


def load() -> dict:
    if os.path.exists(cfg.state_file):
        try:
            with open(cfg.state_file, "r") as f:
                saved = json.load(f)
            # Forward-compatible: fill in any missing keys
            base = _default_state()
            base.update(saved)
            return base
        except (json.JSONDecodeError, OSError):
            pass
    return _default_state()


def save(state: dict) -> None:
    tmp = cfg.state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, cfg.state_file)   # atomic on Linux


def maybe_reset_day(state: dict) -> bool:
    """
    If a new calendar day (UTC) has started, archive yesterday's stats and
    reset day_start_equity. Returns True if a reset happened.
    """
    today = str(date.today())
    if state["day_date"] == today:
        return False

    yesterday_pnl = state["equity"] - state["day_start_equity"]
    state["daily_pnl_history"].append({
        "date":   state["day_date"],
        "pnl":    round(yesterday_pnl, 4),
        "equity": round(state["equity"], 4),
        "trades": sum(
            1 for t in state["trade_history"]
            if t.get("exit_time", "").startswith(state["day_date"])
        ),
    })

    state["day_date"] = today
    state["day_start_equity"] = state["equity"]
    return True


def record_trade(state: dict, trade: dict) -> None:
    """Append a closed trade to history and update equity + realized PnL."""
    state["trade_history"].append(trade)
    state["realized_pnl"] = round(state.get("realized_pnl", 0.0) + trade["pnl"], 4)
    state["equity"]        = round(state["equity"] + trade["pnl"], 4)


def summary(state: dict) -> str:
    """One-line human summary of current state."""
    trades = len(state["trade_history"])
    wins   = sum(1 for t in state["trade_history"] if t["pnl"] > 0)
    win_rate = (wins / trades * 100) if trades else 0.0
    daily_pnl = state["equity"] - state["day_start_equity"]
    return (
        f"equity=${state['equity']:,.2f}  "
        f"realized={'+' if state['realized_pnl']>=0 else ''}"
        f"${state['realized_pnl']:,.2f}  "
        f"trades={trades}  "
        f"win%={win_rate:.0f}  "
        f"daily={'+' if daily_pnl>=0 else ''}${daily_pnl:,.2f}"
    )
PYEOF

cat > logger.py << 'PYEOF'
"""
logger.py — Structured, human-readable event logging.

Every significant event has a fixed-width type tag so logs are grep-able:
  ENTRY   EXIT   PNL   EQUITY   SIGNAL   SKIP   ERROR   INFO
"""

from __future__ import annotations
import logging
import sys
from datetime import datetime, timezone
from config import cfg


# ── ANSI colour codes (disabled in file handler automatically) ─────────────────

_RESET  = "\033[0m"
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_DIM    = "\033[2m"
_BOLD   = "\033[1m"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class QuantLogger:
    """Thin wrapper that writes structured lines to both console and a log file."""

    def __init__(self) -> None:
        self._file = open(cfg.log_file, "a", buffering=1)  # line-buffered

    def _write(self, tag: str, msg: str, colour: str = "") -> None:
        ts = _now()
        plain = f"{ts} | {tag:<7} | {msg}"
        coloured = f"{_DIM}{ts}{_RESET} | {colour}{_BOLD}{tag:<7}{_RESET} | {msg}"
        print(coloured, flush=True)
        self._file.write(plain + "\n")

    # ── Public event methods ───────────────────────────────────────────────────

    def entry(self, direction: str, symbol: str, price: float,
              size_usd: float, sl: float, tp: float, atr: float) -> None:
        d = direction.upper()
        self._write("ENTRY", (
            f"{d:5} {symbol} @ {price:,.2f} | "
            f"size=${size_usd:,.2f} | SL={sl:,.2f} TP={tp:,.2f} | ATR={atr:.2f}"
        ), _GREEN)

    def exit(self, direction: str, symbol: str, price: float,
             reason: str, pnl: float, pnl_pct: float) -> None:
        colour = _GREEN if pnl >= 0 else _RED
        sign   = "+" if pnl >= 0 else ""
        self._write("EXIT", (
            f"{direction.upper():5} {symbol} @ {price:,.2f} | "
            f"reason={reason:<12} pnl={sign}${pnl:,.2f} ({sign}{pnl_pct:.2f}%)"
        ), colour)

    def pnl(self, realized: float, unrealized: float, equity: float) -> None:
        self._write("PNL", (
            f"realized={'+' if realized>=0 else ''}{realized:,.4f}  "
            f"unrealized={'+' if unrealized>=0 else ''}{unrealized:,.4f}  "
            f"equity=${equity:,.2f}"
        ), _CYAN)

    def equity(self, equity: float, daily_pnl: float, daily_pct: float) -> None:
        sign = "+" if daily_pnl >= 0 else ""
        colour = _GREEN if daily_pnl >= 0 else _RED
        self._write("EQUITY", (
            f"${equity:,.2f}  daily={sign}${daily_pnl:,.2f} ({sign}{daily_pct:.2f}%)"
        ), colour)

    def signal(self, direction: str | None, reason: str) -> None:
        if direction:
            self._write("SIGNAL", f"{direction.upper():5} — {reason}", _YELLOW)
        else:
            self._write("SIGNAL", f"NONE  — {reason}", _DIM)

    def skip(self, reason: str) -> None:
        self._write("SKIP", reason, _DIM)

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg, _RED)

    def state_snapshot(self, bar: int, price: float, rsi: float,
                       ema_f: float, ema_s: float, atr_pct: float,
                       position: str, bars_since_exit: int) -> None:
        pos_tag = position if position else "FLAT"
        self._write("SNAP", (
            f"bar={bar:>6} price={price:,.2f} RSI={rsi:.1f} "
            f"EMAf={ema_f:.2f} EMAs={ema_s:.2f} "
            f"ATR%={atr_pct*100:.3f}% pos={pos_tag:<6} bse={bars_since_exit}"
        ), _DIM)

    def close(self) -> None:
        self._file.close()


log = QuantLogger()
PYEOF

cat > engine.py << 'PYEOF'
"""
engine.py — Main trading loop.

Usage:
    python engine.py                  # paper mode, default BTC/1h
    python engine.py --symbol ETHUSDT --interval 4h
    python engine.py --once           # run one tick and exit (for cron/testing)
    QE_RISK_PER_TRADE=0.005 python engine.py  # override via env vars

The loop:
  1. Fetch latest N candles
  2. Compute indicators
  3. If new candle seen → run strategy logic
  4. Check exits on open position
  5. Check entries if no position
  6. Save state
  7. Sleep
"""

from __future__ import annotations
import argparse
import signal
import sys
import time
from datetime import datetime, timezone

from config import cfg, Config
from data import fetch_candles
from indicators import compute
from strategy import generate, check_exit
from execution import ExecutionEngine
from risk import RiskManager
from logger import log
import state as st


# ── Signal handling ────────────────────────────────────────────────────────────

_running = True

def _handle_signal(sig, frame):
    global _running
    log.info(f"Signal {sig} received — shutting down cleanly")
    _running = False

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT,  _handle_signal)


# ── Main engine ────────────────────────────────────────────────────────────────

class Engine:
    def __init__(self, cfg: Config) -> None:
        self.cfg  = cfg
        self.risk = RiskManager(cfg)
        self.exe  = ExecutionEngine(cfg, self.risk)
        self._state: dict = {}

    def _startup(self) -> None:
        self._state = st.load()
        self.exe.load_position(self._state.get("position"))
        log.info(
            f"Engine started | symbol={cfg.symbol} interval={cfg.interval} "
            f"mode={'PAPER' if cfg.paper_mode else 'LIVE'}"
        )
        log.info(f"Loaded state: {st.summary(self._state)}")

    def _save(self) -> None:
        self._state["position"] = self.exe.dump_position()
        st.save(self._state)

    # ── Single tick ────────────────────────────────────────────────────────────

    def tick(self) -> None:
        s = self._state

        # ── Daily reset ──────────────────────────────────────────────────────
        if st.maybe_reset_day(s):
            log.info(f"New day — day_start_equity=${s['day_start_equity']:,.2f}")

        # ── Daily loss kill-switch ────────────────────────────────────────────
        if self.risk.daily_loss_exceeded(s["equity"], s["day_start_equity"]):
            log.error(
                f"Max daily loss hit — equity=${s['equity']:,.2f} "
                f"started=${s['day_start_equity']:,.2f} — no new trades today"
            )
            self._save()
            return

        # ── Fetch candles ────────────────────────────────────────────────────
        try:
            candles = fetch_candles(cfg.symbol, cfg.interval, cfg.candle_limit)
        except Exception as exc:
            log.error(f"Data fetch failed: {exc}")
            return

        if not candles:
            log.error("No candles returned")
            return

        latest_ts = candles[-1]["timestamp"]

        # ── New candle gate ────────────────────────────────────────────────────
        if latest_ts == s.get("last_candle_ts", 0):
            # No new candle — update unrealized PnL only
            if self.exe.has_position:
                upnl = self.exe.unrealized_pnl(candles[-1]["close"])
                # No log spam — only save state
                s["position"] = self.exe.dump_position()
            return

        s["last_candle_ts"] = latest_ts
        s["bar_count"]      = s.get("bar_count", 0) + 1
        bar_idx             = s["bar_count"]

        # ── Compute indicators ────────────────────────────────────────────────
        inds = compute(candles, cfg)
        if inds is None:
            log.skip("Not enough candle history yet")
            return

        price = inds["price"]

        # ── State snapshot ───────────────────────────────────────────────────
        log.state_snapshot(
            bar          = bar_idx,
            price        = price,
            rsi          = inds["rsi"],
            ema_f        = inds["ema_fast"],
            ema_s        = inds["ema_slow"],
            atr_pct      = inds["atr_pct"],
            position     = self.exe.position.direction if self.exe.has_position else None,
            bars_since_exit = s["bars_since_exit"],
        )

        # ── Generate signal ───────────────────────────────────────────────────
        sig = generate(inds, cfg, s["bars_since_exit"])
        log.signal(sig.direction, sig.reason)

        # ── Exit logic ────────────────────────────────────────────────────────
        if self.exe.has_position:
            should_exit, reason = check_exit(
                self.exe.position.to_dict(), price, sig
            )
            if should_exit:
                trade = self.exe.close_position(price, reason)
                st.record_trade(s, trade)
                s["bars_since_exit"] = 0

                log.exit(
                    direction = trade["direction"],
                    symbol    = cfg.symbol,
                    price     = trade["exit_price"],
                    reason    = reason,
                    pnl       = trade["pnl"],
                    pnl_pct   = trade["pnl_pct"],
                )
                daily_pnl = s["equity"] - s["day_start_equity"]
                log.equity(
                    equity    = s["equity"],
                    daily_pnl = daily_pnl,
                    daily_pct = daily_pnl / s["day_start_equity"] * 100,
                )
                log.pnl(
                    realized   = s["realized_pnl"],
                    unrealized = 0.0,
                    equity     = s["equity"],
                )
                self._save()
                return

        # ── Entry logic ───────────────────────────────────────────────────────
        if not self.exe.has_position and sig.direction is not None:
            pos = self.exe.open_position(
                direction = sig.direction,
                price     = price,
                atr       = inds["atr"],
                equity    = s["equity"],
                bar_idx   = bar_idx,
                symbol    = cfg.symbol,
            )
            log.entry(
                direction = pos.direction,
                symbol    = cfg.symbol,
                price     = pos.entry_price,
                size_usd  = pos.size_usd,
                sl        = pos.stop_loss,
                tp        = pos.take_profit,
                atr       = inds["atr"],
            )

        else:
            # Increment cooldown counter if no position and no entry
            if not self.exe.has_position:
                s["bars_since_exit"] = min(s["bars_since_exit"] + 1, 9999)

        # ── Log unrealized PnL if in position ─────────────────────────────────
        if self.exe.has_position:
            upnl = self.exe.unrealized_pnl(price)
            log.pnl(
                realized   = s["realized_pnl"],
                unrealized = upnl,
                equity     = s["equity"],
            )

        self._save()

    # ── Run loop ───────────────────────────────────────────────────────────────

    def run(self, once: bool = False) -> None:
        self._startup()
        global _running
        while _running:
            try:
                self.tick()
            except Exception as exc:
                log.error(f"Tick error: {exc}")
            if once:
                break
            time.sleep(cfg.loop_sleep)
        log.info("Engine stopped.")


# ── CLI ────────────────────────────────────────────────────────────────────────

def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Quant Engine — paper trading")
    p.add_argument("--symbol",   default=cfg.symbol,   help="e.g. ETHUSDT")
    p.add_argument("--interval", default=cfg.interval,  help="e.g. 1h 4h 1d")
    p.add_argument("--once",     action="store_true",   help="run one tick and exit")
    return p.parse_args()


def main() -> None:
    args = _parse()
    cfg.symbol   = args.symbol
    cfg.interval = args.interval

    engine = Engine(cfg)
    engine.run(once=args.once)


if __name__ == "__main__":
    main()
PYEOF

cat > backtest.py << 'PYEOF'
"""
backtest.py — Offline historical backtester.

Usage:
    python backtest.py                           # BTC/1h, last 1000 candles
    python backtest.py --symbol ETHUSDT --candles 2000
    python backtest.py --interval 4h --candles 500
    python backtest.py --show-trades             # print every trade

Output:
    Total return, CAGR, win rate, profit factor, max drawdown, Sharpe ratio
"""

from __future__ import annotations
import argparse
import math
from datetime import datetime, timezone
from typing import Optional

from config import cfg, Config
from data import fetch_candles_since
from indicators import compute
from strategy import generate, check_exit
from risk import RiskManager


# ── Backtest engine ────────────────────────────────────────────────────────────

class BacktestResult:
    def __init__(self) -> None:
        self.trades: list[dict] = []
        self.equity_curve: list[float] = []
        self.starting_equity: float = 0.0
        self.ending_equity: float = 0.0
        self.n_candles: int = 0

    # ── Metrics ───────────────────────────────────────────────────────────────

    @property
    def total_return_pct(self) -> float:
        if self.starting_equity <= 0:
            return 0.0
        return (self.ending_equity - self.starting_equity) / self.starting_equity * 100

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t["pnl"] > 0)
        return wins / len(self.trades) * 100

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t["pnl"] for t in self.trades if t["pnl"] > 0)
        gross_loss   = abs(sum(t["pnl"] for t in self.trades if t["pnl"] < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def sharpe_ratio(self) -> float:
        """
        Simplified Sharpe using per-trade returns (not time-series).
        Annualised assuming ~3 trades per month = 36/year.
        """
        if len(self.trades) < 2:
            return 0.0
        returns = [t["pnl"] / t["size_usd"] for t in self.trades if t["size_usd"] > 0]
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var_r  = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r  = math.sqrt(var_r) if var_r > 0 else 1e-9
        trades_per_year = 36  # rough estimate
        return (mean_r / std_r) * math.sqrt(trades_per_year)

    @property
    def avg_win(self) -> float:
        wins = [t["pnl"] for t in self.trades if t["pnl"] > 0]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t["pnl"] for t in self.trades if t["pnl"] < 0]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def expectancy(self) -> float:
        """Average PnL per trade in USD."""
        if not self.trades:
            return 0.0
        return sum(t["pnl"] for t in self.trades) / len(self.trades)

    # ── Report ────────────────────────────────────────────────────────────────

    def print_report(self, show_trades: bool = False) -> None:
        sep = "─" * 60
        print(f"\n{sep}")
        print(f"  BACKTEST RESULTS — {cfg.symbol} {cfg.interval}")
        print(sep)
        print(f"  Candles tested:     {self.n_candles}")
        print(f"  Starting equity:    ${self.starting_equity:,.2f}")
        print(f"  Ending equity:      ${self.ending_equity:,.2f}")
        print(f"  Total return:       {self.total_return_pct:+.2f}%")
        print(f"  Total trades:       {self.n_trades}")
        print(f"  Win rate:           {self.win_rate:.1f}%")
        print(f"  Profit factor:      {self.profit_factor:.2f}")
        print(f"  Max drawdown:       {self.max_drawdown_pct:.2f}%")
        print(f"  Sharpe ratio:       {self.sharpe_ratio:.2f}")
        print(f"  Expectancy/trade:   ${self.expectancy:,.2f}")
        print(f"  Avg win:            ${self.avg_win:,.2f}")
        print(f"  Avg loss:           ${self.avg_loss:,.2f}")
        print(sep)

        if show_trades and self.trades:
            print(f"\n  {'#':>4}  {'Dir':5}  {'Entry':>10}  {'Exit':>10}  "
                  f"{'Size':>10}  {'P&L':>10}  {'Reason'}")
            print("  " + "─" * 72)
            for i, t in enumerate(self.trades, 1):
                sign = "+" if t["pnl"] >= 0 else ""
                print(
                    f"  {i:>4}  {t['direction']:5}  "
                    f"{t['entry_price']:>10.2f}  {t['exit_price']:>10.2f}  "
                    f"${t['size_usd']:>9.2f}  "
                    f"{sign}${t['pnl']:>8.2f}  {t['reason']}"
                )
            print()


# ── Runner ────────────────────────────────────────────────────────────────────

def run_backtest(cfg: Config, n_candles: int) -> BacktestResult:
    print(f"Fetching {n_candles} candles for {cfg.symbol} {cfg.interval}...")
    candles = fetch_candles_since(cfg.symbol, cfg.interval, n_candles)
    if len(candles) < 60:
        raise RuntimeError(f"Only {len(candles)} candles returned — need at least 60")
    print(f"Fetched {len(candles)} candles. Running simulation...")

    risk   = RiskManager(cfg)
    result = BacktestResult()
    result.starting_equity = cfg.starting_equity
    result.n_candles = len(candles)

    equity         = cfg.starting_equity
    position       = None      # dict or None
    bars_since_exit = 9999

    for i in range(len(candles)):
        # Build a rolling window up to bar i
        window = candles[: i + 1]
        if len(window) < 2:
            result.equity_curve.append(equity)
            continue

        inds = compute(window, cfg)
        if inds is None:
            result.equity_curve.append(equity)
            continue

        price = inds["price"]
        sig   = generate(inds, cfg, bars_since_exit)

        # ── Exit check ────────────────────────────────────────────────────────
        if position is not None:
            should_exit, reason = check_exit(position, price, sig)
            if should_exit:
                # Apply slippage + commission
                if position["direction"] == "long":
                    exit_price = price * (1.0 - cfg.slippage_pct)
                else:
                    exit_price = price * (1.0 + cfg.slippage_pct)

                pnl = risk.realized_pnl(
                    direction      = position["direction"],
                    entry_price    = position["entry_price"],
                    exit_price     = exit_price,
                    size_usd       = position["size_usd"],
                    slippage_pct   = 0.0,
                    commission_pct = cfg.commission_pct,
                )
                equity += pnl
                result.trades.append({
                    "bar":         i,
                    "direction":   position["direction"],
                    "entry_price": position["entry_price"],
                    "exit_price":  exit_price,
                    "size_usd":    position["size_usd"],
                    "pnl":         round(pnl, 4),
                    "reason":      reason,
                })
                position = None
                bars_since_exit = 0

        # ── Entry check ───────────────────────────────────────────────────────
        if position is None and sig.direction is not None:
            # Apply entry slippage
            if sig.direction == "long":
                entry_price = price * (1.0 + cfg.slippage_pct)
            else:
                entry_price = price * (1.0 - cfg.slippage_pct)

            size_usd = risk.position_size_usd(equity, entry_price, inds["atr"])
            sl = risk.stop_loss(sig.direction, entry_price, inds["atr"])
            tp = risk.take_profit(sig.direction, entry_price, inds["atr"])

            position = {
                "direction":   sig.direction,
                "entry_price": entry_price,
                "size_usd":    size_usd,
                "stop_loss":   sl,
                "take_profit": tp,
                "entry_bar":   i,
            }
        elif position is None:
            bars_since_exit = min(bars_since_exit + 1, 9999)

        result.equity_curve.append(equity)

    # Force-close any open position at last price
    if position is not None:
        last_price = candles[-1]["close"]
        pnl = risk.realized_pnl(
            position["direction"], position["entry_price"], last_price,
            position["size_usd"], cfg.slippage_pct, cfg.commission_pct
        )
        equity += pnl
        result.trades.append({
            "bar":         len(candles) - 1,
            "direction":   position["direction"],
            "entry_price": position["entry_price"],
            "exit_price":  last_price,
            "size_usd":    position["size_usd"],
            "pnl":         round(pnl, 4),
            "reason":      "end_of_data",
        })

    result.ending_equity = round(equity, 4)
    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Quant Engine Backtester")
    p.add_argument("--symbol",   default=cfg.symbol,            help="e.g. ETHUSDT")
    p.add_argument("--interval", default=cfg.interval,           help="e.g. 1h 4h 1d")
    p.add_argument("--candles",  type=int, default=cfg.backtest_candles, help="Number of candles")
    p.add_argument("--show-trades", action="store_true",         help="Print every trade")
    args = p.parse_args()

    cfg.symbol   = args.symbol
    cfg.interval = args.interval

    result = run_backtest(cfg, args.candles)
    result.print_report(show_trades=args.show_trades)


if __name__ == "__main__":
    main()
PYEOF

echo "All files written."
python3 -c "import urllib.request,json,math,os,dataclasses; print('stdlib OK')"
echo ""
echo "=== BACKTEST ==="
python3 backtest.py --show-trades
echo ""
echo "=== LIVE ENGINE (Ctrl+C to stop) ==="
python3 engine.py
