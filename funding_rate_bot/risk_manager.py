"""
Risk manager: position sizing, gate checks, P&L tracking, return projections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from config import cfg
from opportunity_scanner import FundingOpportunity

logger = logging.getLogger(__name__)

# Taker fee estimate (each leg): 0.06% for derivatives, 0.1% for spot
_SPOT_TAKER_FEE = 0.001
_PERP_TAKER_FEE = 0.0006


@dataclass
class ReturnEstimate:
    projected_funding_income: float   # USDC
    estimated_fees: float             # USDC (open + close, both legs)
    net_projected_return: float       # funding_income - fees
    projected_apy: float              # annualized as fraction (e.g. 0.32 = 32%)


class RiskManager:
    """
    Stateful risk manager. Tracks daily P&L and enforces all trading gates.
    """

    def __init__(self) -> None:
        self._daily_pnl: float = 0.0
        self._daily_start_balance: float | None = None
        self._current_date: date = date.today()
        self._open_position_count: int = 0

    # ------------------------------------------------------------------
    # Daily tracking
    # ------------------------------------------------------------------

    def set_portfolio_value(self, value: float) -> None:
        """
        Called at startup and daily reset to anchor the daily loss limit.
        """
        if self._daily_start_balance is None:
            self._daily_start_balance = value
        today = date.today()
        if today != self._current_date:
            # Day rolled over
            self._current_date = today
            self._daily_pnl = 0.0
            self._daily_start_balance = value
            logger.info("Daily P&L reset. New reference balance: %.2f", value)

    def update_pnl(self, amount: float) -> None:
        """
        Record a P&L change (positive = profit, negative = loss).
        Logs a warning if daily loss limit is breached.
        """
        self._daily_pnl += amount
        logger.debug("PnL update: %.4f USDC | daily total: %.4f USDC", amount, self._daily_pnl)
        if self._is_daily_loss_breached():
            logger.warning(
                "DAILY LOSS LIMIT BREACHED: %.4f USDC (%.2f%% of starting balance)",
                self._daily_pnl,
                self._daily_loss_pct * 100,
            )

    def register_opened(self) -> None:
        self._open_position_count += 1

    def register_closed(self) -> None:
        self._open_position_count = max(0, self._open_position_count - 1)

    def sync_open_count(self, count: int) -> None:
        self._open_position_count = count

    # ------------------------------------------------------------------
    # Gate checks
    # ------------------------------------------------------------------

    def check_gates(
        self,
        opportunity: FundingOpportunity,
        current_balance: float,
    ) -> tuple[bool, str]:
        """
        Check all pre-trade gates.
        Returns (allowed, reason_if_denied).
        """
        # Gate 1: Daily loss limit
        if self._is_daily_loss_breached():
            return False, (
                f"Daily loss limit active: P&L={self._daily_pnl:.2f} USDC "
                f"({self._daily_loss_pct * 100:.1f}% of balance)"
            )

        # Gate 2: Max concurrent positions
        if self._open_position_count >= cfg.max_total_positions:
            return False, (
                f"Max positions reached ({self._open_position_count}/{cfg.max_total_positions})"
            )

        # Gate 3: Minimum funding rate
        if opportunity.funding_rate < cfg.min_funding_rate:
            return False, (
                f"Funding rate {opportunity.funding_rate:.6f} below minimum {cfg.min_funding_rate:.6f}"
            )

        # Gate 4: Available balance
        min_required = cfg.min_position_usdc * (1 + cfg.margin_buffer_pct)
        if current_balance < min_required:
            return False, (
                f"Insufficient balance: {current_balance:.2f} USDC < {min_required:.2f} required"
            )

        # Gate 5: Minimum recommended size is achievable
        if opportunity.recommended_size_usdc < cfg.min_position_usdc:
            return False, (
                f"Recommended size {opportunity.recommended_size_usdc:.2f} USDC "
                f"< minimum {cfg.min_position_usdc:.2f}"
            )

        # Gate 6: Confidence score
        if opportunity.confidence_score < 0.3:
            return False, (
                f"Confidence score {opportunity.confidence_score:.2f} too low"
            )

        return True, ""

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def compute_position_size(
        self,
        opportunity: FundingOpportunity,
        portfolio_value: float,
    ) -> float:
        """
        Compute the USDC notional for a new position.

        Sizing logic:
        1. Base = MAX_POSITION_SIZE_PCT × portfolio
        2. Scale down linearly as open positions approach the max
        3. Apply margin buffer: actual capital deployed = size / (1 - MARGIN_BUFFER_PCT)
        4. Clamp to [MIN_POSITION_USDC, MAX_POSITION_USDC]
        """
        if portfolio_value <= 0:
            return 0.0

        base = cfg.max_position_size_pct * portfolio_value

        # Scale down as positions fill up
        utilisation = self._open_position_count / max(cfg.max_total_positions, 1)
        scale = max(0.5, 1.0 - utilisation * 0.3)  # reduce at most 30%
        base *= scale

        # Account for margin buffer: we need extra capital to maintain 25% free margin
        # on the perp leg.  Perp margin = size / leverage = size (at 1x).
        # Required: size + size * margin_buffer = size * (1 + margin_buffer)
        required_with_buffer = base * (1.0 + cfg.margin_buffer_pct)

        if required_with_buffer > portfolio_value * 0.9:
            # Don't use more than 90% of portfolio in one shot
            base = portfolio_value * 0.9 / (1.0 + cfg.margin_buffer_pct)

        # Clamp
        size = max(cfg.min_position_usdc, min(base, cfg.max_position_usdc))

        # Final check: does portfolio have enough?
        if size * (1 + cfg.margin_buffer_pct) > portfolio_value:
            size = portfolio_value / (1 + cfg.margin_buffer_pct)

        return round(size, 2)

    def compute_position_size_from_portfolio(
        self,
        funding_rate: float,
        portfolio_value: float,
    ) -> float:
        """
        Quick size estimate without a full FundingOpportunity (used by scanner).
        """
        if portfolio_value <= 0:
            return cfg.min_position_usdc
        base = cfg.max_position_size_pct * portfolio_value
        utilisation = self._open_position_count / max(cfg.max_total_positions, 1)
        base *= max(0.5, 1.0 - utilisation * 0.3)
        size = max(cfg.min_position_usdc, min(base, cfg.max_position_usdc))
        return round(size, 2)

    # ------------------------------------------------------------------
    # Return projections
    # ------------------------------------------------------------------

    def estimate_returns(
        self,
        opportunity: FundingOpportunity,
        size_usdc: float,
        days: int = 30,
    ) -> ReturnEstimate:
        """
        Project P&L for holding a funding arb position for ``days`` days.
        """
        periods = days * 3  # 3 payments per day (every 8h)

        # Funding income: rate × notional × periods
        gross_funding = opportunity.funding_rate * size_usdc * periods

        # Fee estimate: 2 round-trips (open + close), each with spot + perp legs
        # Open:  spot buy + perp sell
        # Close: spot sell + perp buy
        open_fees = size_usdc * (_SPOT_TAKER_FEE + _PERP_TAKER_FEE)
        close_fees = size_usdc * (_SPOT_TAKER_FEE + _PERP_TAKER_FEE)
        total_fees = open_fees + close_fees

        net = gross_funding - total_fees
        # APY = (net / size_usdc) / days * 365
        apy = (net / size_usdc) / days * 365 if size_usdc > 0 and days > 0 else 0.0

        return ReturnEstimate(
            projected_funding_income=round(gross_funding, 4),
            estimated_fees=round(total_fees, 4),
            net_projected_return=round(net, 4),
            projected_apy=round(apy, 6),
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _daily_loss_pct(self) -> float:
        if not self._daily_start_balance:
            return 0.0
        return self._daily_pnl / self._daily_start_balance

    def _is_daily_loss_breached(self) -> bool:
        if self._daily_start_balance is None or self._daily_start_balance <= 0:
            return False
        return self._daily_pnl < -(cfg.daily_loss_limit_pct * self._daily_start_balance)

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def open_position_count(self) -> int:
        return self._open_position_count
