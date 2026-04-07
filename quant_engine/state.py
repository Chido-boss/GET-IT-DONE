"""
state.py — Persistent state management via a JSON file.

Schema:
{
  "equity":            float,
  "realized_pnl":      float,   # cumulative all-time
  "day_start_equity":  float,
  "day_date":          str,      # "YYYY-MM-DD"
  "position":          dict|null,
  "bars_since_exit":   int,
  "bar_count":         int,
  "last_candle_ts":    int,      # ms timestamp of last processed candle
  "trade_history":     list[dict],
  "daily_pnl_history": list[dict]
}
"""

from __future__ import annotations
import json
import os
from datetime import date, datetime, timezone
from typing import Any, Optional
from config import cfg


def _default_state() -> dict:
    return {
        "equity":            cfg.starting_equity,
        "realized_pnl":      0.0,
        "day_start_equity":  cfg.starting_equity,
        "day_date":          str(date.today()),
        "position":          None,
        "bars_since_exit":   9999,   # start ready to trade
        "bar_count":         0,
        "last_candle_ts":    0,
        "trade_history":     [],
        "daily_pnl_history": [],
    }


def load() -> dict:
    if os.path.exists(cfg.state_file):
        try:
            with open(cfg.state_file, "r") as f:
                saved = json.load(f)
            # Forward-compatible: fill in any missing keys
            base = _default_state()
            base.update(saved)
            return base
        except (json.JSONDecodeError, OSError):
            pass
    return _default_state()


def save(state: dict) -> None:
    tmp = cfg.state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, default=str)
    os.replace(tmp, cfg.state_file)   # atomic on Linux


def maybe_reset_day(state: dict) -> bool:
    """
    If a new calendar day (UTC) has started, archive yesterday's stats and
    reset day_start_equity. Returns True if a reset happened.
    """
    today = str(date.today())
    if state["day_date"] == today:
        return False

    yesterday_pnl = state["equity"] - state["day_start_equity"]
    state["daily_pnl_history"].append({
        "date":   state["day_date"],
        "pnl":    round(yesterday_pnl, 4),
        "equity": round(state["equity"], 4),
        "trades": sum(
            1 for t in state["trade_history"]
            if t.get("exit_time", "").startswith(state["day_date"])
        ),
    })

    state["day_date"] = today
    state["day_start_equity"] = state["equity"]
    return True


def record_trade(state: dict, trade: dict) -> None:
    """Append a closed trade to history and update equity + realized PnL."""
    state["trade_history"].append(trade)
    state["realized_pnl"] = round(state.get("realized_pnl", 0.0) + trade["pnl"], 4)
    state["equity"]        = round(state["equity"] + trade["pnl"], 4)


def summary(state: dict) -> str:
    """One-line human summary of current state."""
    trades = len(state["trade_history"])
    wins   = sum(1 for t in state["trade_history"] if t["pnl"] > 0)
    win_rate = (wins / trades * 100) if trades else 0.0
    daily_pnl = state["equity"] - state["day_start_equity"]
    return (
        f"equity=${state['equity']:,.2f}  "
        f"realized={'+' if state['realized_pnl']>=0 else ''}"
        f"${state['realized_pnl']:,.2f}  "
        f"trades={trades}  "
        f"win%={win_rate:.0f}  "
        f"daily={'+' if daily_pnl>=0 else ''}${daily_pnl:,.2f}"
    )
