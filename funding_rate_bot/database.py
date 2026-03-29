"""
Async SQLite database layer for the Funding Rate Arbitrage Bot.
Uses aiosqlite for non-blocking I/O, compatible with the asyncio event loop.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

import aiosqlite

from config import cfg

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema DDL
# ---------------------------------------------------------------------------

_DDL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS funding_snapshots (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp         TEXT    NOT NULL,
    exchange          TEXT    NOT NULL,
    symbol            TEXT    NOT NULL,
    funding_rate      REAL    NOT NULL,
    annualized_rate   REAL    NOT NULL,
    next_funding_time TEXT
);

CREATE INDEX IF NOT EXISTS idx_fs_exchange_symbol
    ON funding_snapshots (exchange, symbol, timestamp DESC);

CREATE TABLE IF NOT EXISTS positions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol                  TEXT    NOT NULL,
    exchange_spot           TEXT    NOT NULL,
    exchange_perp           TEXT    NOT NULL,
    spot_size               REAL    NOT NULL,
    perp_size               REAL    NOT NULL,
    entry_spot_price        REAL    NOT NULL,
    entry_perp_price        REAL    NOT NULL,
    entry_funding_rate      REAL    NOT NULL,
    entry_time              TEXT    NOT NULL,
    status                  TEXT    NOT NULL DEFAULT 'open',
    total_funding_collected REAL    NOT NULL DEFAULT 0.0,
    paper_mode              INTEGER NOT NULL DEFAULT 1,
    exit_time               TEXT,
    exit_spot_price         REAL,
    exit_perp_price         REAL,
    close_reason            TEXT,
    below_threshold_count   INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pos_status ON positions (status);

CREATE TABLE IF NOT EXISTS funding_payments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    position_id     INTEGER NOT NULL REFERENCES positions(id),
    timestamp       TEXT    NOT NULL,
    payment_amount  REAL    NOT NULL,
    funding_rate    REAL    NOT NULL,
    cumulative_total REAL   NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp      TEXT    NOT NULL,
    symbol         TEXT    NOT NULL,
    action         TEXT    NOT NULL,
    spot_exchange  TEXT    NOT NULL,
    perp_exchange  TEXT    NOT NULL,
    spot_price     REAL    NOT NULL,
    perp_price     REAL    NOT NULL,
    size_usdc      REAL    NOT NULL,
    reason         TEXT,
    pnl            REAL,
    paper_mode     INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS daily_stats (
    date                    TEXT    PRIMARY KEY,
    total_funding_collected REAL    NOT NULL DEFAULT 0.0,
    positions_opened        INTEGER NOT NULL DEFAULT 0,
    positions_closed        INTEGER NOT NULL DEFAULT 0,
    net_pnl                 REAL    NOT NULL DEFAULT 0.0
);
"""


# ---------------------------------------------------------------------------
# Database manager
# ---------------------------------------------------------------------------

