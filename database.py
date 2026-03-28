"""
Async SQLite database manager using aiosqlite.
Handles all persistence: trades, positions, price snapshots, and daily stats.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import List, Optional

import aiosqlite

from config import cfg

logger = logging.getLogger(__name__)


# ── Dataclasses for DB rows ────────────────────────────────────────────────────

@dataclass
class TradeRecord:
    id: Optional[int]
    timestamp: datetime
    asset: str
    contract_id: str
    direction: str          # "YES" or "NO"
    entry_price: float
    exit_price: Optional[float]
    size_usdc: float
    pnl: Optional[float]
    edge_at_entry: float
    confidence_at_entry: float
    hold_duration_sec: Optional[float]
    outcome: Optional[str]  # "WIN", "LOSS", "EVEN", "OPEN"
    paper_mode: bool


@dataclass
class PositionRecord:
    id: Optional[int]
    contract_id: str
    asset: str
    direction: str
    entry_price: float
    size_usdc: float
    entry_edge: float
    entry_confidence: float
    entry_time: datetime
    status: str             # "open" or "closed"


@dataclass
class PriceSnapshotRecord:
    timestamp: datetime
    asset: str
    binance_price: float
    polymarket_yes_price: float
    polymarket_no_price: float
    implied_prob: float
    edge: float


@dataclass
class DailyStatsRecord:
    date: date
    total_trades: int
    wins: int
    losses: int
    gross_pnl: float
    net_pnl: float
    max_drawdown: float
    win_rate: float


# ── Database manager ──────────────────────────────────────────────────────────

class Database:
    """Async SQLite manager. Call await db.init_db() before any other method."""

    def __init__(self, db_path: str = cfg.DB_FILE) -> None:
        self._db_path = db_path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init_db(self) -> None:
        """Open connection and create all tables if they don't exist."""
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL;")
        await self._conn.execute("PRAGMA synchronous=NORMAL;")
        await self._create_tables()
        await self._conn.commit()
        logger.info("Database initialised at %s", self._db_path)

    async def _create_tables(self) -> None:
        await self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp            TEXT NOT NULL,
                asset                TEXT NOT NULL,
                contract_id          TEXT NOT NULL,
                direction            TEXT NOT NULL,
                entry_price          REAL NOT NULL,
                exit_price           REAL,
                size_usdc            REAL NOT NULL,
                pnl                  REAL,
                edge_at_entry        REAL NOT NULL,
                confidence_at_entry  REAL NOT NULL,
                hold_duration_sec    REAL,
                outcome              TEXT,
                paper_mode           INTEGER NOT NULL DEFAULT 1
            );

            CREATE INDEX IF NOT EXISTS idx_trades_timestamp ON trades(timestamp);
            CREATE INDEX IF NOT EXISTS idx_trades_asset ON trades(asset);

            CREATE TABLE IF NOT EXISTS positions (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                contract_id         TEXT NOT NULL,
                asset               TEXT NOT NULL,
                direction           TEXT NOT NULL,
                entry_price         REAL NOT NULL,
                size_usdc           REAL NOT NULL,
                entry_edge          REAL NOT NULL,
                entry_confidence    REAL NOT NULL,
                entry_time          TEXT NOT NULL,
                status              TEXT NOT NULL DEFAULT 'open'
            );

            CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
            CREATE INDEX IF NOT EXISTS idx_positions_contract ON positions(contract_id);

            CREATE TABLE IF NOT EXISTS price_snapshots (
                id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp               TEXT NOT NULL,
                asset                   TEXT NOT NULL,
                binance_price           REAL NOT NULL,
                polymarket_yes_price    REAL NOT NULL,
                polymarket_no_price     REAL NOT NULL,
                implied_prob            REAL NOT NULL,
                edge                    REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp ON price_snapshots(timestamp);
            CREATE INDEX IF NOT EXISTS idx_snapshots_asset ON price_snapshots(asset);

            CREATE TABLE IF NOT EXISTS daily_stats (
                date          TEXT PRIMARY KEY,
                total_trades  INTEGER NOT NULL DEFAULT 0,
                wins          INTEGER NOT NULL DEFAULT 0,
                losses        INTEGER NOT NULL DEFAULT 0,
                gross_pnl     REAL NOT NULL DEFAULT 0.0,
                net_pnl       REAL NOT NULL DEFAULT 0.0,
                max_drawdown  REAL NOT NULL DEFAULT 0.0,
                win_rate      REAL NOT NULL DEFAULT 0.0
            );
            """
        )

    # ── Writes ────────────────────────────────────────────────────────────────

    async def log_trade(self, trade: TradeRecord) -> int:
        """Insert a completed trade record and return its row id."""
        cursor = await self._conn.execute(
            """
            INSERT INTO trades
              (timestamp, asset, contract_id, direction, entry_price, exit_price,
               size_usdc, pnl, edge_at_entry, confidence_at_entry,
               hold_duration_sec, outcome, paper_mode)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                trade.timestamp.isoformat(),
                trade.asset,
                trade.contract_id,
                trade.direction,
                trade.entry_price,
                trade.exit_price,
                trade.size_usdc,
                trade.pnl,
                trade.edge_at_entry,
                trade.confidence_at_entry,
                trade.hold_duration_sec,
                trade.outcome,
                int(trade.paper_mode),
            ),
        )
        await self._conn.commit()
        row_id: int = cursor.lastrowid
        logger.debug("Logged trade id=%d asset=%s pnl=%s", row_id, trade.asset, trade.pnl)
        return row_id

    async def log_position_open(self, pos: PositionRecord) -> int:
        """Insert a new open position and return its row id."""
        cursor = await self._conn.execute(
            """
            INSERT INTO positions
              (contract_id, asset, direction, entry_price, size_usdc,
               entry_edge, entry_confidence, entry_time, status)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                pos.contract_id,
                pos.asset,
                pos.direction,
                pos.entry_price,
                pos.size_usdc,
                pos.entry_edge,
                pos.entry_confidence,
                pos.entry_time.isoformat(),
                pos.status,
            ),
        )
        await self._conn.commit()
        row_id: int = cursor.lastrowid
        logger.debug(
            "Opened position id=%d %s %s %s",
            row_id, pos.asset, pos.direction, pos.contract_id,
        )
        return row_id

    async def log_position_close(
        self,
        position_id: int,
        exit_price: float,
        pnl: float,
        outcome: str,
    ) -> None:
        """Mark a position as closed."""
        await self._conn.execute(
            "UPDATE positions SET status='closed' WHERE id=?",
            (position_id,),
        )
        await self._conn.commit()
        logger.debug("Closed position id=%d outcome=%s pnl=%.4f", position_id, outcome, pnl)

    async def log_price_snapshot(self, snap: PriceSnapshotRecord) -> None:
        """Insert a price snapshot (fire-and-forget, throttled by caller)."""
        await self._conn.execute(
            """
            INSERT INTO price_snapshots
              (timestamp, asset, binance_price, polymarket_yes_price,
               polymarket_no_price, implied_prob, edge)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                snap.timestamp.isoformat(),
                snap.asset,
                snap.binance_price,
                snap.polymarket_yes_price,
                snap.polymarket_no_price,
                snap.implied_prob,
                snap.edge,
            ),
        )
        # Batch commit is handled by caller or periodic flush
        await self._conn.commit()

    async def upsert_daily_stats(self, stats: DailyStatsRecord) -> None:
        """Insert or replace daily stats row."""
        await self._conn.execute(
            """
            INSERT INTO daily_stats
              (date, total_trades, wins, losses, gross_pnl, net_pnl,
               max_drawdown, win_rate)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(date) DO UPDATE SET
              total_trades = excluded.total_trades,
              wins         = excluded.wins,
              losses       = excluded.losses,
              gross_pnl    = excluded.gross_pnl,
              net_pnl      = excluded.net_pnl,
              max_drawdown = excluded.max_drawdown,
              win_rate     = excluded.win_rate
            """,
            (
                stats.date.isoformat(),
                stats.total_trades,
                stats.wins,
                stats.losses,
                stats.gross_pnl,
                stats.net_pnl,
                stats.max_drawdown,
                stats.win_rate,
            ),
        )
        await self._conn.commit()

    # ── Reads ─────────────────────────────────────────────────────────────────

    async def get_daily_stats(self, d: Optional[date] = None) -> Optional[DailyStatsRecord]:
        """Return stats for a given date (default: today UTC)."""
        target = (d or datetime.now(tz=timezone.utc).date()).isoformat()
        async with self._conn.execute(
            "SELECT * FROM daily_stats WHERE date=?", (target,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        return DailyStatsRecord(
            date=date.fromisoformat(row["date"]),
            total_trades=row["total_trades"],
            wins=row["wins"],
            losses=row["losses"],
            gross_pnl=row["gross_pnl"],
            net_pnl=row["net_pnl"],
            max_drawdown=row["max_drawdown"],
            win_rate=row["win_rate"],
        )

    async def get_last_n_trades(self, n: int = 10) -> List[TradeRecord]:
        """Return the n most recent closed trades."""
        rows = []
        async with self._conn.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (n,)
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_trade(r) for r in rows]

    async def get_open_positions(self) -> List[PositionRecord]:
        """Return all positions with status='open'."""
        async with self._conn.execute(
            "SELECT * FROM positions WHERE status='open' ORDER BY entry_time ASC"
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_position(r) for r in rows]

    async def get_total_pnl(self) -> float:
        """Sum of pnl across all closed trades."""
        async with self._conn.execute(
            "SELECT COALESCE(SUM(pnl), 0.0) AS total FROM trades WHERE outcome IS NOT NULL"
        ) as cur:
            row = await cur.fetchone()
        return float(row["total"]) if row else 0.0

    async def get_trades_for_date(self, d: Optional[date] = None) -> List[TradeRecord]:
        """Return all trades for a given date."""
        target = (d or datetime.now(tz=timezone.utc).date()).isoformat()
        async with self._conn.execute(
            "SELECT * FROM trades WHERE timestamp LIKE ? ORDER BY timestamp ASC",
            (f"{target}%",),
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_trade(r) for r in rows]

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            logger.info("Database connection closed.")


# ── Row helpers ───────────────────────────────────────────────────────────────

def _row_to_trade(row: aiosqlite.Row) -> TradeRecord:
    return TradeRecord(
        id=row["id"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        asset=row["asset"],
        contract_id=row["contract_id"],
        direction=row["direction"],
        entry_price=row["entry_price"],
        exit_price=row["exit_price"],
        size_usdc=row["size_usdc"],
        pnl=row["pnl"],
        edge_at_entry=row["edge_at_entry"],
        confidence_at_entry=row["confidence_at_entry"],
        hold_duration_sec=row["hold_duration_sec"],
        outcome=row["outcome"],
        paper_mode=bool(row["paper_mode"]),
    )


def _row_to_position(row: aiosqlite.Row) -> PositionRecord:
    return PositionRecord(
        id=row["id"],
        contract_id=row["contract_id"],
        asset=row["asset"],
        direction=row["direction"],
        entry_price=row["entry_price"],
        size_usdc=row["size_usdc"],
        entry_edge=row["entry_edge"],
        entry_confidence=row["entry_confidence"],
        entry_time=datetime.fromisoformat(row["entry_time"]),
        status=row["status"],
    )
