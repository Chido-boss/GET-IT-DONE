"""
Database layer for CryptoWatch SaaS.
Tables: users, subscriptions, alerts, alert_history
All async via aiosqlite.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import List, Optional

import aiosqlite

DB_PATH = os.getenv("DB_FILE", "cryptowatch.db")


# ── Schema ─────────────────────────────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    email       TEXT    UNIQUE NOT NULL,
    pw_hash     TEXT    NOT NULL,
    telegram_chat_id TEXT DEFAULT '',
    created_at  REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id             INTEGER NOT NULL REFERENCES users(id),
    stripe_customer_id  TEXT    DEFAULT '',
    stripe_sub_id       TEXT    DEFAULT '',
    plan                TEXT    NOT NULL DEFAULT 'free',   -- free | starter | pro
    status              TEXT    NOT NULL DEFAULT 'active', -- active | cancelled | past_due
    current_period_end  REAL    DEFAULT 0,
    updated_at          REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    asset       TEXT    NOT NULL,           -- BTC | ETH
    condition   TEXT    NOT NULL,           -- above | below | change_pct
    threshold   REAL    NOT NULL,
    label       TEXT    DEFAULT '',         -- user-given name
    enabled     INTEGER NOT NULL DEFAULT 1,
    last_fired  REAL    DEFAULT 0,
    cooldown_sec INTEGER NOT NULL DEFAULT 3600,
    created_at  REAL    NOT NULL DEFAULT (strftime('%s','now'))
);

CREATE TABLE IF NOT EXISTS alert_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id    INTEGER NOT NULL REFERENCES alerts(id),
    user_id     INTEGER NOT NULL,
    asset       TEXT    NOT NULL,
    price_at_fire REAL  NOT NULL,
    message     TEXT    NOT NULL,
    fired_at    REAL    NOT NULL DEFAULT (strftime('%s','now'))
);
"""

PLAN_LIMITS = {
    "free":    1,
    "starter": 10,
    "pro":     9999,
}


# ── Dataclasses ────────────────────────────────────────────────────────────────

@dataclass
class User:
    id: int
    email: str
    pw_hash: str
    telegram_chat_id: str
    created_at: float


@dataclass
class Subscription:
    id: int
    user_id: int
    stripe_customer_id: str
    stripe_sub_id: str
    plan: str
    status: str
    current_period_end: float


@dataclass
class Alert:
    id: int
    user_id: int
    asset: str
    condition: str
    threshold: float
    label: str
    enabled: bool
    last_fired: float
    cooldown_sec: int
    created_at: float


# ── DB class ───────────────────────────────────────────────────────────────────