class Database:
    """Async database wrapper. Call ``await db.init_db()`` before use."""

    def __init__(self, db_path: str | None = None) -> None:
        self._path = db_path or cfg.db_file
        self._conn: aiosqlite.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def init_db(self) -> None:
        """Open connection and create schema if it does not exist."""
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(_DDL)
        await self._conn.commit()
        logger.info("Database initialised at %s", self._path)

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _execute(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> aiosqlite.Cursor:
        assert self._conn is not None, "call init_db() first"
        cursor = await self._conn.execute(sql, params)
        await self._conn.commit()
        return cursor

    async def _fetchall(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> list[dict[str, Any]]:
        assert self._conn is not None, "call init_db() first"
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def _fetchone(
        self, sql: str, params: tuple[Any, ...] = ()
    ) -> dict[str, Any] | None:
        assert self._conn is not None, "call init_db() first"
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _today() -> str:
        return date.today().isoformat()

    # ------------------------------------------------------------------
    # Funding snapshots
    # ------------------------------------------------------------------

    async def log_funding_snapshot(
        self,
        exchange: str,
        symbol: str,
        funding_rate: float,
        annualized_rate: float,
        next_funding_time: str | None = None,
    ) -> None:
        await self._execute(
            """
            INSERT INTO funding_snapshots
                (timestamp, exchange, symbol, funding_rate, annualized_rate, next_funding_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (self._now(), exchange, symbol, funding_rate, annualized_rate, next_funding_time),
        )

    async def get_top_opportunities(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent funding snapshot per symbol with highest rate."""
        return await self._fetchall(
            """
            SELECT fs.*
            FROM funding_snapshots fs
            INNER JOIN (
                SELECT exchange, symbol, MAX(timestamp) AS max_ts
                FROM funding_snapshots
                GROUP BY exchange, symbol
            ) latest ON fs.exchange = latest.exchange
                     AND fs.symbol = latest.symbol
                     AND fs.timestamp = latest.max_ts
            WHERE fs.funding_rate > 0
            ORDER BY fs.funding_rate DESC
            LIMIT ?
            """,
            (limit,),
        )

    # ------------------------------------------------------------------
    # Positions
    # ------------------------------------------------------------------

    async def open_position(
        self,
        symbol: str,
        exchange_spot: str,
        exchange_perp: str,
        spot_size: float,
        perp_size: float,
        entry_spot_price: float,
        entry_perp_price: float,
        entry_funding_rate: float,
        paper_mode: bool = True,
    ) -> int:
        """Insert a new position and return its row id."""
        cursor = await self._execute(
            """
            INSERT INTO positions
                (symbol, exchange_spot, exchange_perp, spot_size, perp_size,
                 entry_spot_price, entry_perp_price, entry_funding_rate,
                 entry_time, status, paper_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                symbol,
                exchange_spot,
                exchange_perp,
                spot_size,
                perp_size,
                entry_spot_price,
                entry_perp_price,
                entry_funding_rate,
                self._now(),
                int(paper_mode),
            ),
        )
        pos_id = cursor.lastrowid
        await self._update_daily_stats(positions_opened=1)
        logger.info("Position opened: id=%s symbol=%s", pos_id, symbol)
        return pos_id  # type: ignore[return-value]

    async def close_position(
        self,
        position_id: int,
        exit_spot_price: float,
        exit_perp_price: float,
        close_reason: str,
        pnl: float,
    ) -> None:
        """Mark a position as closed and record exit details."""
        await self._execute(
            """
            UPDATE positions
            SET status = 'closed',
                exit_time = ?,
                exit_spot_price = ?,
                exit_perp_price = ?,
                close_reason = ?
            WHERE id = ?
            """,
            (self._now(), exit_spot_price, exit_perp_price, close_reason, position_id),
        )
        await self._update_daily_stats(positions_closed=1, net_pnl=pnl)
        logger.info("Position closed: id=%s reason=%s pnl=%.4f", position_id, close_reason, pnl)

    async def increment_below_threshold(self, position_id: int) -> int:
        """Increment the consecutive below-threshold counter and return new value."""
        await self._execute(
            "UPDATE positions SET below_threshold_count = below_threshold_count + 1 WHERE id = ?",
            (position_id,),
        )
        row = await self._fetchone(
            "SELECT below_threshold_count FROM positions WHERE id = ?", (position_id,)
        )
        return row["below_threshold_count"] if row else 0

    async def reset_below_threshold(self, position_id: int) -> None:
        await self._execute(
            "UPDATE positions SET below_threshold_count = 0 WHERE id = ?",
            (position_id,),
        )

    # ------------------------------------------------------------------
    # Funding payments
    # ------------------------------------------------------------------

    async def log_funding_payment(
        self,
        position_id: int,
        payment_amount: float,
        funding_rate: float,
    ) -> None:
        """Record a funding payment and update the position's cumulative total."""
        # Get current cumulative total for this position
        row = await self._fetchone(
            "SELECT total_funding_collected FROM positions WHERE id = ?",
            (position_id,),
        )
        if row is None:
            logger.warning("log_funding_payment: unknown position_id=%s", position_id)
            return
        new_total = row["total_funding_collected"] + payment_amount

        await self._execute(
            """
            INSERT INTO funding_payments
                (position_id, timestamp, payment_amount, funding_rate, cumulative_total)
            VALUES (?, ?, ?, ?, ?)
            """,
            (position_id, self._now(), payment_amount, funding_rate, new_total),
        )
        await self._execute(
            "UPDATE positions SET total_funding_collected = ? WHERE id = ?",
            (new_total, position_id),
        )
        await self._update_daily_stats(total_funding_collected=payment_amount)

    async def get_recent_payments(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return the most recent funding payments across all positions."""
        return await self._fetchall(
            """
            SELECT fp.*, p.symbol, p.exchange_perp
            FROM funding_payments fp
            JOIN positions p ON fp.position_id = p.id
            ORDER BY fp.timestamp DESC
            LIMIT ?
            """,
            (limit,),
        )

    # ------------------------------------------------------------------
    # Trades log
    # ------------------------------------------------------------------

    async def log_trade(
        self,
        symbol: str,
        action: str,
        spot_exchange: str,
        perp_exchange: str,
        spot_price: float,
        perp_price: float,
        size_usdc: float,
        reason: str | None = None,
        pnl: float | None = None,
        paper_mode: bool = True,
    ) -> None:
        await self._execute(
            """
            INSERT INTO trades
                (timestamp, symbol, action, spot_exchange, perp_exchange,
                 spot_price, perp_price, size_usdc, reason, pnl, paper_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self._now(),
                symbol,
                action,
                spot_exchange,
                perp_exchange,
                spot_price,
                perp_price,
                size_usdc,
                reason,
                pnl,
                int(paper_mode),
            ),
        )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_open_positions(self) -> list[dict[str, Any]]:
        return await self._fetchall(
            "SELECT * FROM positions WHERE status = 'open' ORDER BY entry_time ASC"
        )

    async def get_position_by_id(self, position_id: int) -> dict[str, Any] | None:
        return await self._fetchone(
            "SELECT * FROM positions WHERE id = ?", (position_id,)
        )

    async def get_open_symbols(self) -> set[str]:
        rows = await self._fetchall(
            "SELECT symbol FROM positions WHERE status = 'open'"
        )
        return {r["symbol"] for r in rows}

    async def get_daily_stats(self, for_date: str | None = None) -> dict[str, Any]:
        d = for_date or self._today()
        row = await self._fetchone(
            "SELECT * FROM daily_stats WHERE date = ?", (d,)
        )
        if row is None:
            return {
                "date": d,
                "total_funding_collected": 0.0,
                "positions_opened": 0,
                "positions_closed": 0,
                "net_pnl": 0.0,
            }
        return row

    async def get_all_time_funding(self) -> float:
        row = await self._fetchone(
            "SELECT COALESCE(SUM(total_funding_collected), 0) AS total FROM positions"
        )
        return row["total"] if row else 0.0

    # ------------------------------------------------------------------
    # Daily stats helpers
    # ------------------------------------------------------------------

    async def _update_daily_stats(
        self,
        total_funding_collected: float = 0.0,
        positions_opened: int = 0,
        positions_closed: int = 0,
        net_pnl: float = 0.0,
    ) -> None:
        today = self._today()
        await self._execute(
            """
            INSERT INTO daily_stats (date, total_funding_collected, positions_opened,
                                     positions_closed, net_pnl)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                total_funding_collected = total_funding_collected + excluded.total_funding_collected,
                positions_opened        = positions_opened + excluded.positions_opened,
                positions_closed        = positions_closed + excluded.positions_closed,
                net_pnl                 = net_pnl + excluded.net_pnl
            """,
            (today, total_funding_collected, positions_opened, positions_closed, net_pnl),
        )

    async def reset_daily_stats(self) -> None:
        """Called at midnight UTC to initialise a fresh daily_stats row."""
        today = self._today()
        await self._execute(
            """
            INSERT OR IGNORE INTO daily_stats (date) VALUES (?)
            """,
            (today,),
        )
        logger.info("Daily stats reset for %s", today)
