"""
risk.py — Pre-trade risk checks and position management.
Applied in paper mode today; same interface will gate live trades later.
"""

from __future__ import annotations
import logging
import os
import time
from pathlib import Path

log = logging.getLogger(__name__)

KILL_SWITCH_FILE = "STOP"


class RiskManager:
    def __init__(self, cfg: dict) -> None:
        self.cfg = cfg
        self._trade_times: list[float] = []
        self._daily_pnl: float = 0.0
        self._daily_reset_ts: float = _today_start()
        self._loss_cooldown_until: float = 0.0

    # ── Kill switch ───────────────────────────────────────────────────────────

    def kill_switch_active(self) -> bool:
        if Path(KILL_SWITCH_FILE).exists():
            log.warning("KILL SWITCH ACTIVE — STOP file found. Halting all trades.")
            return True
        return False

    # ── Daily PnL tracking ────────────────────────────────────────────────────

    def record_pnl(self, pnl: float) -> None:
        self._maybe_reset_day()
        self._daily_pnl += pnl
        if pnl < 0:
            self._loss_cooldown_until = time.time() + self.cfg.get("cooldown_after_loss_minutes", 5) * 60

    def _maybe_reset_day(self) -> None:
        today = _today_start()
        if today > self._daily_reset_ts:
            self._daily_reset_ts = today
            self._daily_pnl = 0.0

    def daily_loss_exceeded(self) -> bool:
        self._maybe_reset_day()
        max_loss = self.cfg.get("max_daily_loss_usd", 200.0)
        if self._daily_pnl < -max_loss:
            log.warning(f"Daily loss limit hit: ${self._daily_pnl:.2f} < -${max_loss:.2f}")
            return True
        return False

    def in_cooldown(self) -> bool:
        if time.time() < self._loss_cooldown_until:
            secs = self._loss_cooldown_until - time.time()
            log.debug(f"In cooldown: {secs:.0f}s remaining")
            return True
        return False

    # ── Rate limits ───────────────────────────────────────────────────────────

    def trades_per_hour_ok(self) -> bool:
        now = time.time()
        cutoff = now - 3600
        self._trade_times = [t for t in self._trade_times if t > cutoff]
        max_per_hour = self.cfg.get("max_trades_per_hour", 20)
        if len(self._trade_times) >= max_per_hour:
            log.warning(f"Hourly trade limit reached ({max_per_hour}/hr)")
            return False
        return True

    def record_trade(self) -> None:
        self._trade_times.append(time.time())

    # ── Position limits ───────────────────────────────────────────────────────

    def concurrent_positions_ok(self, open_count: int) -> bool:
        max_pos = self.cfg.get("max_concurrent_positions", 5)
        if open_count >= max_pos:
            log.debug(f"Max concurrent positions reached ({open_count}/{max_pos})")
            return False
        return True

    # ── Signal quality ────────────────────────────────────────────────────────

    def signal_passes(
        self,
        adjusted_edge: float,
        spread: float,
        liquidity: float,
        ref_price_age: float,
        orderbook_age: float,
        confidence: float,
        open_count: int,
    ) -> tuple[bool, str]:
        """Returns (passes, reason_if_blocked)."""

        if self.kill_switch_active():
            return False, "kill_switch"
        if self.daily_loss_exceeded():
            return False, "daily_loss_limit"
        if self.in_cooldown():
            return False, "loss_cooldown"
        if not self.trades_per_hour_ok():
            return False, "hourly_rate_limit"
        if not self.concurrent_positions_ok(open_count):
            return False, "max_concurrent_positions"

        min_edge = self.cfg.get("min_edge_pct", 0.04)
        if adjusted_edge < min_edge:
            return False, f"edge_too_small ({adjusted_edge*100:.2f}% < {min_edge*100:.2f}%)"

        max_spread = self.cfg.get("max_spread", 0.08)
        if spread > max_spread:
            return False, f"spread_too_wide ({spread*100:.1f}% > {max_spread*100:.1f}%)"

        min_liq = self.cfg.get("min_liquidity_usd", 500)
        if liquidity < min_liq:
            return False, f"insufficient_liquidity (${liquidity:.0f} < ${min_liq:.0f})"

        max_ref_age = self.cfg.get("max_ref_price_age_seconds", 30)
        if ref_price_age > max_ref_age:
            return False, f"ref_price_stale ({ref_price_age:.0f}s > {max_ref_age}s)"

        max_ob_age = self.cfg.get("max_orderbook_age_seconds", 60)
        if orderbook_age > max_ob_age:
            return False, f"orderbook_stale ({orderbook_age:.0f}s > {max_ob_age}s)"

        min_conf = self.cfg.get("min_fair_value_confidence", 0.55)
        if confidence < min_conf:
            return False, f"low_confidence ({confidence:.2f} < {min_conf:.2f})"

        return True, ""


def _today_start() -> float:
    import datetime
    now = datetime.datetime.utcnow()
    today = datetime.datetime(now.year, now.month, now.day)
    return today.timestamp()
