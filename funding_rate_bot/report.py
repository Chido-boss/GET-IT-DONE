"""
Standalone performance report for the Funding Rate Arbitrage Bot.

Usage:
    python report.py           # Full report from default DB
    python report.py --days 7  # Limit daily history to N days
    python report.py --json    # Machine-readable JSON output
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from the funding_rate_bot/ directory or the repo root
_HERE = Path(__file__).parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import aiosqlite
from config import cfg


# ─── helpers ──────────────────────────────────────────────────────────────────

def _age_str(entry_time_str: str) -> str:
    try:
        dt = datetime.fromisoformat(entry_time_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((datetime.now(timezone.utc) - dt).total_seconds())
        if secs < 3600:
            return f"{secs // 60}m"
        if secs < 86400:
            return f"{secs // 3600}h {(secs % 3600) // 60}m"
        return f"{secs // 86400}d {(secs % 86400) // 3600}h"
    except Exception:
        return "?"


def _bar(value: float, max_val: float, width: int = 20) -> str:
    if max_val <= 0:
        return " " * width
    filled = int(min(value / max_val, 1.0) * width)
    return "█" * filled + "░" * (width - filled)


# ─── core queries ─────────────────────────────────────────────────────────────

async def _build_report(db_path: str, days: int = 30) -> dict:
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row

        async def q(sql, params=()):
            cur = await conn.execute(sql, params)
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

        async def q1(sql, params=()):
            cur = await conn.execute(sql, params)
            row = await cur.fetchone()
            return dict(row) if row else {}

        # All-time totals
        totals = await q1("""
            SELECT
                COALESCE(SUM(total_funding_collected), 0) AS all_time_funding,
                COUNT(*) AS total_positions,
                COUNT(CASE WHEN status='open' THEN 1 END) AS open_count,
                COUNT(CASE WHEN status='closed' THEN 1 END) AS closed_count,
                COALESCE(SUM(CASE WHEN status='closed' THEN total_funding_collected ELSE 0 END), 0) AS closed_funding
            FROM positions
        """)

        # Open positions detail
        open_pos = await q("""
            SELECT p.*,
                   COALESCE(fp_sum.total, 0) AS confirmed_collected
            FROM positions p
            LEFT JOIN (
                SELECT position_id, SUM(payment_amount) AS total
                FROM funding_payments
                GROUP BY position_id
            ) fp_sum ON fp_sum.position_id = p.id
            WHERE p.status = 'open'
            ORDER BY p.entry_time ASC
        """)

        # Closed positions summary
        closed_pos = await q("""
            SELECT symbol, entry_funding_rate, total_funding_collected,
                   entry_time, exit_time, close_reason,
                   spot_size * entry_spot_price AS notional_usdc
            FROM positions
            WHERE status = 'closed'
            ORDER BY exit_time DESC
            LIMIT 10
        """)

        # Daily stats
        daily = await q(f"""
            SELECT *
            FROM daily_stats
            ORDER BY date DESC
            LIMIT {days}
        """)

        # Recent payments
        payments = await q("""
            SELECT fp.timestamp, fp.payment_amount, fp.funding_rate, p.symbol
            FROM funding_payments fp
            JOIN positions p ON fp.position_id = p.id
            ORDER BY fp.timestamp DESC
            LIMIT 15
        """)

        # Projected annual yield from open positions
        proj_annual = 0.0
        for pos in open_pos:
            notional = pos["spot_size"] * pos["entry_spot_price"]
            proj_annual += notional * pos["entry_funding_rate"] * 1095  # 3/day * 365

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_path": db_path,
            "paper_mode": bool(cfg.paper_mode),
            "starting_balance": cfg.paper_starting_balance if cfg.paper_mode else None,
            "totals": totals,
            "open_positions": open_pos,
            "closed_positions": closed_pos,
            "daily_stats": daily,
            "recent_payments": payments,
            "projected_annual_yield": proj_annual,
        }


# ─── formatters ───────────────────────────────────────────────────────────────

def _print_report(report: dict) -> None:
    try:
        from rich.console import Console
        from rich.table import Table
        from rich import box
        from rich.panel import Panel
        from rich.text import Text
        _rich_print(report, Console())
    except ImportError:
        _plain_print(report)


def _rich_print(report: dict, console) -> None:
    from rich.table import Table
    from rich import box
    from rich.panel import Panel

    totals = report["totals"]
    open_pos = report["open_positions"]
    daily = report["daily_stats"]
    payments = report["recent_payments"]

    mode_tag = "[bold red]LIVE[/bold red]" if not report["paper_mode"] else "[bold cyan]PAPER[/bold cyan]"
    console.print()
    console.rule(f"[bold white]  FUNDING RATE BOT — PERFORMANCE REPORT  {mode_tag}  ")
    console.print(f"[dim]  Generated: {report['generated_at']}[/dim]")
    console.print()

    # ── Summary ──
    all_time = totals.get("all_time_funding", 0.0)
    start_bal = report.get("starting_balance") or 0.0
    pct = (all_time / start_bal * 100) if start_bal > 0 else 0.0
    proj = report["projected_annual_yield"]

    summary = Table(box=None, show_header=False, padding=(0, 2))
    summary.add_column("K", style="dim", width=28)
    summary.add_column("V", width=30)

    if report["paper_mode"] and start_bal:
        summary.add_row("Starting Balance", f"${start_bal:,.2f}")
        summary.add_row("Simulated Balance", f"[bold]${start_bal + all_time:,.2f}[/bold]")
    pnl_style = "green" if all_time >= 0 else "red"
    sign = "+" if all_time >= 0 else ""
    summary.add_row("All-time Funding Collected", f"[{pnl_style}]{sign}${all_time:,.4f} ({sign}{pct:.2f}%)[/{pnl_style}]")
    summary.add_row("Projected Annual Yield", f"[yellow]${proj:,.2f}[/yellow]")
    summary.add_row("Total Positions", str(totals.get("total_positions", 0)))
    summary.add_row("  ↳ Open", str(totals.get("open_count", 0)))
    summary.add_row("  ↳ Closed", str(totals.get("closed_count", 0)))
    console.print(Panel(summary, title="[bold]Portfolio Summary[/bold]", border_style="blue"))

    # ── Open Positions ──
    if open_pos:
        t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan", expand=True)
        t.add_column("Symbol", width=8)
        t.add_column("Exchange", width=8)
        t.add_column("Notional", width=12)
        t.add_column("Rate/8h", width=10)
        t.add_column("APY", width=8)
        t.add_column("Collected", width=12)
        t.add_column("Age", width=8)

        max_collected = max((p["total_funding_collected"] for p in open_pos), default=1) or 1
        for pos in open_pos:
            notional = pos["spot_size"] * pos["entry_spot_price"]
            apy = pos["entry_funding_rate"] * 1095 * 100
            collected = pos["total_funding_collected"]
            bar = _bar(collected, max_collected, 8)
            t.add_row(
                f"[bold]{pos['symbol']}[/bold]",
                pos["exchange_perp"],
                f"${notional:,.2f}",
                f"{pos['entry_funding_rate'] * 100:.4f}%",
                f"[green]{apy:.1f}%[/green]",
                f"[cyan]{bar}[/cyan] ${collected:.4f}",
                _age_str(pos["entry_time"]),
            )
        console.print(Panel(t, title=f"[bold]Open Positions ({len(open_pos)})[/bold]", border_style="blue"))
    else:
        console.print(Panel("[dim]No open positions.[/dim]", title="[bold]Open Positions[/bold]", border_style="dim"))

    # ── Daily Stats ──
    if daily:
        t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan", expand=True)
        t.add_column("Date", width=12)
        t.add_column("Funding Collected", width=20)
        t.add_column("Opened", width=8)
        t.add_column("Closed", width=8)
        t.add_column("Net P&L", width=14)

        max_funding = max((d["total_funding_collected"] for d in daily), default=1) or 1
        for d in daily:
            f = d["total_funding_collected"]
            bar = _bar(f, max_funding, 10)
            pnl = d["net_pnl"]
            pnl_style = "green" if pnl >= 0 else "red"
            t.add_row(
                d["date"],
                f"[cyan]{bar}[/cyan] ${f:.4f}",
                str(d["positions_opened"]),
                str(d["positions_closed"]),
                f"[{pnl_style}]{'+' if pnl >= 0 else ''}${pnl:.4f}[/{pnl_style}]",
            )
        console.print(Panel(t, title="[bold]Daily Stats[/bold]", border_style="blue"))

    # ── Recent Payments ──
    if payments:
        t = Table(box=box.SIMPLE_HEAD, show_header=True, header_style="bold cyan", expand=True)
        t.add_column("Time (UTC)", width=22)
        t.add_column("Symbol", width=8)
        t.add_column("Payment", width=12)
        t.add_column("Rate/8h", width=10)

        for p in payments:
            ts = p["timestamp"][:19].replace("T", " ")
            t.add_row(
                ts,
                f"[bold]{p['symbol']}[/bold]",
                f"[green]+${p['payment_amount']:.4f}[/green]",
                f"{p['funding_rate'] * 100:.4f}%",
            )
        console.print(Panel(t, title="[bold]Recent Funding Payments[/bold]", border_style="blue"))

    console.print()


def _plain_print(report: dict) -> None:
    """Fallback plain-text output if Rich is not available."""
    totals = report["totals"]
    print("\n" + "=" * 60)
    print("  FUNDING RATE BOT — PERFORMANCE REPORT")
    print(f"  {report['generated_at']}")
    print("=" * 60)

    all_time = totals.get("all_time_funding", 0.0)
    start_bal = report.get("starting_balance") or 0.0
    pct = (all_time / start_bal * 100) if start_bal > 0 else 0.0
    if report["paper_mode"] and start_bal:
        print(f"\n  Starting Balance:      ${start_bal:,.2f}")
        print(f"  Simulated Balance:     ${start_bal + all_time:,.2f}")
    print(f"  All-time Funding:      ${all_time:,.4f} ({pct:+.2f}%)")
    print(f"  Projected Annual:      ${report['projected_annual_yield']:,.2f}")
    print(f"  Positions Open/Closed: {totals.get('open_count',0)} / {totals.get('closed_count',0)}")

    print("\n  OPEN POSITIONS")
    for pos in report["open_positions"]:
        notional = pos["spot_size"] * pos["entry_spot_price"]
        apy = pos["entry_funding_rate"] * 1095 * 100
        print(
            f"    {pos['symbol']:8s}  ${notional:8.2f}  "
            f"{pos['entry_funding_rate']*100:.4f}%/8h  {apy:.1f}% APY  "
            f"collected=${pos['total_funding_collected']:.4f}  age={_age_str(pos['entry_time'])}"
        )

    print("\n  DAILY STATS")
    for d in report["daily_stats"]:
        print(
            f"    {d['date']}  funding=${d['total_funding_collected']:.4f}  "
            f"opened={d['positions_opened']}  closed={d['positions_closed']}  "
            f"pnl={d['net_pnl']:+.4f}"
        )

    print("\n  RECENT PAYMENTS")
    for p in report["recent_payments"]:
        ts = p["timestamp"][:19].replace("T", " ")
        print(f"    {ts}  {p['symbol']:8s}  +${p['payment_amount']:.4f}  rate={p['funding_rate']*100:.4f}%")
    print()


# ─── entry point ──────────────────────────────────────────────────────────────

async def _run(days: int, as_json: bool) -> None:
    db_path = cfg.db_file
    if not Path(db_path).exists():
        print(f"[ERROR] Database not found at {db_path}")
        print("Make sure the bot has run at least once to create the database.")
        sys.exit(1)

    report = await _build_report(db_path, days=days)

    if as_json:
        # Remove non-serialisable items
        print(json.dumps(report, indent=2, default=str))
    else:
        _print_report(report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Funding Rate Bot — Performance Report")
    parser.add_argument("--days", type=int, default=30, help="Days of daily stats to show (default: 30)")
    parser.add_argument("--json", action="store_true", dest="as_json", help="Output raw JSON")
    args = parser.parse_args()
    asyncio.run(_run(args.days, args.as_json))


if __name__ == "__main__":
    main()
