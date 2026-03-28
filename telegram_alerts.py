"""
Telegram notification system using direct Bot API calls via httpx.
All sends are non-blocking — failures are logged but never propagate to trading logic.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx

from config import cfg

logger = logging.getLogger(__name__)

_TELEGRAM_API_BASE = "https://api.telegram.org/bot"


class TelegramAlerter:
    """
    Sends Telegram messages via HTTP.
    Falls back to console logging when no token is configured.
    """

    def __init__(self) -> None:
        self._token = cfg.TELEGRAM_BOT_TOKEN
        self._chat_id = cfg.TELEGRAM_CHAT_ID
        self._enabled = bool(self._token and self._chat_id)
        self._http: Optional[httpx.AsyncClient] = None
        self._send_lock = asyncio.Lock()

        if not self._enabled:
            logger.info(
                "Telegram not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set). "
                "Alerts will be logged to console only."
            )

    async def __aenter__(self) -> TelegramAlerter:
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
        return self

    async def __aexit__(self, *_) -> None:
        if self._http:
            await self._http.aclose()

    # ── Core send ─────────────────────────────────────────────────────────────

    async def send_message(self, text: str) -> None:
        """Send a message. Non-blocking — swallows all exceptions."""
        if not self._enabled:
            logger.info("[TELEGRAM] %s", text)
            return

        async with self._send_lock:
            try:
                url = f"{_TELEGRAM_API_BASE}{self._token}/sendMessage"
                payload = {
                    "chat_id": self._chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                }
                if self._http is None:
                    self._http = httpx.AsyncClient(timeout=httpx.Timeout(10.0))
                resp = await self._http.post(url, json=payload)
                if resp.status_code != 200:
                    logger.warning(
                        "Telegram API returned %d: %s",
                        resp.status_code, resp.text[:200],
                    )
            except Exception as exc:
                logger.warning("Telegram send failed (non-fatal): %s", exc)

    # ── Alert helpers ─────────────────────────────────────────────────────────

    async def trade_opened(
        self,
        asset: str,
        direction: str,
        size_usdc: float,
        edge_pct: float,
        confidence: float,
        entry_price: float,
        paper_mode: bool,
    ) -> None:
        mode = "📄 PAPER" if paper_mode else "🔴 LIVE"
        arrow = "⬆️" if direction == "YES" else "⬇️"
        text = (
            f"{mode} | Trade Opened {arrow}\n"
            f"<b>Asset:</b> {asset}\n"
            f"<b>Direction:</b> {direction}\n"
            f"<b>Size:</b> ${size_usdc:.2f} USDC\n"
            f"<b>Entry Price:</b> {entry_price:.4f}\n"
            f"<b>Edge:</b> {edge_pct:.1f}%\n"
            f"<b>Confidence:</b> {confidence:.1%}\n"
            f"<b>Time:</b> {_now_utc()}"
        )
        asyncio.create_task(self.send_message(text))

    async def trade_closed(
        self,
        asset: str,
        direction: str,
        size_usdc: float,
        pnl: float,
        hold_duration_sec: float,
        outcome: str,
        paper_mode: bool,
    ) -> None:
        mode = "📄 PAPER" if paper_mode else "🔴 LIVE"
        pnl_sign = "+" if pnl >= 0 else ""
        outcome_emoji = "✅" if outcome == "WIN" else "❌" if outcome == "LOSS" else "➖"
        text = (
            f"{mode} | Trade Closed {outcome_emoji}\n"
            f"<b>Asset:</b> {asset} ({direction})\n"
            f"<b>Size:</b> ${size_usdc:.2f} USDC\n"
            f"<b>P&amp;L:</b> {pnl_sign}${pnl:.4f}\n"
            f"<b>Outcome:</b> {outcome}\n"
            f"<b>Hold:</b> {hold_duration_sec:.0f}s\n"
            f"<b>Time:</b> {_now_utc()}"
        )
        asyncio.create_task(self.send_message(text))

    async def kill_switch_triggered(self, reason: str, daily_pnl: float) -> None:
        text = (
            f"🚨 <b>KILL SWITCH TRIGGERED</b> 🚨\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Daily P&amp;L:</b> ${daily_pnl:.4f}\n"
            f"<b>Time:</b> {_now_utc()}\n"
            f"All trading halted."
        )
        await self.send_message(text)

    async def asset_paused(self, asset: str, reason: str) -> None:
        text = (
            f"⚠️ {asset} Trading Paused\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Time:</b> {_now_utc()}"
        )
        asyncio.create_task(self.send_message(text))

    async def drawdown_warning(self, current_drawdown_pct: float, portfolio_value: float) -> None:
        text = (
            f"⚠️ Drawdown Warning\n"
            f"<b>Current Drawdown:</b> {current_drawdown_pct:.1%}\n"
            f"<b>Portfolio:</b> ${portfolio_value:.2f}\n"
            f"<b>Time:</b> {_now_utc()}"
        )
        asyncio.create_task(self.send_message(text))

    async def daily_summary(
        self,
        total_trades: int,
        wins: int,
        losses: int,
        net_pnl: float,
        win_rate: float,
        portfolio_value: float,
        max_drawdown: float,
        paper_mode: bool,
    ) -> None:
        mode = "📄 PAPER" if paper_mode else "🔴 LIVE"
        pnl_sign = "+" if net_pnl >= 0 else ""
        text = (
            f"{mode} | Daily Summary 📊\n"
            f"<b>Date:</b> {_today_utc()}\n"
            f"<b>Trades:</b> {total_trades} (W: {wins} / L: {losses})\n"
            f"<b>Win Rate:</b> {win_rate:.1%}\n"
            f"<b>Net P&amp;L:</b> {pnl_sign}${net_pnl:.4f}\n"
            f"<b>Portfolio:</b> ${portfolio_value:.2f}\n"
            f"<b>Max Drawdown:</b> {max_drawdown:.1%}\n"
        )
        await self.send_message(text)

    async def startup_notification(self, mode: str, portfolio_value: float) -> None:
        text = (
            f"🤖 Polymarket Arb Bot Started\n"
            f"<b>Mode:</b> {mode}\n"
            f"<b>Portfolio:</b> ${portfolio_value:.2f}\n"
            f"<b>Time:</b> {_now_utc()}"
        )
        asyncio.create_task(self.send_message(text))

    async def shutdown_notification(self, reason: str, portfolio_value: float) -> None:
        text = (
            f"🛑 Bot Shutting Down\n"
            f"<b>Reason:</b> {reason}\n"
            f"<b>Portfolio:</b> ${portfolio_value:.2f}\n"
            f"<b>Time:</b> {_now_utc()}"
        )
        await self.send_message(text)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _now_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _today_utc() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
