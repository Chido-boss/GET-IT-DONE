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
from indicators import compute, ema as ema_series
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


# ── HTF helper ────────────────────────────────────────────────────────────────

def _fetch_htf_ema(symbol: str, period: int) -> float | None:
    """Fetch 4h candles and return the latest EMA(period) value, or None on failure."""
    try:
        candles = fetch_candles(symbol, "4h", limit=period + 10)
        if len(candles) < period:
            return None
        closes = [c["close"] for c in candles]
        series = ema_series(closes, period)
        val = series[-1]
        return float(val) if val is not None else None
    except Exception:
        return None


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

        # ── HTF bias (4h EMA) — injected into inds dict ───────────────────────
        inds["htf_ema_trend"] = _fetch_htf_ema(cfg.symbol, cfg.ema_trend)

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
