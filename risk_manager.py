"""
Risk management engine.

Handles position sizing (half-Kelly), risk gates, per-asset circuit breakers,
daily loss limits, and total drawdown kill switch.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from config import cfg
from edge_calculator import EdgeResult

logger = logging.getLogger(__name__)


# ── State dataclass ────────────────────────────────────────────────────────────

@dataclass
class RiskState:
    portfolio_value: float
    daily_start_value: float
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0

    # Per-asset P&L tracking
    btc_daily_pnl: float = 0.0
    eth_daily_pnl: float = 0.0
    btc_paused: bool = False
    eth_paused: bool = False

    # Drawdown tracking
    peak_value: float = 0.0
    current_drawdown_pct: float = 0.0

    # Kill switch
    kill_switch_triggered: bool = False
    kill_switch_reason: str = ""

    # Position count
    open_position_count: int = 0

    def __post_init__(self) -> None:
        if self.peak_value == 0.0:
            self.peak_value = self.portfolio_value


@dataclass
class TradeResult:
    """Result of a completed trade for risk state updates."""
    asset: str
    pnl: float
    size_usdc: float
    edge_at_entry: float
    paper_mode: bool


# ── Risk manager ──────────────────────────────────────────────────────────────

class RiskManager:
    """
    Central risk management engine.

    Usage:
        rm = RiskManager(initial_portfolio=1000.0)
        size = rm.compute_kelly_size(edge_pct=7.5, confidence=0.90, portfolio_value=1000.0)
        allowed, reason = rm.check_risk_gates(asset="BTC", edge_result=..., proposed_size=50.0)
        rm.update_pnl(TradeResult(...))
    """

    def __init__(self, initial_portfolio: float = cfg.PAPER_STARTING_BALANCE) -> None:
        self._state = RiskState(
            portfolio_value=initial_portfolio,
            daily_start_value=initial_portfolio,
            peak_value=initial_portfolio,
        )
        self._daily_trade_count: Dict[str, int] = {"BTC": 0, "ETH": 0}

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def state(self) -> RiskState:
        return self._state

    def compute_kelly_size(
        self,
        edge_pct: float,
        confidence: float,
        portfolio_value: float,
        entry_price: float = 0.5,
    ) -> float:
        """
        Compute half-Kelly position size in USDC.

        Kelly formula for binary outcome:
          f* = (p * b - (1-p)) / b
        where:
          p  = win probability (confidence-weighted)
          b  = net odds (1/entry_price - 1)

        Returns 0.0 if Kelly is negative (no edge).
        """
        if entry_price <= 0 or entry_price >= 1:
            entry_price = 0.5

        # Use confidence-adjusted win probability
        # Base p from edge: if edge is 7%, and we're at 0.5 poly price → implied ~57%
        base_win_prob = 0.5 + (edge_pct / 200.0)  # linear approximation
        p = max(0.51, min(0.99, base_win_prob * (0.5 + confidence * 0.5)))

        # Net odds: if you pay 0.45 and win 1.0, net odds = 1.0/0.45 - 1 = 1.22
        b = (1.0 / entry_price) - 1.0
        if b <= 0:
            return 0.0

        # Full Kelly
        kelly_f = (p * b - (1.0 - p)) / b
        kelly_f = max(0.0, kelly_f)

        # Half-Kelly (cfg.KELLY_FRACTION = 0.5)
        kelly_f *= cfg.KELLY_FRACTION

        # Size in USDC
        raw_size = kelly_f * portfolio_value

        # Cap at MAX_POSITION_PCT
        max_size = cfg.MAX_POSITION_PCT * portfolio_value
        size = min(raw_size, max_size)

        logger.debug(
            "Kelly sizing: p=%.3f b=%.3f f*=%.3f half_f=%.3f "
            "raw=$%.2f capped=$%.2f",
            p, b, kelly_f / cfg.KELLY_FRACTION, kelly_f, raw_size, size,
        )
        return size

    def check_risk_gates(
        self,
        asset: str,
        edge_result: EdgeResult,
        proposed_size: float,
    ) -> Tuple[bool, str]:
        """
        Run all risk checks. Returns (allowed, reason).
        reason is empty string when allowed=True.
        """
        s = self._state

        # 1. Kill switch
        if s.kill_switch_triggered:
            return False, f"Kill switch: {s.kill_switch_reason}"

        # 2. Per-asset pause
        if asset.upper() == "BTC" and s.btc_paused:
            return False, "BTC trading paused (per-asset loss limit)"
        if asset.upper() == "ETH" and s.eth_paused:
            return False, "ETH trading paused (per-asset loss limit)"

        # 3. Edge threshold
        if edge_result.edge_pct < cfg.MIN_EDGE_PCT:
            return False, (
                f"Edge {edge_result.edge_pct:.1f}% < min {cfg.MIN_EDGE_PCT:.1f}%"
            )

        # 4. Confidence threshold
        if edge_result.confidence < cfg.MIN_CONFIDENCE:
            return False, (
                f"Confidence {edge_result.confidence:.3f} < min {cfg.MIN_CONFIDENCE:.3f}"
            )

        # 5. Position count
        if s.open_position_count >= cfg.MAX_CONCURRENT_POSITIONS:
            return False, (
                f"Max positions reached ({s.open_position_count}/{cfg.MAX_CONCURRENT_POSITIONS})"
            )

        # 6. Minimum meaningful trade size ($1)
        if proposed_size < 1.0:
            return False, f"Proposed size ${proposed_size:.2f} < $1 minimum"

        # 7. Liquidity
        if not edge_result.liquidity_ok:
            return False, "Insufficient liquidity on Polymarket orderbook"

        # 8. Time to expiry — must be at least 60s
        if edge_result.time_to_expiry_sec < 60:
            return False, f"Too close to expiry ({edge_result.time_to_expiry_sec:.0f}s)"

        return True, ""

    def update_pnl(self, trade: TradeResult) -> None:
        """
        Update state after a trade completes.
        Checks all kill-switch and pause thresholds.
        """
        s = self._state

        # Update portfolio value
        s.portfolio_value += trade.pnl
        s.daily_pnl += trade.pnl

        # Per-asset P&L
        if trade.asset.upper() == "BTC":
            s.btc_daily_pnl += trade.pnl
        elif trade.asset.upper() == "ETH":
            s.eth_daily_pnl += trade.pnl

        # Daily P&L percentage
        if s.daily_start_value > 0:
            s.daily_pnl_pct = s.daily_pnl / s.daily_start_value

        # Drawdown tracking
        if s.portfolio_value > s.peak_value:
            s.peak_value = s.portfolio_value
        if s.peak_value > 0:
            s.current_drawdown_pct = (s.peak_value - s.portfolio_value) / s.peak_value

        # ── Threshold checks ─────────────────────────────────────────────────

        # Daily loss kill switch
        if (
            not s.kill_switch_triggered
            and s.daily_pnl_pct < -cfg.DAILY_LOSS_LIMIT_PCT
        ):
            self._trigger_kill_switch(
                f"Daily loss limit hit: {s.daily_pnl_pct:.1%}"
            )

        # Total drawdown kill switch
        if (
            not s.kill_switch_triggered
            and s.current_drawdown_pct > cfg.TOTAL_DRAWDOWN_KILL_PCT
        ):
            self._trigger_kill_switch(
                f"Total drawdown limit hit: {s.current_drawdown_pct:.1%}"
            )

        # Per-asset pause (only if not already paused)
        if s.daily_start_value > 0:
            btc_loss_pct = s.btc_daily_pnl / s.daily_start_value
            eth_loss_pct = s.eth_daily_pnl / s.daily_start_value

            if not s.btc_paused and btc_loss_pct < -cfg.PER_ASSET_LOSS_LIMIT_PCT:
                s.btc_paused = True
                logger.warning(
                    "BTC trading PAUSED: daily loss %.1f%%", btc_loss_pct * 100
                )

            if not s.eth_paused and eth_loss_pct < -cfg.PER_ASSET_LOSS_LIMIT_PCT:
                s.eth_paused = True
                logger.warning(
                    "ETH trading PAUSED: daily loss %.1f%%", eth_loss_pct * 100
                )

        logger.debug(
            "PnL update: asset=%s pnl=%.4f portfolio=%.2f daily_pnl=%.4f drawdown=%.2f%%",
            trade.asset, trade.pnl, s.portfolio_value,
            s.daily_pnl, s.current_drawdown_pct * 100,
        )

    def register_position_opened(self) -> None:
        """Call when a new position is opened."""
        self._state.open_position_count += 1

    def register_position_closed(self) -> None:
        """Call when a position is closed."""
        self._state.open_position_count = max(0, self._state.open_position_count - 1)

    def reset_daily(self) -> None:
        """Reset daily stats at midnight UTC."""
        s = self._state
        s.daily_start_value = s.portfolio_value
        s.daily_pnl = 0.0
        s.daily_pnl_pct = 0.0
        s.btc_daily_pnl = 0.0
        s.eth_daily_pnl = 0.0
        s.btc_paused = False
        s.eth_paused = False
        # Don't reset kill switch or drawdown at daily reset
        self._daily_trade_count = {"BTC": 0, "ETH": 0}
        logger.info(
            "Daily stats reset. Portfolio: $%.2f Peak: $%.2f",
            s.portfolio_value, s.peak_value,
        )

    def update_portfolio_value(self, value: float) -> None:
        """Update portfolio value from external source (e.g. live balance query)."""
        s = self._state
        s.portfolio_value = value
        if value > s.peak_value:
            s.peak_value = value
        if s.peak_value > 0:
            s.current_drawdown_pct = (s.peak_value - value) / s.peak_value

    def get_summary(self) -> dict:
        """Return a summary dict for display/logging."""
        s = self._state
        return {
            "portfolio_value": s.portfolio_value,
            "daily_pnl": s.daily_pnl,
            "daily_pnl_pct": s.daily_pnl_pct,
            "current_drawdown_pct": s.current_drawdown_pct,
            "peak_value": s.peak_value,
            "btc_paused": s.btc_paused,
            "eth_paused": s.eth_paused,
            "kill_switch": s.kill_switch_triggered,
            "open_positions": s.open_position_count,
        }

    # ── Internal ───────────────────────────────────────────────────────────────

    def _trigger_kill_switch(self, reason: str) -> None:
        self._state.kill_switch_triggered = True
        self._state.kill_switch_reason = reason
        logger.critical("KILL SWITCH TRIGGERED: %s", reason)
