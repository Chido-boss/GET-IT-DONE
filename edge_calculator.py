"""
Edge calculator — the core intelligence of the latency arbitrage bot.

Combines Binance price momentum with Polymarket orderbook data to detect
when Polymarket odds lag CEX price moves, scoring each opportunity with a
multi-factor confidence model.
"""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Deque, Dict, Optional, Tuple

from binance_feed import PriceUpdate
from config import cfg
from polymarket_client import MarketInfo, Orderbook

logger = logging.getLogger(__name__)


# ── Output dataclass ───────────────────────────────────────────────────────────

@dataclass
class EdgeResult:
    asset: str
    market_id: str
    direction: str          # "YES" or "NO"
    edge_pct: float         # raw edge in percentage points
    confidence: float       # composite 0.0–1.0
    implied_cex_prob: float # P(up) from CEX momentum
    polymarket_prob: float  # current Polymarket YES price
    velocity: float
    acceleration: float
    volume_ratio: float
    time_to_expiry_sec: float
    liquidity_ok: bool
    atr_threshold: float    # adaptive threshold used
    timestamp: float = field(default_factory=time.time)

    @property
    def tradeable(self) -> bool:
        return (
            self.edge_pct >= cfg.MIN_EDGE_PCT
            and self.confidence >= cfg.MIN_CONFIDENCE
            and self.liquidity_ok
            and self.time_to_expiry_sec > 60
        )


# ── Rolling ATR / volatility tracker ─────────────────────────────────────────

@dataclass
class _VolPoint:
    ts: float
    price: float


class VolatilityTracker:
    """Tracks rolling ATR over VOLATILITY_WINDOW seconds."""

    def __init__(self, window_sec: int = cfg.VOLATILITY_WINDOW) -> None:
        self._window = window_sec
        self._prices: Deque[_VolPoint] = deque()

    def update(self, price: float, ts: float) -> None:
        self._prices.append(_VolPoint(ts=ts, price=price))
        # Prune old data
        cutoff = ts - self._window
        while self._prices and self._prices[0].ts < cutoff:
            self._prices.popleft()

    def atr_pct(self) -> float:
        """
        Approximate ATR as stddev of returns (pct), annualised to per-period.
        Returns 0.0 when insufficient data.
        """
        pts = list(self._prices)
        if len(pts) < 10:
            return 0.0
        returns = []
        for i in range(1, len(pts)):
            if pts[i - 1].price > 0:
                r = (pts[i].price - pts[i - 1].price) / pts[i - 1].price
                returns.append(r)
        if not returns:
            return 0.0
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return math.sqrt(variance) * 100.0  # as percentage

    def atr_multiplier(self) -> float:
        """
        Returns a multiplier for the lag threshold.
        Low vol → multiplier ~0.0 (use base threshold).
        High vol → multiplier ~1.0 (double threshold required).
        """
        atr = self.atr_pct()
        # Normalise: 0.05% stddev = normal, 0.30% = high volatility
        normalised = min(atr / 0.30, 1.0)
        return normalised


# ── Deduplication tracker ─────────────────────────────────────────────────────

class DedupTracker:
    """Prevents double-entry on the same (asset, direction, market) within DEDUP_WINDOW_MS."""

    def __init__(self, window_ms: int = cfg.DEDUP_WINDOW_MS) -> None:
        self._window_ms = window_ms
        self._last: Dict[str, float] = {}  # key -> last_signal_ms

    def is_duplicate(self, key: str) -> bool:
        now_ms = time.time() * 1000
        last = self._last.get(key)
        if last is not None and (now_ms - last) < self._window_ms:
            return True
        self._last[key] = now_ms
        return False

    def clear_expired(self) -> None:
        now_ms = time.time() * 1000
        expired = [k for k, v in self._last.items() if (now_ms - v) > self._window_ms * 10]
        for k in expired:
            del self._last[k]


# ── Main edge calculator ──────────────────────────────────────────────────────

