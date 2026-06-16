"""
replay.py — Replay snapshots stored during live scan sessions.

Mode 1 (default): The scanner is already collecting snapshots every cycle.
  This module reads them back and replays the signal logic to show what
  would have been traded historically.

IMPORTANT limitation: paper fills in replay are more optimistic than live.
Replay cannot simulate fill rejection or mid-market moves during entry.
Label all replay results clearly as SIMULATED.
"""

from __future__ import annotations
import datetime
import json
import logging
import time

import storage
import fair_value as fv

log = logging.getLogger(__name__)


def replay_snapshots(conn, cfg: dict, since_ts: float | None = None) -> None:
    """
    Replay stored snapshots and print what signals would have fired.
    Does NOT create new DB records — read-only analysis.
    """
    log.info("=" * 65)
    log.info("  REPLAY MODE — SIMULATED (no live fills)")
    log.info("  WARNING: Results are optimistic. Paper fills assumed at ask.")
    log.info("=" * 65)

    if since_ts is None:
        # Default: last 24h
        since_ts = time.time() - 86400

    snaps = conn.execute("""
        SELECT s.*, m.symbol, m.market_type, m.direction, m.target_price,
               m.expiry_ts, m.question
        FROM snapshots s
        JOIN markets m ON m.condition_id = s.condition_id
        WHERE s.ts >= ?
        ORDER BY s.ts ASC
    """, (since_ts,)).fetchall()

    log.info(f"  Loaded {len(snaps)} snapshots since "
             f"{datetime.datetime.utcfromtimestamp(since_ts).strftime('%Y-%m-%d %H:%M')}")

    if not snaps:
        log.info("  No snapshot data. Run the scanner first to collect data.")
        return

    signals = 0
    would_trade = 0
    min_edge = cfg.get("min_edge_pct", 0.04)

    for row in snaps:
        snap = dict(row)
        ts        = snap.get("ts", 0)
        expiry_ts = snap.get("expiry_ts")
        if not expiry_ts or ts >= expiry_ts:
            continue

        # Reconstruct fair value
        fv_result = fv.compute_fair_value(
            market_type       = snap.get("market_type", "directional"),
            direction         = snap.get("direction"),
            target_price      = snap.get("target_price"),
            current_price     = snap.get("ref_price") or 0,
            expiry_ts         = expiry_ts,
            now_ts            = ts,
            vol_annual        = snap.get("vol_annual"),
            n_vol_samples     = 20,   # assume adequate in replay
            momentum_pct_per_min = snap.get("momentum") or 0,
            ref_price_age     = snap.get("ref_price_age") or 5,
            ob_age            = 0,    # already in the snapshot
            cfg               = cfg,
        )

        for outcome, exec_price in [
            ("YES", snap.get("yes_ask")),
            ("NO",  snap.get("no_ask")),
        ]:
            if not exec_price or exec_price <= 0:
                continue

            fair_p = fv_result.yes_prob if outcome == "YES" else fv_result.no_prob
            spread = snap.get("spread") or 0.05
            edge_r = fv.compute_edge(fair_p, exec_price, spread, cfg)
            adj_e  = edge_r.get("adjusted_edge", 0)

            signals += 1
            if adj_e >= min_edge and fv_result.confidence >= cfg.get("min_fair_value_confidence", 0.55):
                would_trade += 1
                ts_str = datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
                log.info(
                    f"  [WOULD TRADE] {ts_str} | {outcome} | "
                    f"{snap.get('question','')[:55]} | "
                    f"adj_edge={adj_e*100:+.2f}% conf={fv_result.confidence:.2f}"
                )
            break  # one outcome per snapshot for readability

    log.info(f"\n  Total snapshots : {len(snaps)}")
    log.info(f"  Signals evaluated: {signals}")
    log.info(f"  Would have traded: {would_trade}")
    log.info(f"  Signal rate       : {would_trade/max(signals,1)*100:.1f}%")
    log.info("")
    log.info("  NOTE: To evaluate profitability you need at least 2 weeks of")
    log.info("  live paper trading data. Replay alone cannot prove edge.")


def print_trade_stats(conn) -> None:
    """Print summary of all closed paper trades from the database."""
    trades = storage.get_closed_trades(conn)

    log.info("=" * 65)
    log.info(f"  PAPER TRADE SUMMARY ({len(trades)} closed trades)")
    log.info("=" * 65)

    if not trades:
        log.info("  No closed paper trades yet.")
        return

    wins   = [t for t in trades if (t.get("pnl") or 0) > 0]
    losses = [t for t in trades if (t.get("pnl") or 0) <= 0]
    total  = sum(t.get("pnl") or 0 for t in trades)
    g_win  = sum(t.get("pnl") or 0 for t in wins)
    g_loss = abs(sum(t.get("pnl") or 0 for t in losses))

    win_rate = len(wins) / len(trades) * 100
    avg_win  = g_win / len(wins) if wins else 0
    avg_loss = g_loss / len(losses) if losses else 0
    pf       = g_win / g_loss if g_loss > 0 else float("inf")

    holds = [t.get("hold_seconds") or 0 for t in trades]
    avg_hold = sum(holds) / len(holds) / 60 if holds else 0

    edges = [t.get("edge_entry") or 0 for t in trades]
    avg_edge = sum(edges) / len(edges) * 100 if edges else 0

    log.info(f"  Win rate      : {win_rate:.1f}%")
    log.info(f"  Avg win       : ${avg_win:+.2f}")
    log.info(f"  Avg loss      : -${avg_loss:.2f}")
    log.info(f"  Profit factor : {pf:.2f}")
    log.info(f"  Total PnL     : ${total:+.2f}")
    log.info(f"  Avg hold time : {avg_hold:.1f} min")
    log.info(f"  Avg edge      : {avg_edge:.2f}%")
    log.info("")

    # Exit reason breakdown
    reasons: dict[str, list] = {}
    for t in trades:
        r = t.get("exit_reason") or "unknown"
        reasons.setdefault(r, []).append(t.get("pnl") or 0)
    log.info("  By exit reason:")
    for r, ps in sorted(reasons.items()):
        wr = sum(1 for p in ps if p > 0) / len(ps) * 100
        log.info(f"    {r:<25} : {len(ps):>4} trades  wr={wr:.0f}%  net=${sum(ps):+.2f}")

    log.info("=" * 65)

    # Print individual trades
    log.info("\n  Individual trades:")
    hdr = f"  {'#':>4}  {'Outcome':6}  {'Entry':>8}  {'Exit':>8}  {'PnL':>8}  {'Exit reason':<22}  {'Question'}"
    log.info(hdr)
    log.info("  " + "-" * 100)
    for i, t in enumerate(trades, 1):
        sign = "+" if (t.get("pnl") or 0) >= 0 else ""
        log.info(
            f"  {i:>4}  {t.get('outcome','?'):6}  "
            f"{t.get('entry_price',0):.4f}   {t.get('exit_price',0):.4f}   "
            f"{sign}${t.get('pnl',0):.2f}   "
            f"{(t.get('exit_reason') or 'unknown'):<22}  "
            f"{(t.get('question') or '')[:45]}"
        )
