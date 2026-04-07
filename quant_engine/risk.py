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