class EdgeCalculator:
    """
    Stateful edge calculator. Maintains per-asset volatility trackers and
    deduplication state. Call compute_edge() for each price update.
    """

    def __init__(self) -> None:
        self._vol_trackers: Dict[str, VolatilityTracker] = {
            "BTC": VolatilityTracker(),
            "ETH": VolatilityTracker(),
        }
        self._dedup = DedupTracker()

    # ── Public API ─────────────────────────────────────────────────────────────

    def compute_edge(
        self,
        asset: str,
        binance_data: PriceUpdate,
        market: MarketInfo,
        orderbook: Optional[Orderbook],
        contract_duration_sec: int = 300,
    ) -> Optional[EdgeResult]:
        """
        Compute edge and confidence for a specific Polymarket market.

        Returns None if no meaningful edge detected.
        """
        # Update volatility tracker
        self._vol_trackers[asset].update(binance_data.price, binance_data.timestamp)

        # 1. CEX implied probability
        cex_prob = self._cex_implied_prob(
            price_change_pct=binance_data.price_change_pct_30s,
            velocity=binance_data.velocity,
            acceleration=binance_data.acceleration,
            price=binance_data.price,
            contract_duration_sec=contract_duration_sec,
        )

        # 2. Polymarket probability
        poly_prob = market.yes_price

        if poly_prob <= 0 or poly_prob >= 1:
            return None

        # 3. Determine direction and raw edge
        raw_edge_pct = (cex_prob - poly_prob) * 100.0  # +ve = YES underpriced
        direction = "YES" if raw_edge_pct > 0 else "NO"
        edge_pct = abs(raw_edge_pct)

        # 4. Adaptive threshold
        vol_multiplier = self._vol_trackers[asset].atr_multiplier()
        threshold = cfg.LAG_THRESHOLD_BASE * (1 + vol_multiplier)

        if edge_pct < threshold:
            return None

        # 5. Time to expiry
        time_to_expiry = self._parse_time_to_expiry(market.end_date_iso)
        if time_to_expiry <= 0:
            return None

        # 6. Liquidity check
        liquidity_ok = True
        ob_imbalance = 0.0
        if orderbook is not None:
            required_usdc = 1000.0  # minimum $1000 available
            side = "BUY" if direction == "YES" else "SELL"
            available = orderbook.available_at_levels(side, n_levels=3)
            liquidity_ok = available >= required_usdc
            ob_imbalance = orderbook.imbalance()

        # 7. Multi-factor confidence
        confidence = self._compute_confidence(
            asset=asset,
            velocity=binance_data.velocity,
            acceleration=binance_data.acceleration,
            price_change_pct=binance_data.price_change_pct_30s,
            volume_ratio=binance_data.volume_ratio,
            edge_pct=edge_pct,
            threshold=threshold,
            time_to_expiry_sec=time_to_expiry,
            ob_imbalance=ob_imbalance,
            direction=direction,
        )

        # 8. Deduplication check
        dedup_key = f"{asset}:{market.market_id}:{direction}"
        self._dedup.clear_expired()
        if self._dedup.is_duplicate(dedup_key):
            logger.debug("Dedup: suppressing signal %s", dedup_key)
            return None

        return EdgeResult(
            asset=asset,
            market_id=market.market_id,
            direction=direction,
            edge_pct=edge_pct,
            confidence=confidence,
            implied_cex_prob=cex_prob,
            polymarket_prob=poly_prob,
            velocity=binance_data.velocity,
            acceleration=binance_data.acceleration,
            volume_ratio=binance_data.volume_ratio,
            time_to_expiry_sec=time_to_expiry,
            liquidity_ok=liquidity_ok,
            atr_threshold=threshold,
        )

    # ── CEX implied probability ────────────────────────────────────────────────

    def _cex_implied_prob(
        self,
        price_change_pct: float,
        velocity: float,
        acceleration: float,
        price: float,
        contract_duration_sec: int,
    ) -> float:
        """
        Estimate P(price will be higher at contract expiry) from CEX data.

        Uses a logistic function calibrated to short-duration crypto moves:
          base_prob = sigmoid(price_change_pct * 15)

        Then adjusts for momentum persistence and acceleration.
        """
        # Base probability from 30s price change
        scaled = price_change_pct * 15.0
        base_prob = _sigmoid(scaled)

        # Momentum adjustment: velocity in $/s normalised by price
        vel_pct_per_sec = (velocity / price * 100.0) if price > 0 else 0.0
        # At 0.01%/s velocity (e.g. $0.65/s on BTC), add up to ±5% prob
        momentum_adj = _sigmoid(vel_pct_per_sec * 500.0) * 0.10 - 0.05
        # Only apply momentum in the same direction as price change
        if price_change_pct * velocity < 0:
            momentum_adj *= 0.5  # Dampened when conflicting

        # Acceleration confirms or contradicts direction
        accel_pct_per_sec2 = (acceleration / price * 100.0) if price > 0 else 0.0
        accel_adj = 0.0
        if price_change_pct > 0 and accel_pct_per_sec2 > 0:
            accel_adj = min(accel_pct_per_sec2 * 100.0, 0.03)  # up to 3%
        elif price_change_pct < 0 and accel_pct_per_sec2 < 0:
            accel_adj = min(abs(accel_pct_per_sec2) * 100.0, 0.03)
            accel_adj = -accel_adj

        # Duration factor: shorter remaining time = stronger signal from momentum
        duration_factor = 1.0
        if contract_duration_sec <= 60:
            duration_factor = 1.3  # Near-expiry momentum matters more
        elif contract_duration_sec <= 180:
            duration_factor = 1.15

        prob = base_prob + (momentum_adj + accel_adj) * duration_factor
        return max(0.02, min(0.98, prob))

    # ── Confidence scoring ────────────────────────────────────────────────────

    def _compute_confidence(
        self,
        asset: str,
        velocity: float,
        acceleration: float,
        price_change_pct: float,
        volume_ratio: float,
        edge_pct: float,
        threshold: float,
        time_to_expiry_sec: float,
        ob_imbalance: float,
        direction: str,
    ) -> float:
        """
        Multi-factor confidence score (0.0 to 1.0).

        Component weights:
          momentum_score : 0.30
          volume_score   : 0.25
          edge_score     : 0.25
          time_score     : 0.20
        """
        # --- Momentum score (0–0.30) ---
        # Velocity magnitude (normalised) + consistency with price change direction
        vel_magnitude = abs(velocity)
        # BTC: high velocity ~100 $/s, ETH ~5 $/s; normalise by asset
        norm_divisor = 50.0 if asset == "BTC" else 3.0
        vel_norm = min(vel_magnitude / norm_divisor, 1.0)

        # Consistency: velocity and price_change should agree on direction
        direction_sign = 1.0 if direction == "YES" else -1.0
        vel_sign_match = 1.0 if (velocity * direction_sign) > 0 else 0.3
        accel_sign_match = 1.0 if (acceleration * direction_sign) > 0 else 0.7

        momentum_score = vel_norm * vel_sign_match * accel_sign_match * 0.30

        # --- Volume score (0–0.25) ---
        # volume_ratio > 2x = strong signal, 1x = neutral, <1x = weak
        if volume_ratio >= 3.0:
            vol_score = 0.25
        elif volume_ratio >= 2.0:
            vol_score = 0.20
        elif volume_ratio >= 1.5:
            vol_score = 0.15
        elif volume_ratio >= 1.0:
            vol_score = 0.10
        else:
            vol_score = 0.05

        # --- Edge score (0–0.25) ---
        # Normalise edge above threshold up to 3x threshold = full score
        excess = edge_pct - threshold
        edge_normalised = min(excess / (threshold * 2.0), 1.0) if threshold > 0 else 0.0
        edge_score = edge_normalised * 0.25

        # --- Time score (0–0.20) ---
        # More time remaining = more opportunity for the gap to persist
        # Optimal: 60-180s remaining for 5-min contracts
        if 60 <= time_to_expiry_sec <= 240:
            time_score = 0.20
        elif time_to_expiry_sec < 60:
            # Too close to expiry — uncertain
            time_score = max(0.0, (time_to_expiry_sec / 60.0) * 0.10)
        else:
            # Early in contract — gap may compress further
            decay = min(time_to_expiry_sec / 300.0, 1.0)
            time_score = (1.0 - decay * 0.5) * 0.20

        # Orderbook imbalance bonus (up to 5%)
        ob_bonus = 0.0
        if direction == "YES" and ob_imbalance > 0.1:
            ob_bonus = min(ob_imbalance * 0.05, 0.05)
        elif direction == "NO" and ob_imbalance < -0.1:
            ob_bonus = min(abs(ob_imbalance) * 0.05, 0.05)

        confidence = momentum_score + vol_score + edge_score + time_score + ob_bonus
        return max(0.0, min(1.0, confidence))

    # ── Utility ────────────────────────────────────────────────────────────────

    @staticmethod
    def _parse_time_to_expiry(end_date_iso: str) -> float:
        """Parse ISO datetime string and return seconds until expiry."""
        if not end_date_iso:
            return 300.0  # Default: assume 5 min remaining

        try:
            # Handle various ISO formats
            end_date_iso = end_date_iso.rstrip("Z").replace(" ", "T")
            if "." in end_date_iso:
                dt = datetime.fromisoformat(end_date_iso).replace(tzinfo=timezone.utc)
            else:
                dt = datetime.fromisoformat(end_date_iso).replace(tzinfo=timezone.utc)

            now = datetime.now(tz=timezone.utc)
            remaining = (dt - now).total_seconds()
            return max(0.0, remaining)
        except (ValueError, TypeError) as exc:
            logger.debug("Could not parse end_date_iso=%r: %s", end_date_iso, exc)
            return 300.0


# ── Math helpers ───────────────────────────────────────────────────────────────

def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid function."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)
