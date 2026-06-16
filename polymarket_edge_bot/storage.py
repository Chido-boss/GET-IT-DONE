"""
storage.py — SQLite persistence for markets, snapshots, signals, and paper trades.
"""

from __future__ import annotations
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


def connect(db_path: str) -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    _create_schema(conn)
    return conn


def _create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS markets (
            condition_id    TEXT PRIMARY KEY,
            question        TEXT NOT NULL,
            slug            TEXT,
            symbol          TEXT,
            market_type     TEXT,
            direction       TEXT,
            target_price    REAL,
            expiry_ts       REAL,
            yes_token_id    TEXT,
            no_token_id     TEXT,
            first_seen_ts   REAL,
            last_seen_ts    REAL,
            active          INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              REAL NOT NULL,
            condition_id    TEXT NOT NULL,
            yes_bid         REAL,
            yes_ask         REAL,
            yes_mid         REAL,
            no_bid          REAL,
            no_ask          REAL,
            no_mid          REAL,
            spread          REAL,
            liquidity       REAL,
            ref_price       REAL,
            ref_price_source TEXT,
            ref_price_age   REAL,
            vol_annual      REAL,
            momentum        REAL,
            fair_yes        REAL,
            fair_no         REAL,
            confidence      REAL,
            raw_json        TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_snapshots_ts ON snapshots(ts);
        CREATE INDEX IF NOT EXISTS idx_snapshots_cid ON snapshots(condition_id, ts);

        CREATE TABLE IF NOT EXISTS signals (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            ts              REAL NOT NULL,
            condition_id    TEXT NOT NULL,
            outcome         TEXT NOT NULL,
            action          TEXT NOT NULL,
            fair_value      REAL,
            executable_price REAL,
            raw_edge        REAL,
            adjusted_edge   REAL,
            confidence      REAL,
            reason          TEXT,
            skip_reason     TEXT
        );

        CREATE TABLE IF NOT EXISTS paper_trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            condition_id    TEXT NOT NULL,
            question        TEXT,
            outcome         TEXT NOT NULL,
            entry_ts        REAL NOT NULL,
            entry_price     REAL NOT NULL,
            fair_value_entry REAL,
            edge_entry      REAL,
            size_usd        REAL NOT NULL,
            num_contracts   REAL NOT NULL,
            expiry_ts       REAL,
            status          TEXT DEFAULT 'open',
            exit_ts         REAL,
            exit_price      REAL,
            exit_reason     TEXT,
            pnl             REAL,
            pnl_pct         REAL,
            max_adverse     REAL DEFAULT 0.0,
            max_favourable  REAL DEFAULT 0.0,
            hold_seconds    REAL,
            liquidity_entry REAL,
            spread_entry    REAL,
            signal_id       INTEGER
        );

        CREATE TABLE IF NOT EXISTS daily_metrics (
            date            TEXT PRIMARY KEY,
            scans           INTEGER DEFAULT 0,
            markets_seen    INTEGER DEFAULT 0,
            signals         INTEGER DEFAULT 0,
            paper_trades    INTEGER DEFAULT 0,
            paper_wins      INTEGER DEFAULT 0,
            paper_losses    INTEGER DEFAULT 0,
            paper_pnl       REAL DEFAULT 0.0,
            max_drawdown    REAL DEFAULT 0.0
        );
    """)
    conn.commit()


# ── Market helpers ─────────────────────────────────────────────────────────────

def upsert_market(conn: sqlite3.Connection, m: dict) -> None:
    now = time.time()
    conn.execute("""
        INSERT INTO markets
            (condition_id, question, slug, symbol, market_type, direction,
             target_price, expiry_ts, yes_token_id, no_token_id,
             first_seen_ts, last_seen_ts, active)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)
        ON CONFLICT(condition_id) DO UPDATE SET
            last_seen_ts = excluded.last_seen_ts,
            active       = 1
    """, (
        m["condition_id"], m["question"], m.get("slug"),
        m.get("symbol"), m.get("market_type"), m.get("direction"),
        m.get("target_price"), m.get("expiry_ts"),
        m.get("yes_token_id"), m.get("no_token_id"),
        now, now,
    ))
    conn.commit()


def save_snapshot(conn: sqlite3.Connection, snap: dict) -> int:
    cur = conn.execute("""
        INSERT INTO snapshots
            (ts, condition_id, yes_bid, yes_ask, yes_mid,
             no_bid, no_ask, no_mid, spread, liquidity,
             ref_price, ref_price_source, ref_price_age,
             vol_annual, momentum, fair_yes, fair_no, confidence, raw_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        snap.get("ts", time.time()),
        snap["condition_id"],
        snap.get("yes_bid"), snap.get("yes_ask"), snap.get("yes_mid"),
        snap.get("no_bid"),  snap.get("no_ask"),  snap.get("no_mid"),
        snap.get("spread"), snap.get("liquidity"),
        snap.get("ref_price"), snap.get("ref_price_source"), snap.get("ref_price_age"),
        snap.get("vol_annual"), snap.get("momentum"),
        snap.get("fair_yes"), snap.get("fair_no"), snap.get("confidence"),
        json.dumps(snap.get("raw", {})),
    ))
    conn.commit()
    return cur.lastrowid


