"""
logger.py — Structured, human-readable event logging.

Every significant event has a fixed-width type tag so logs are grep-able:
  ENTRY   EXIT   PNL   EQUITY   SIGNAL   SKIP   ERROR   INFO
"""

from __future__ import annotations
import logging
import sys
from datetime import datetime, timezone
from config import cfg


# ── ANSI colour codes (disabled in file handler automatically) ─────────────────

_RESET  = "\033[0m"
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_DIM    = "\033[2m"
_BOLD   = "\033[1m"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class QuantLogger:
    """Thin wrapper that writes structured lines to both console and a log file."""

    def __init__(self) -> None:
        self._file = open(cfg.log_file, "a", buffering=1)  # line-buffered

    def _write(self, tag: str, msg: str, colour: str = "") -> None:
        ts = _now()
        plain = f"{ts} | {tag:<7} | {msg}"
        coloured = f"{_DIM}{ts}{_RESET} | {colour}{_BOLD}{tag:<7}{_RESET} | {msg}"
        print(coloured, flush=True)
        self._file.write(plain + "\n")

    # ── Public event methods ───────────────────────────────────────────────────

    def entry(self, direction: str, symbol: str, price: float,
              size_usd: float, sl: float, tp: float, atr: float) -> None:
        d = direction.upper()
        self._write("ENTRY", (
            f"{d:5} {symbol} @ {price:,.2f} | "
            f"size=${size_usd:,.2f} | SL={sl:,.2f} TP={tp:,.2f} | ATR={atr:.2f}"
        ), _GREEN)

    def exit(self, direction: str, symbol: str, price: float,
             reason: str, pnl: float, pnl_pct: float) -> None:
        colour = _GREEN if pnl >= 0 else _RED
        sign   = "+" if pnl >= 0 else ""
        self._write("EXIT", (
            f"{direction.upper():5} {symbol} @ {price:,.2f} | "
            f"reason={reason:<12} pnl={sign}${pnl:,.2f} ({sign}{pnl_pct:.2f}%)"
        ), colour)

    def pnl(self, realized: float, unrealized: float, equity: float) -> None:
        self._write("PNL", (
            f"realized={'+' if realized>=0 else ''}{realized:,.4f}  "
            f"unrealized={'+' if unrealized>=0 else ''}{unrealized:,.4f}  "
            f"equity=${equity:,.2f}"
        ), _CYAN)

    def equity(self, equity: float, daily_pnl: float, daily_pct: float) -> None:
        sign = "+" if daily_pnl >= 0 else ""
        colour = _GREEN if daily_pnl >= 0 else _RED
        self._write("EQUITY", (
            f"${equity:,.2f}  daily={sign}${daily_pnl:,.2f} ({sign}{daily_pct:.2f}%)"
        ), colour)

    def signal(self, direction: str | None, reason: str) -> None:
        if direction:
            self._write("SIGNAL", f"{direction.upper():5} — {reason}", _YELLOW)
        else:
            self._write("SIGNAL", f"NONE  — {reason}", _DIM)

    def skip(self, reason: str) -> None:
        self._write("SKIP", reason, _DIM)

    def info(self, msg: str) -> None:
        self._write("INFO", msg)

    def error(self, msg: str) -> None:
        self._write("ERROR", msg, _RED)

    def state_snapshot(self, bar: int, price: float, rsi: float,
                       ema_f: float, ema_s: float, atr_pct: float,
                       position: str, bars_since_exit: int) -> None:
        pos_tag = position if position else "FLAT"
        self._write("SNAP", (
            f"bar={bar:>6} price={price:,.2f} RSI={rsi:.1f} "
            f"EMAf={ema_f:.2f} EMAs={ema_s:.2f} "
            f"ATR%={atr_pct*100:.3f}% pos={pos_tag:<6} bse={bars_since_exit}"
        ), _DIM)

    def close(self) -> None:
        self._file.close()


log = QuantLogger()
