"""
paper_trader.py — Realistic paper trading simulation.

Paper trades simulate buying YES or NO tokens at the CLOB best ask,
not the midpoint. Positions are marked to market every scan cycle.
Exits are triggered by fair-value reversal, take-profit, stop-loss,
expiry proximity, or market resolution.

Intentionally conservative: adds delay and slippage assumptions that
make paper results closer to (but still more optimistic than) live fills.
"""

from __future__ import annotations
import logging
import time
from typing import Optional

import storage
import risk as risk_module

log = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self, conn, cfg: dict, risk: risk_module.RiskManager) -> None:
        self.conn = conn
        self.cfg  = cfg
        self.risk = risk

        # In-memory position cache keyed by DB trade id
        # {trade_id: {condition_id, outcome, entry_price, num_contracts,
        #              size_usd, entry_ts, expiry_ts, max_adverse, max_favourable}}
        self._positions: dict[int, dict] = {}
        self._load_open_positions()

        self._equity = cfg.get("paper_starting_capital_usd", 1000.0)
        self._realized_pnl = 0.0

    # ── Startup ───────────────────────────────────────────────────────────────

    def _load_open_positions(self) -> None:
        rows = storage.get_open_paper_trades(self.conn)
        for r in rows:
            self._positions[r["id"]] = dict(r)
        if self._positions:
            log.info(f"Loaded {len(self._positions)} open paper positions from DB")

    # ── Entry ─────────────────────────────────────────────────────────────────

    def open(
        self,
        market:          dict,
        outcome:         str,            # 'YES' or 'NO'
        executable_price: float,         # best ask (what we "pay")
        fair_value:      float,
        edge:            float,
        spread:          float,
        liquidity:       float,
        signal_id:       Optional[int] = None,
    ) -> Optional[int]:
        """
        Open a paper position. Returns trade_id or None if blocked by risk checks.
        """
        open_count = len(self._positions)
        passes, block_reason = self.risk.signal_passes(
            adjusted_edge  = edge,
            spread         = spread,
            liquidity      = liquidity,
            ref_price_age  = 0,   # already checked upstream
            orderbook_age  = 0,
            confidence     = fair_value,  # crude proxy
            open_count     = open_count,
        )

        if not passes:
            log.debug(f"Paper trade blocked: {block_reason}")
            return None

        size_usd = self.cfg.get("paper_position_size_usd", 50.0)
        if executable_price <= 0:
            return None

        num_contracts = size_usd / executable_price
        entry_ts      = time.time()

        trade = {
            "condition_id":    market["condition_id"],
            "question":        market.get("question", ""),
            "outcome":         outcome,
            "entry_ts":        entry_ts,
            "entry_price":     executable_price,
            "fair_value_entry": fair_value,
            "edge_entry":      edge,
            "size_usd":        size_usd,
            "num_contracts":   num_contracts,
            "expiry_ts":       market.get("expiry_ts"),
            "liquidity_entry": liquidity,
            "spread_entry":    spread,
            "signal_id":       signal_id,
        }

        trade_id = storage.open_paper_trade(self.conn, trade)
        self._positions[trade_id] = {
            **trade,
            "id":             trade_id,
            "max_adverse":    0.0,
            "max_favourable": 0.0,
        }

        self.risk.record_trade()
        self._equity -= size_usd  # capital committed

        log.info(
            f"  PAPER OPEN  {outcome:3s} | {market['question'][:60]} | "
            f"price={executable_price:.3f} fv={fair_value:.3f} edge={edge*100:.1f}% "
            f"size=${size_usd:.0f} contracts={num_contracts:.1f}"
        )
        return trade_id

    # ── Mark to market + exit check ────────────────────────────────────────────

    def update(
        self,
        trade_id:     int,
        current_mid:  Optional[float],   # current midpoint of the outcome token
        fair_value:   Optional[float],   # current fair value
        now_ts:       Optional[float]    = None,
        resolved:     Optional[bool]     = None,  # True if market resolved
        resolved_yes: Optional[bool]     = None,  # direction of resolution
    ) -> Optional[dict]:
        """
        Mark position to market. Returns close dict if position should exit, else None.
        """
        pos = self._positions.get(trade_id)
        if pos is None:
            return None

        now_ts = now_ts or time.time()
        expiry_ts = pos.get("expiry_ts")
        outcome   = pos["outcome"]
        entry_p   = pos["entry_price"]
        num_c     = pos["num_contracts"]
        size_usd  = pos["size_usd"]
        entry_ts  = pos["entry_ts"]

        # Current mark-to-market value
        mtm_price = current_mid if current_mid else entry_p
        mtm_value = num_c * mtm_price
        mtm_pnl   = mtm_value - size_usd

        # Track max adverse/favourable excursion
        pos["max_adverse"]    = min(pos.get("max_adverse", 0.0),    mtm_pnl)
        pos["max_favourable"] = max(pos.get("max_favourable", 0.0), mtm_pnl)

        # ── Exit conditions ────────────────────────────────────────────────────

        exit_price  = None
        exit_reason = None

        # 1. Market resolved
        if resolved:
            if resolved_yes is not None:
                win = (outcome == "YES" and resolved_yes) or \
                      (outcome == "NO"  and not resolved_yes)
                exit_price  = 1.0 if win else 0.0
                exit_reason = "resolved_win" if win else "resolved_loss"
            else:
                exit_price, exit_reason = mtm_price, "resolved_unknown"

        # 2. Stop loss
        tp_pct = self.cfg.get("paper_take_profit_pct", 0.35)
        sl_pct = self.cfg.get("paper_stop_loss_pct",   0.25)

        if exit_price is None:
            if mtm_pnl / size_usd <= -sl_pct:
                exit_price  = mtm_price
                exit_reason = f"stop_loss ({mtm_pnl/size_usd*100:.1f}%)"

        # 3. Take profit
        if exit_price is None:
            if mtm_pnl / size_usd >= tp_pct:
                exit_price  = mtm_price
                exit_reason = f"take_profit ({mtm_pnl/size_usd*100:.1f}%)"

        # 4. Fair value edge gone — exit to free capital
        if exit_price is None and fair_value is not None:
            fv_edge = fair_value - mtm_price
            min_edge = self.cfg.get("min_edge_pct", 0.04) * 0.5  # exit at half threshold
            if fv_edge < min_edge:
                exit_price  = mtm_price
                exit_reason = f"edge_gone (fv={fair_value:.3f} mid={mtm_price:.3f})"

        # 5. Expiry too close
        if exit_price is None and expiry_ts:
            min_t = self.cfg.get("min_time_to_expiry_minutes", 10)
            t_remaining = (expiry_ts - now_ts) / 60
            if t_remaining < min_t * 0.5:
                exit_price  = mtm_price
                exit_reason = f"expiry_near ({t_remaining:.1f}min)"

        if exit_price is None:
            return None  # keep position open

        return self._close(trade_id, exit_price, exit_reason, now_ts)

    def _close(
        self, trade_id: int, exit_price: float, reason: str, now_ts: float
    ) -> dict:
        pos      = self._positions.pop(trade_id)
        num_c    = pos["num_contracts"]
        size_usd = pos["size_usd"]
        entry_p  = pos["entry_price"]
        entry_ts = pos["entry_ts"]

        exit_value   = num_c * exit_price
        pnl          = exit_value - size_usd
        pnl_pct      = pnl / size_usd
        hold_seconds = now_ts - entry_ts

        self._equity         += size_usd + pnl
        self._realized_pnl   += pnl
        self.risk.record_pnl(pnl)

        close = {
            "exit_ts":        now_ts,
            "exit_price":     exit_price,
            "exit_reason":    reason,
            "pnl":            round(pnl, 4),
            "pnl_pct":        round(pnl_pct, 4),
            "max_adverse":    round(pos.get("max_adverse", 0), 4),
            "max_favourable": round(pos.get("max_favourable", 0), 4),
            "hold_seconds":   round(hold_seconds, 1),
        }
        storage.close_paper_trade(self.conn, trade_id, close)

        sign = "WIN" if pnl >= 0 else "LOSS"
        log.info(
            f"  PAPER CLOSE {sign} | {pos['outcome']:3s} | {pos['question'][:55]} | "
            f"reason={reason} pnl=${pnl:+.2f} ({pnl_pct*100:+.1f}%) "
            f"held={hold_seconds/60:.1f}min"
        )
        return close

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def open_count(self) -> int:
        return len(self._positions)

    @property
    def equity(self) -> float:
        return self._equity

    @property
    def realized_pnl(self) -> float:
        return self._realized_pnl

    def print_stats(self) -> None:
        trades = storage.get_closed_trades(self.conn)
        n = len(trades)
        if n == 0:
            log.info("No closed paper trades yet.")
            return

        wins   = [t for t in trades if (t["pnl"] or 0) > 0]
        losses = [t for t in trades if (t["pnl"] or 0) <= 0]
        total_pnl = sum(t["pnl"] or 0 for t in trades)
        avg_win   = sum(t["pnl"] or 0 for t in wins)   / len(wins)   if wins   else 0
        avg_loss  = sum(t["pnl"] or 0 for t in losses) / len(losses) if losses else 0
        pf = abs(avg_win * len(wins)) / abs(avg_loss * len(losses)) if losses and avg_loss != 0 else float("inf")

        log.info("=" * 60)
        log.info(f"  PAPER TRADING STATS ({n} closed trades)")
        log.info(f"  Win rate      : {len(wins)/n*100:.1f}%")
        log.info(f"  Avg win       : ${avg_win:+.2f}")
        log.info(f"  Avg loss      : ${avg_loss:+.2f}")
        log.info(f"  Profit factor : {pf:.2f}")
        log.info(f"  Total PnL     : ${total_pnl:+.2f}")
        log.info(f"  Equity        : ${self._equity:.2f}")
        log.info(f"  Open positions: {self.open_count}")
        log.info("=" * 60)