def save_signal(conn: sqlite3.Connection, sig: dict) -> int:
    cur = conn.execute("""
        INSERT INTO signals
            (ts, condition_id, outcome, action, fair_value, executable_price,
             raw_edge, adjusted_edge, confidence, reason, skip_reason)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (
        sig.get("ts", time.time()),
        sig["condition_id"], sig["outcome"], sig["action"],
        sig.get("fair_value"), sig.get("executable_price"),
        sig.get("raw_edge"), sig.get("adjusted_edge"),
        sig.get("confidence"), sig.get("reason"), sig.get("skip_reason"),
    ))
    conn.commit()
    return cur.lastrowid


def open_paper_trade(conn: sqlite3.Connection, trade: dict) -> int:
    cur = conn.execute("""
        INSERT INTO paper_trades
            (condition_id, question, outcome, entry_ts, entry_price,
             fair_value_entry, edge_entry, size_usd, num_contracts,
             expiry_ts, liquidity_entry, spread_entry, signal_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        trade["condition_id"], trade.get("question"), trade["outcome"],
        trade["entry_ts"], trade["entry_price"],
        trade.get("fair_value_entry"), trade.get("edge_entry"),
        trade["size_usd"], trade["num_contracts"],
        trade.get("expiry_ts"), trade.get("liquidity_entry"),
        trade.get("spread_entry"), trade.get("signal_id"),
    ))
    conn.commit()
    return cur.lastrowid


def close_paper_trade(conn: sqlite3.Connection, trade_id: int, close: dict) -> None:
    conn.execute("""
        UPDATE paper_trades SET
            status        = 'closed',
            exit_ts       = ?,
            exit_price    = ?,
            exit_reason   = ?,
            pnl           = ?,
            pnl_pct       = ?,
            max_adverse   = ?,
            max_favourable= ?,
            hold_seconds  = ?
        WHERE id = ?
    """, (
        close["exit_ts"], close["exit_price"], close["exit_reason"],
        close["pnl"], close.get("pnl_pct"),
        close.get("max_adverse", 0), close.get("max_favourable", 0),
        close.get("hold_seconds"), trade_id,
    ))
    conn.commit()


def get_open_paper_trades(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM paper_trades WHERE status = 'open'"
    ).fetchall()
    return [dict(r) for r in rows]


def get_paper_trade(conn: sqlite3.Connection, trade_id: int) -> dict | None:
    row = conn.execute(
        "SELECT * FROM paper_trades WHERE id = ?", (trade_id,)
    ).fetchone()
    return dict(row) if row else None


def bump_daily_metric(conn: sqlite3.Connection, date_str: str, **kwargs: Any) -> None:
    conn.execute("""
        INSERT INTO daily_metrics (date) VALUES (?)
        ON CONFLICT(date) DO NOTHING
    """, (date_str,))
    for col, delta in kwargs.items():
        conn.execute(
            f"UPDATE daily_metrics SET {col} = {col} + ? WHERE date = ?",
            (delta, date_str)
        )
    conn.commit()


def get_daily_summary(conn: sqlite3.Connection, date_str: str) -> dict:
    row = conn.execute(
        "SELECT * FROM daily_metrics WHERE date = ?", (date_str,)
    ).fetchone()
    return dict(row) if row else {}


def get_closed_trades(conn: sqlite3.Connection, since_ts: float = 0) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM paper_trades WHERE status = 'closed' AND exit_ts >= ?",
        (since_ts,)
    ).fetchall()
    return [dict(r) for r in rows]
