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
