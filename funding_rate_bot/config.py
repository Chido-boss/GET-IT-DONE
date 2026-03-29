"""
Configuration module for the Funding Rate Arbitrage Bot.
All settings are loaded from environment variables with sensible defaults.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env file if present (silently skip if missing)
_env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_env_path, override=False)


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


def _env_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    return float(val.strip())


def _env_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    return int(val.strip())


def _env_str(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()


@dataclass
class Config:
    # Exchange credentials
    bybit_api_key: str = field(default_factory=lambda: _env_str("BYBIT_API_KEY"))
    bybit_api_secret: str = field(default_factory=lambda: _env_str("BYBIT_API_SECRET"))

    okx_api_key: str = field(default_factory=lambda: _env_str("OKX_API_KEY"))
    okx_api_secret: str = field(default_factory=lambda: _env_str("OKX_API_SECRET"))
    okx_passphrase: str = field(default_factory=lambda: _env_str("OKX_PASSPHRASE"))

    # Trading mode
    paper_mode: bool = field(default_factory=lambda: _env_bool("PAPER_MODE", True))
    paper_starting_balance: float = field(
        default_factory=lambda: _env_float("PAPER_STARTING_BALANCE", 10_000.0)
    )

    # Entry / exit thresholds
    min_funding_rate: float = field(
        default_factory=lambda: _env_float("MIN_FUNDING_RATE", 0.0003)
    )
    exit_funding_rate: float = field(
        default_factory=lambda: _env_float("EXIT_FUNDING_RATE", 0.00005)
    )
    exit_consecutive_cycles: int = field(
        default_factory=lambda: _env_int("EXIT_CONSECUTIVE_CYCLES", 3)
    )

    # Position sizing
    max_position_size_pct: float = field(
        default_factory=lambda: _env_float("MAX_POSITION_SIZE_PCT", 0.15)
    )
    max_total_positions: int = field(
        default_factory=lambda: _env_int("MAX_TOTAL_POSITIONS", 8)
    )
    margin_buffer_pct: float = field(
        default_factory=lambda: _env_float("MARGIN_BUFFER_PCT", 0.25)
    )
    min_position_usdc: float = field(
        default_factory=lambda: _env_float("MIN_POSITION_USDC", 50.0)
    )
    max_position_usdc: float = field(
        default_factory=lambda: _env_float("MAX_POSITION_USDC", 2000.0)
    )

    # Timing
    scan_interval: int = field(default_factory=lambda: _env_int("SCAN_INTERVAL", 60))

    # Risk management
    daily_loss_limit_pct: float = field(
        default_factory=lambda: _env_float("DAILY_LOSS_LIMIT_PCT", 0.05)
    )

    # Storage
    log_file: str = field(default_factory=lambda: _env_str("LOG_FILE", "funding_bot.log"))
    db_file: str = field(default_factory=lambda: _env_str("DB_FILE", "funding_bot.db"))

    # Telegram (optional)
    telegram_bot_token: str = field(
        default_factory=lambda: _env_str("TELEGRAM_BOT_TOKEN")
    )
    telegram_chat_id: str = field(
        default_factory=lambda: _env_str("TELEGRAM_CHAT_ID")
    )

    # Derived / static constants
    basis_max_pct: float = 0.5        # Max basis (perp premium over spot) to enter
    basis_exit_pct: float = 0.8       # Exit if basis inverts past this level
    max_position_age_days: int = 7    # Force-exit positions older than this
    funding_interval_hours: int = 8   # Standard crypto funding interval
    perp_leverage: int = 1            # Always trade at 1x leverage

    # Annualisation factor: 3 payments/day × 365 days = 1095 periods per year
    funding_periods_per_year: int = 1095

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def bybit_enabled(self) -> bool:
        return bool(self.bybit_api_key and self.bybit_api_secret)

    @property
    def okx_enabled(self) -> bool:
        return bool(self.okx_api_key and self.okx_api_secret and self.okx_passphrase)

    def setup_logging(self) -> None:
        """Configure root logger to file + console."""
        log_path = Path(__file__).parent / self.log_file
        fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        logging.basicConfig(
            level=logging.INFO,
            format=fmt,
            handlers=[
                logging.FileHandler(log_path),
                logging.StreamHandler(),
            ],
        )
        # Quieten noisy third-party loggers
        for name in ("httpx", "httpcore", "websockets"):
            logging.getLogger(name).setLevel(logging.WARNING)

    def __post_init__(self) -> None:
        # Resolve DB path relative to module directory
        if not os.path.isabs(self.db_file):
            self.db_file = str(Path(__file__).parent / self.db_file)
        if not os.path.isabs(self.log_file):
            self.log_file = str(Path(__file__).parent / self.log_file)


# Module-level singleton – import and use directly
cfg = Config()