class Database:
    def __init__(self, path: str = DB_PATH) -> None:
        self._path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    # ── Users ──────────────────────────────────────────────────────────────────

    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.getenv("PW_SALT", "cryptowatch-salt-change-me")
        return hashlib.sha256(f"{salt}{password}".encode()).hexdigest()

    async def create_user(self, email: str, password: str) -> Optional[User]:
        pw_hash = self.hash_password(password)
        try:
            async with self._conn.execute(
                "INSERT INTO users (email, pw_hash) VALUES (?, ?)",
                (email.lower().strip(), pw_hash),
            ) as cur:
                user_id = cur.lastrowid
            await self._conn.commit()
            # Create free subscription for new user
            await self._conn.execute(
                "INSERT INTO subscriptions (user_id, plan, status) VALUES (?, 'free', 'active')",
                (user_id,),
            )
            await self._conn.commit()
            return await self.get_user_by_id(user_id)
        except aiosqlite.IntegrityError:
            return None  # Email already exists

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with self._conn.execute(
            "SELECT * FROM users WHERE email = ?", (email.lower().strip(),)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_user(row) if row else None

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        async with self._conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_user(row) if row else None

    async def verify_password(self, email: str, password: str) -> Optional[User]:
        user = await self.get_user_by_email(email)
        if user and user.pw_hash == self.hash_password(password):
            return user
        return None

    async def update_telegram_chat_id(self, user_id: int, chat_id: str) -> None:
        await self._conn.execute(
            "UPDATE users SET telegram_chat_id = ? WHERE id = ?", (chat_id, user_id)
        )
        await self._conn.commit()

    # ── Subscriptions ──────────────────────────────────────────────────────────

    async def get_subscription(self, user_id: int) -> Optional[Subscription]:
        async with self._conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return _row_to_sub(row) if row else None

    async def upsert_subscription(
        self,
        user_id: int,
        plan: str,
        status: str,
        stripe_customer_id: str = "",
        stripe_sub_id: str = "",
        current_period_end: float = 0,
    ) -> None:
        await self._conn.execute(
            """
            UPDATE subscriptions
            SET plan=?, status=?, stripe_customer_id=?, stripe_sub_id=?,
                current_period_end=?, updated_at=unixepoch()
            WHERE user_id=?
            """,
            (plan, status, stripe_customer_id, stripe_sub_id, current_period_end, user_id),
        )
        await self._conn.commit()

    async def get_alert_count(self, user_id: int) -> int:
        async with self._conn.execute(
            "SELECT COUNT(*) FROM alerts WHERE user_id = ? AND enabled = 1", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return row[0] if row else 0

    async def can_create_alert(self, user_id: int) -> bool:
        sub = await self.get_subscription(user_id)
        plan = sub.plan if sub else "free"
        limit = PLAN_LIMITS.get(plan, 1)
        count = await self.get_alert_count(user_id)
        return count < limit

    # ── Alerts ─────────────────────────────────────────────────────────────────

    async def create_alert(
        self,
        user_id: int,
        asset: str,
        condition: str,
        threshold: float,
        label: str = "",
        cooldown_sec: int = 3600,
    ) -> Optional[Alert]:
        if not await self.can_create_alert(user_id):
            return None
        async with self._conn.execute(
            """
            INSERT INTO alerts (user_id, asset, condition, threshold, label, cooldown_sec)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, asset.upper(), condition, threshold, label, cooldown_sec),
        ) as cur:
            alert_id = cur.lastrowid
        await self._conn.commit()
        return await self.get_alert(alert_id)

    async def get_alert(self, alert_id: int) -> Optional[Alert]:
        async with self._conn.execute(
            "SELECT * FROM alerts WHERE id = ?", (alert_id,)
        ) as cur:
            row = await cur.fetchone()
        return _row_to_alert(row) if row else None

    async def get_user_alerts(self, user_id: int) -> List[Alert]:
        async with self._conn.execute(
            "SELECT * FROM alerts WHERE user_id = ? ORDER BY created_at DESC", (user_id,)
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_alert(r) for r in rows]

    async def delete_alert(self, alert_id: int, user_id: int) -> bool:
        async with self._conn.execute(
            "DELETE FROM alerts WHERE id = ? AND user_id = ?", (alert_id, user_id)
        ) as cur:
            return cur.rowcount > 0

    async def toggle_alert(self, alert_id: int, user_id: int, enabled: bool) -> None:
        await self._conn.execute(
            "UPDATE alerts SET enabled = ? WHERE id = ? AND user_id = ?",
            (1 if enabled else 0, alert_id, user_id),
        )
        await self._conn.commit()

    async def get_all_active_alerts(self) -> List[Alert]:
        """Used by alert monitor to load all enabled alerts."""
        async with self._conn.execute(
            "SELECT * FROM alerts WHERE enabled = 1"
        ) as cur:
            rows = await cur.fetchall()
        return [_row_to_alert(r) for r in rows]

    async def record_alert_fired(
        self, alert: Alert, price: float, message: str
    ) -> None:
        now = time.time()
        await self._conn.execute(
            "UPDATE alerts SET last_fired = ? WHERE id = ?", (now, alert.id)
        )
        await self._conn.execute(
            """
            INSERT INTO alert_history (alert_id, user_id, asset, price_at_fire, message, fired_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (alert.id, alert.user_id, alert.asset, price, message, now),
        )
        await self._conn.commit()

    async def get_alert_history(self, user_id: int, limit: int = 20) -> list:
        async with self._conn.execute(
            """
            SELECT ah.*, a.label FROM alert_history ah
            LEFT JOIN alerts a ON ah.alert_id = a.id
            WHERE ah.user_id = ?
            ORDER BY ah.fired_at DESC LIMIT ?
            """,
            (user_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]


# ── Row helpers ────────────────────────────────────────────────────────────────

def _row_to_user(row) -> User:
    return User(
        id=row["id"],
        email=row["email"],
        pw_hash=row["pw_hash"],
        telegram_chat_id=row["telegram_chat_id"] or "",
        created_at=row["created_at"],
    )


def _row_to_sub(row) -> Subscription:
    return Subscription(
        id=row["id"],
        user_id=row["user_id"],
        stripe_customer_id=row["stripe_customer_id"] or "",
        stripe_sub_id=row["stripe_sub_id"] or "",
        plan=row["plan"],
        status=row["status"],
        current_period_end=row["current_period_end"],
    )


def _row_to_alert(row) -> Alert:
    return Alert(
        id=row["id"],
        user_id=row["user_id"],
        asset=row["asset"],
        condition=row["condition"],
        threshold=row["threshold"],
        label=row["label"] or "",
        enabled=bool(row["enabled"]),
        last_fired=row["last_fired"] or 0.0,
        cooldown_sec=row["cooldown_sec"],
        created_at=row["created_at"],
    )
