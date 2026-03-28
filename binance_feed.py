"""
Async Binance WebSocket price feed.

Subscribes to combined stream:
  wss://stream.binance.com:9443/stream?streams=
    btcusdt@ticker/ethusdt@ticker/btcusdt@kline_1m/ethusdt@kline_1m

Maintains rolling price history and computes:
  - current_price, velocity (dp/dt over 5s), acceleration (d²p/dt²)
  - volume_ratio (current vs 20-period kline average)

Emits PriceUpdate objects to an asyncio.Queue with exponential backoff reconnect.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Optional, Tuple

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from config import cfg

logger = logging.getLogger(__name__)

# ── Data structures ────────────────────────────────────────────────────────────

@dataclass
class PricePoint:
    ts: float       # Unix timestamp (seconds, from time.monotonic-anchored wall time)
    price: float


@dataclass
class PriceUpdate:
    asset: str          # "BTC" or "ETH"
    timestamp: float    # Unix wall time (time.time())
    price: float
    bid: float
    ask: float
    # Derived momentum metrics
    velocity: float         # dp/dt over last 5 s (price units per second)
    acceleration: float     # d²p/dt² over last 5 s (price units per second²)
    price_change_30s: float # absolute change vs 30 s ago
    price_change_pct_30s: float  # percentage change vs 30 s ago
    volume_ratio: float     # current 1-min volume vs 20-period average


@dataclass
class AssetState:
    """Per-asset state maintained by the feed."""
    symbol: str
    history: Deque[PricePoint] = field(
        default_factory=lambda: deque(maxlen=600)
    )  # up to 10 min of ticks
    # kline volume ring buffer (20 closes)
    kline_volumes: Deque[float] = field(
        default_factory=lambda: deque(maxlen=20)
    )
    current_kline_volume: float = 0.0
    last_bid: float = 0.0
    last_ask: float = 0.0
    last_price: float = 0.0


# ── Feed class ────────────────────────────────────────────────────────────────

class BinanceFeed:
    """
    Manages a single persistent WebSocket connection to Binance combined stream.
    Reconnects automatically with exponential backoff.
    """

    _BACKOFF_STEPS = [2, 4, 8, 16, 32]  # seconds
    _PING_INTERVAL = 30  # seconds
    _PONG_TIMEOUT = 10   # seconds

    def __init__(self, queue: asyncio.Queue) -> None:
        self._queue = queue
        self._assets: Dict[str, AssetState] = {
            "BTC": AssetState(symbol="btcusdt"),
            "ETH": AssetState(symbol="ethusdt"),
        }
        self._running = False
        self._connected = False
        self._last_message_ts: float = 0.0
        self._reconnect_count: int = 0

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def last_message_ts(self) -> float:
        return self._last_message_ts

    def get_state(self, asset: str) -> Optional[AssetState]:
        return self._assets.get(asset.upper())

    async def run(self) -> None:
        """Main run loop. Connects, receives messages, reconnects on failure."""
        self._running = True
        backoff_idx = 0

        while self._running:
            try:
                await self._connect_and_receive()
                # Clean exit — reset backoff
                backoff_idx = 0
            except asyncio.CancelledError:
                logger.info("BinanceFeed cancelled.")
                break
            except Exception as exc:
                self._connected = False
                wait = self._BACKOFF_STEPS[min(backoff_idx, len(self._BACKOFF_STEPS) - 1)]
                logger.warning(
                    "BinanceFeed disconnected (%s). Reconnecting in %ds (attempt %d).",
                    exc, wait, self._reconnect_count + 1,
                )
                self._reconnect_count += 1
                backoff_idx += 1
                await asyncio.sleep(wait)

        self._connected = False
        logger.info("BinanceFeed stopped.")

    async def stop(self) -> None:
        self._running = False

    # ── Internal ───────────────────────────────────────────────────────────────

    def _build_url(self) -> str:
        streams = "/".join([
            "btcusdt@ticker",
            "ethusdt@ticker",
            "btcusdt@kline_1m",
            "ethusdt@kline_1m",
        ])
        return f"{cfg.BINANCE_WS_URL}/stream?streams={streams}"

    async def _connect_and_receive(self) -> None:
        url = self._build_url()
        logger.info("Connecting to Binance WS: %s", url)

        async with websockets.connect(
            url,
            ping_interval=self._PING_INTERVAL,
            ping_timeout=self._PONG_TIMEOUT,
            close_timeout=5,
            max_size=2**20,
        ) as ws:
            self._connected = True
            self._last_message_ts = time.time()
            logger.info("Binance WebSocket connected.")

            async for raw in ws:
                if not self._running:
                    break
                self._last_message_ts = time.time()
                try:
                    msg = json.loads(raw)
                    await self._handle_message(msg)
                except Exception as exc:
                    logger.debug("Error handling message: %s", exc)

    async def _handle_message(self, msg: dict) -> None:
        """Dispatch combined-stream envelope to the right handler."""
        stream: str = msg.get("stream", "")
        data: dict = msg.get("data", {})

        if "@ticker" in stream:
            await self._handle_ticker(stream, data)
        elif "@kline" in stream:
            self._handle_kline(stream, data)

    async def _handle_ticker(self, stream: str, data: dict) -> None:
        asset = "BTC" if "btcusdt" in stream else "ETH"
        state = self._assets[asset]

        try:
            price = float(data["c"])    # last price
            bid = float(data["b"])      # best bid
            ask = float(data["a"])      # best ask
        except (KeyError, ValueError):
            return

        now = time.time()
        state.last_price = price
        state.last_bid = bid
        state.last_ask = ask
        state.history.append(PricePoint(ts=now, price=price))

        # Compute derived metrics
        velocity, acceleration = self._compute_velocity_accel(state, now)
        change_30s, change_pct_30s = self._compute_change(state, now, seconds=30)
        volume_ratio = self._compute_volume_ratio(state)

        update = PriceUpdate(
            asset=asset,
            timestamp=now,
            price=price,
            bid=bid,
            ask=ask,
            velocity=velocity,
            acceleration=acceleration,
            price_change_30s=change_30s,
            price_change_pct_30s=change_pct_30s,
            volume_ratio=volume_ratio,
        )

        # Non-blocking put; drop if queue full to avoid memory growth
        try:
            self._queue.put_nowait(update)
        except asyncio.QueueFull:
            logger.debug("Price queue full, dropping tick for %s", asset)

    def _handle_kline(self, stream: str, data: dict) -> None:
        asset = "BTC" if "btcusdt" in stream else "ETH"
        state = self._assets[asset]

        kline = data.get("k", {})
        try:
            volume = float(kline.get("v", 0))
            is_closed = kline.get("x", False)
        except (ValueError, TypeError):
            return

        state.current_kline_volume = volume
        if is_closed:
            state.kline_volumes.append(volume)

    # ── Metrics helpers ────────────────────────────────────────────────────────

    def _compute_velocity_accel(
        self, state: AssetState, now: float
    ) -> Tuple[float, float]:
        """
        Compute velocity (dp/dt) and acceleration (d²p/dt²) using the last 5 seconds.
        We use a three-point finite difference on (t=now-5s, t=now-2.5s, t=now).
        """
        history = state.history
        if len(history) < 3:
            return 0.0, 0.0

        # Find price at ~5s ago and ~2.5s ago
        def price_at(target_ts: float) -> Optional[float]:
            best: Optional[PricePoint] = None
            best_diff = math.inf
            for pt in history:
                diff = abs(pt.ts - target_ts)
                if diff < best_diff:
                    best_diff = diff
                    best = pt
            return best.price if best and best_diff < 3.0 else None

        p_now = state.last_price
        p_mid = price_at(now - 2.5)
        p_old = price_at(now - 5.0)

        if p_mid is None or p_old is None:
            # Fall back to simple linear velocity over available window
            oldest = history[0]
            elapsed = now - oldest.ts
            if elapsed < 0.01:
                return 0.0, 0.0
            velocity = (p_now - oldest.price) / elapsed
            return velocity, 0.0

        dt = 2.5  # seconds per interval
        v1 = (p_mid - p_old) / dt    # velocity at midpoint
        v2 = (p_now - p_mid) / dt    # velocity at end
        velocity = v2
        acceleration = (v2 - v1) / dt
        return velocity, acceleration

    def _compute_change(
        self, state: AssetState, now: float, seconds: int = 30
    ) -> Tuple[float, float]:
        """Return (absolute_change, pct_change) over the last `seconds` seconds."""
        target_ts = now - seconds
        history = state.history
        p_now = state.last_price

        if not history or p_now == 0:
            return 0.0, 0.0

        # Find closest point to target_ts
        best: Optional[PricePoint] = None
        best_diff = math.inf
        for pt in history:
            diff = abs(pt.ts - target_ts)
            if diff < best_diff:
                best_diff = diff
                best = pt

        if best is None or best_diff > seconds * 1.5:
            return 0.0, 0.0

        p_old = best.price
        if p_old == 0:
            return 0.0, 0.0

        abs_change = p_now - p_old
        pct_change = (abs_change / p_old) * 100.0
        return abs_change, pct_change

    def _compute_volume_ratio(self, state: AssetState) -> float:
        """
        Return ratio of current kline volume to 20-period rolling average.
        Returns 1.0 when insufficient data.
        """
        if len(state.kline_volumes) < 5:
            return 1.0
        avg = sum(state.kline_volumes) / len(state.kline_volumes)
        if avg == 0:
            return 1.0
        return state.current_kline_volume / avg
