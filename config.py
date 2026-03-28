"""
Configuration module for the Polymarket latency arbitrage bot.
All secrets loaded from environment variables — never hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _env_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key, "").strip().lower()
    if val in ("1", "true", "yes"):
        return True
    if val in ("0", "false", "no"):
        return False
    return default


def _env_float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


def _env_int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (ValueError, TypeError):
        return default


@dataclass
class Config:
    # ── Polymarket credentials ────────────────────────────────────────────────
    POLYMARKET_API_KEY: str = field(
        default_factory=lambda: os.getenv("POLYMARKET_API_KEY", "")
    )
    POLYMARKET_API_SECRET: str = field(
        default_factory=lambda: os.getenv("POLYMARKET_API_SECRET", "")
    )
    POLYMARKET_API_PASSPHRASE: str = field(
        default_factory=lambda: os.getenv("POLYMARKET_API_PASSPHRASE", "")
    )
    WALLET_ADDRESS: str = field(
        default_factory=lambda: os.getenv("WALLET_ADDRESS", "")
    )
    PRIVATE_KEY: str = field(
        default_factory=lambda: os.getenv("PRIVATE_KEY", "")
    )

    # ── Exchange endpoints ─────────────────────────────────────────────────────
    BINANCE_WS_URL: str = "wss://stream.binance.com:9443"
    POLYMARKET_CLOB_URL: str = "https://clob.polymarket.com"
    POLYMARKET_GAMMA_URL: str = "https://gamma-api.polymarket.com"

    # ── Trading mode ──────────────────────────────────────────────────────────
    PAPER_MODE: bool = field(default_factory=lambda: _env_bool("PAPER_MODE", True))
    # All three must be explicitly set True (via env or CLI) for live trading
    LIVE_FLAG_1: bool = field(default_factory=lambda: _env_bool("LIVE_FLAG_1", False))
    LIVE_FLAG_2: bool = field(default_factory=lambda: _env_bool("LIVE_FLAG_2", False))
    LIVE_FLAG_3: bool = field(default_factory=lambda: _env_bool("LIVE_FLAG_3", False))

    # ── Strategy parameters ───────────────────────────────────────────────────
    MIN_EDGE_PCT: float = field(
        default_factory=lambda: _env_float("MIN_EDGE_PCT", 5.0)
    )
    MIN_CONFIDENCE: float = field(
        default_factory=lambda: _env_float("MIN_CONFIDENCE", 0.85)
    )
    MAX_POSITION_PCT: float = field(
        default_factory=lambda: _env_float("MAX_POSITION_PCT", 0.08)
    )
    KELLY_FRACTION: float = field(
        default_factory=lambda: _env_float("KELLY_FRACTION", 0.5)
    )
    LAG_THRESHOLD_BASE: float = field(
        default_factory=lambda: _env_float("LAG_THRESHOLD_BASE", 3.0)
    )
    MOMENTUM_WINDOW: int = field(
        default_factory=lambda: _env_int("MOMENTUM_WINDOW", 30)
    )
    VOLATILITY_WINDOW: int = field(
        default_factory=lambda: _env_int("VOLATILITY_WINDOW", 300)
    )
    MIN_MARKET_LIQUIDITY: float = field(
        default_factory=lambda: _env_float("MIN_MARKET_LIQUIDITY", 50_000.0)
    )
    DEDUP_WINDOW_MS: int = field(
        default_factory=lambda: _env_int("DEDUP_WINDOW_MS", 500)
    )
    MAX_CONCURRENT_POSITIONS: int = field(
        default_factory=lambda: _env_int("MAX_CONCURRENT_POSITIONS", 10)
    )

    # ── Risk limits ───────────────────────────────────────────────────────────
    DAILY_LOSS_LIMIT_PCT: float = field(
        default_factory=lambda: _env_float("DAILY_LOSS_LIMIT_PCT", 0.20)
    )
    PER_ASSET_LOSS_LIMIT_PCT: float = field(
        default_factory=lambda: _env_float("PER_ASSET_LOSS_LIMIT_PCT", 0.10)
    )
    TOTAL_DRAWDOWN_KILL_PCT: float = field(
        default_factory=lambda: _env_float("TOTAL_DRAWDOWN_KILL_PCT", 0.40)
    )

    # ── Paper trading ─────────────────────────────────────────────────────────
    PAPER_STARTING_BALANCE: float = field(
        default_factory=lambda: _env_float("PAPER_STARTING_BALANCE", 1000.0)
    )
    PAPER_SLIPPAGE_PCT: float = field(
        default_factory=lambda: _env_float("PAPER_SLIPPAGE_PCT", 0.001)
    )  # 0.1%

    # ── Telegram ──────────────────────────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    TELEGRAM_CHAT_ID: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "")
    )

    # ── Logging ───────────────────────────────────────────────────────────────
    LOG_FILE: str = field(default_factory=lambda: os.getenv("LOG_FILE", "bot.log"))
    DB_FILE: str = field(default_factory=lambda: os.getenv("DB_FILE", "bot.db"))

    # ── Derived ───────────────────────────────────────────────────────────────
    @property
    def live_trading_enabled(self) -> bool:
        """All three live flags must be True AND PAPER_MODE must be False."""
        return (
            not self.PAPER_MODE
            and self.LIVE_FLAG_1
            and self.LIVE_FLAG_2
            and self.LIVE_FLAG_3
        )

    def enable_live_mode(self) -> None:
        """Called from CLI when --live --confirm --yes flags are passed."""
        self.PAPER_MODE = False
        self.LIVE_FLAG_1 = True
        self.LIVE_FLAG_2 = True
        self.LIVE_FLAG_3 = True

    def masked_repr(self) -> dict:
        """Return config dict with secrets masked for display."""

        def mask(val: str) -> str:
            if not val:
                return "<not set>"
            if len(val) <= 8:
                return "****"
            return val[:4] + "****" + val[-4:]

        return {
            "PAPER_MODE": self.PAPER_MODE,
            "LIVE_TRADING_ENABLED": self.live_trading_enabled,
            "POLYMARKET_API_KEY": mask(self.POLYMARKET_API_KEY),
            "WALLET_ADDRESS": mask(self.WALLET_ADDRESS),
            "BINANCE_WS_URL": self.BINANCE_WS_URL,
            "POLYMARKET_CLOB_URL": self.POLYMARKET_CLOB_URL,
            "MIN_EDGE_PCT": self.MIN_EDGE_PCT,
            "MIN_CONFIDENCE": self.MIN_CONFIDENCE,
            "MAX_POSITION_PCT": self.MAX_POSITION_PCT,
            "KELLY_FRACTION": self.KELLY_FRACTION,
            "LAG_THRESHOLD_BASE": self.LAG_THRESHOLD_BASE,
            "DAILY_LOSS_LIMIT_PCT": self.DAILY_LOSS_LIMIT_PCT,
            "PER_ASSET_LOSS_LIMIT_PCT": self.PER_ASSET_LOSS_LIMIT_PCT,
            "TOTAL_DRAWDOWN_KILL_PCT": self.TOTAL_DRAWDOWN_KILL_PCT,
            "PAPER_STARTING_BALANCE": self.PAPER_STARTING_BALANCE,
            "MIN_MARKET_LIQUIDITY": self.MIN_MARKET_LIQUIDITY,
            "MAX_CONCURRENT_POSITIONS": self.MAX_CONCURRENT_POSITIONS,
            "TELEGRAM_BOT_TOKEN": mask(self.TELEGRAM_BOT_TOKEN),
            "TELEGRAM_CHAT_ID": mask(self.TELEGRAM_CHAT_ID),
            "DB_FILE": self.DB_FILE,
            "LOG_FILE": self.LOG_FILE,
        }


# Singleton instance used across the whole application
cfg = Config()
