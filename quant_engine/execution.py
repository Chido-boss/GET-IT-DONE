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
