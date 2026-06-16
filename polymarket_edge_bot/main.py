"""
main.py — CLI entry point.

Commands:
  python main.py scan          scan continuously (default)
  python main.py scan --once   single scan cycle and exit
  python main.py markets       list active crypto Up/Down markets only
  python main.py stats         print paper trading statistics
  python main.py replay        replay stored snapshots

All output goes to stdout and logs/<date>.log simultaneously.
"""

from __future__ import annotations
import argparse
import datetime
import json
import logging
import os
import sys
from pathlib import Path


# ── Config loading ────────────────────────────────────────────────────────────

def load_config(path: str = "config.json") -> dict:
    cfg_path = Path(path)
    if not cfg_path.exists():
        example = Path("config.example.json")
        if example.exists():
            print(f"[INFO] {path} not found — using config.example.json defaults")
            cfg_path = example
        else:
            print("[WARN] No config file found — using hardcoded defaults")
            return _default_config()

    with cfg_path.open() as f:
        raw = f.read()

    # Strip single-line comments (// ...) before parsing — JSON doesn't allow them
    import re
    raw = re.sub(r'//[^\n]*', '', raw)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"[ERROR] Config parse error: {exc}")
        sys.exit(1)


def _default_config() -> dict:
    return {
        "polling_interval_seconds": 30,
        "max_markets_per_scan": 100,
        "symbols": ["BTC", "ETH", "SOL"],
        "min_liquidity_usd": 500,
        "max_spread": 0.08,
        "min_time_to_expiry_minutes": 10,
        "max_time_to_expiry_hours": 72,
        "max_ref_price_age_seconds": 30,
        "max_orderbook_age_seconds": 60,
        "min_edge_pct": 0.04,
        "min_fair_value_confidence": 0.55,
        "delay_penalty_pct": 0.010,
        "slippage_pct": 0.005,
        "safety_margin_pct": 0.010,
        "paper_starting_capital_usd": 1000.0,
        "paper_position_size_usd": 50.0,
        "paper_take_profit_pct": 0.35,
        "paper_stop_loss_pct": 0.25,
        "max_trades_per_hour": 20,
        "max_concurrent_positions": 5,
        "max_daily_loss_usd": 200.0,
        "cooldown_after_loss_minutes": 5,
        "vol_window_minutes": 15,
        "vol_min_samples": 8,
        "momentum_window_seconds": 180,
        "reference_exchanges": ["kraken", "binance", "coinbase"],
        "save_raw_samples": True,
        "log_level": "INFO",
        "db_path": "data/edge_bot.db",
        "log_dir": "logs",
    }


# ── Logging setup ─────────────────────────────────────────────────────────────

def setup_logging(cfg: dict) -> None:
    log_dir  = Path(cfg.get("log_dir", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    date_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    log_file = log_dir / f"{date_str}.log"

    level = getattr(logging, cfg.get("log_level", "INFO").upper(), logging.INFO)

    fmt = logging.Formatter(
        fmt     = "%(asctime)s %(levelname)-7s %(message)s",
        datefmt = "%H:%M:%S",
    )
    root = logging.getLogger()
    root.setLevel(level)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(fmt)
    root.addHandler(ch)

    # File handler
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)

    logging.info(f"Logging to {log_file}")


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_scan(cfg: dict, once: bool = False) -> None:
    import storage
    import scanner as sc

    conn = storage.connect(cfg.get("db_path", "data/edge_bot.db"))
    engine = sc.Scanner(conn, cfg)
    engine.run(once=once)


def cmd_markets(cfg: dict) -> None:
    """List active crypto Up/Down markets without trading."""
    import polymarket_client as pm

    symbols = cfg.get("symbols", ["BTC", "ETH", "SOL"])
    raw     = pm.get_active_markets(limit=cfg.get("max_markets_per_scan", 100))

    print(f"\nFetched {len(raw)} markets — filtering for {symbols}...\n")
    found = 0
    for r in raw:
        m = pm.parse_market(r, target_symbols=symbols)
        if not m:
            continue
        found += 1
        expiry = m.get("expiry_ts")
        exp_str = datetime.datetime.utcfromtimestamp(expiry).strftime("%Y-%m-%d %H:%M") if expiry else "?"
        yes_p = m.get("yes_mid_gamma")
        no_p  = m.get("no_mid_gamma")
        print(
            f"  [{m['symbol']:3s}] {m['market_type'][:8]:8s}  "
            f"target=${m['target_price']:>10.2f}  "
            f"YES={yes_p:.3f}  NO={no_p:.3f}  "
            f"liq=${m['liquidity']:>8,.0f}  "
            f"expiry={exp_str}"
            if m.get("target_price") and yes_p and no_p
            else f"  [{m['symbol']:3s}] {m['question'][:70]}"
        )

    print(f"\n  Total: {found} crypto Up/Down markets\n")


def cmd_stats(cfg: dict) -> None:
    import storage
    import replay

    conn = storage.connect(cfg.get("db_path", "data/edge_bot.db"))
    replay.print_trade_stats(conn)


def cmd_replay(cfg: dict, hours: int = 24) -> None:
    import storage
    import replay
    import time

    conn = storage.connect(cfg.get("db_path", "data/edge_bot.db"))
    since = time.time() - hours * 3600
    replay.replay_snapshots(conn, cfg, since_ts=since)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Polymarket Edge Bot — paper trading scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  scan          Run continuous market scan + paper trading (default)
  markets       List active crypto Up/Down markets only
  stats         Show paper trading statistics
  replay        Replay stored snapshots

Examples:
  python main.py scan
  python main.py scan --once
  python main.py scan --config config.json
  python main.py markets
  python main.py stats
  python main.py replay --hours 48
        """,
    )

    parser.add_argument("command", nargs="?", default="scan",
                        choices=["scan", "markets", "stats", "replay"],
                        help="Sub-command to run")
    parser.add_argument("--config",  default="config.json",
                        help="Path to config file (default: config.json)")
    parser.add_argument("--once",    action="store_true",
                        help="Run a single scan cycle and exit")
    parser.add_argument("--hours",   type=int, default=24,
                        help="Hours of history for replay command")
    parser.add_argument("--verbose", action="store_true",
                        help="Set log level to DEBUG")

    args = parser.parse_args()
    cfg  = load_config(args.config)

    if args.verbose:
        cfg["log_level"] = "DEBUG"

    setup_logging(cfg)
    logging.info(f"Polymarket Edge Bot — command={args.command}")

    # Ensure data directories exist
    Path(cfg.get("db_path", "data/edge_bot.db")).parent.mkdir(parents=True, exist_ok=True)
    Path("data/raw_samples").mkdir(parents=True, exist_ok=True)

    if args.command == "scan":
        cmd_scan(cfg, once=args.once)
    elif args.command == "markets":
        cmd_markets(cfg)
    elif args.command == "stats":
        cmd_stats(cfg)
    elif args.command == "replay":
        cmd_replay(cfg, hours=args.hours)


if __name__ == "__main__":
    main()
