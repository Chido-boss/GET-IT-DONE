"""
Alert monitor — background asyncio task.

Polls Binance REST API every 10 seconds for BTC/ETH prices,
evaluates all active user alerts, fires Telegram notifications
when conditions are met (respecting per-alert cooldowns).

Conditions supported:
  above       — fires when price > threshold
  below       — fires when price < threshold
  change_pct  — fires when |% change in last 1hr| > threshold
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Optional

import httpx

from database import Alert, Database

logger = logging.getLogger(__name__)

BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/price"
POLL_INTERVAL = 10  # seconds between price checks
ASSETS = ["BTC", "ETH"]
SYMBOLS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT"}


class AlertMonitor:
    """
    Runs as a long-lived asyncio background task.
    Injected with the shared Database instance.
    """

    def __init__(self, db: Database, telegram_token: str) -> None:
        self._db = db
        self._telegram_token = telegram_token
        self._prices: Dict[str, float] = {}
        self._price_history: Dict[str, list] = {a: [] for a in ASSETS}
        self._running = False

    async def start(self) -> None:
        self._running = True
        logger.info("Alert monitor started")
        async with httpx.AsyncClient(timeout=10.0) as client:
            while self._running:
                try:
                    await self._tick(client)
                except Exception as exc:
                    logger.warning("Monitor tick error: %s", exc)
                await asyncio.sleep(POLL_INTERVAL)

    def stop(self) -> None:
        self._running = False

    # ── Core tick ──────────────────────────────────────────────────────────────

    async def _tick(self, client: httpx.AsyncClient) -> None:
        prices = await self._fetch_prices(client)
        if not prices:
            return

        now = time.time()
        for asset, price in prices.items():
            self._prices[asset] = price
            self._price_history[asset].append((now, price))
            # Keep only last 2 hours of history
            cutoff = now - 7200
            self._price_history[asset] = [
                (t, p) for t, p in self._price_history[asset] if t > cutoff
            ]

        # Load all active alerts fresh each tick (cheap on SQLite)
        alerts = await self._db.get_all_active_alerts()

        for alert in alerts:
            if alert.asset not in prices:
                continue
            current_price = prices[alert.asset]
            fired, message = self._evaluate(alert, current_price)
            if fired and message:
                await self._fire_alert(alert, current_price, message)

    # ── Alert evaluation ───────────────────────────────────────────────────────

    def _evaluate(self, alert: Alert, current_price: float) -> tuple[bool, str]:
        # Cooldown check
        if time.time() - alert.last_fired < alert.cooldown_sec:
            return False, ""

        label = f" ({alert.label})" if alert.label else ""

        if alert.condition == "above":
            if current_price > alert.threshold:
                return True, (
                    f"🚀 {alert.asset} is above ${alert.threshold:,.2f}{label}\n"
                    f"Current price: ${current_price:,.2f}"
                )

        elif alert.condition == "below":
            if current_price < alert.threshold:
                return True, (
                    f"📉 {alert.asset} is below ${alert.threshold:,.2f}{label}\n"
                    f"Current price: ${current_price:,.2f}"
                )

        elif alert.condition == "change_pct":
            pct = self._one_hour_change(alert.asset, current_price)
            if pct is not None and abs(pct) >= alert.threshold:
                direction = "up" if pct > 0 else "down"
                return True, (
                    f"⚡ {alert.asset} moved {direction} {abs(pct):.1f}%{label} in the last hour\n"
                    f"Current price: ${current_price:,.2f}"
                )

        return False, ""

    def _one_hour_change(self, asset: str, current_price: float) -> Optional[float]:
        history = self._price_history.get(asset, [])
        cutoff = time.time() - 3600
        old = [p for t, p in history if t <= cutoff]
        if not old:
            return None
        reference = old[-1]
        if reference <= 0:
            return None
        return ((current_price - reference) / reference) * 100.0

    # ── Firing ─────────────────────────────────────────────────────────────────

    async def _fire_alert(self, alert: Alert, price: float, message: str) -> None:
        user = await self._db.get_user_by_id(alert.user_id)
        if not user or not user.telegram_chat_id:
            logger.debug("No Telegram chat ID for user %d — skipping", alert.user_id)
            return

        success = await self._send_telegram(user.telegram_chat_id, f"🔔 CryptoWatch Alert\n\n{message}")
        if success:
            await self._db.record_alert_fired(alert, price, message)
            logger.info(
                "Alert %d fired for user %d: %s @ %.2f",
                alert.id, alert.user_id, alert.asset, price,
            )

    async def _send_telegram(self, chat_id: str, text: str) -> bool:
        if not self._telegram_token:
            logger.warning("TELEGRAM_BOT_TOKEN not set — cannot send alerts")
            return False
        url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"})
                return resp.status_code == 200
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)
            return False

    # ── Price fetching ─────────────────────────────────────────────────────────

    async def _fetch_prices(self, client: httpx.AsyncClient) -> Dict[str, float]:
        results = {}
        try:
            resp = await client.get(
                BINANCE_TICKER_URL,
                params={"symbols": str([SYMBOLS[a] for a in ASSETS]).replace("'", '"')},
            )
            if resp.status_code == 200:
                for item in resp.json():
                    for asset, sym in SYMBOLS.items():
                        if item["symbol"] == sym:
                            results[asset] = float(item["price"])
        except Exception as exc:
            logger.warning("Price fetch error: %s", exc)
        return results

    def get_current_prices(self) -> Dict[str, float]:
        """Called by web routes to show live prices in the dashboard."""
        return dict(self._prices)
