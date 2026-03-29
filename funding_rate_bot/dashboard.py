"""
Rich terminal dashboard for the Funding Rate Arbitrage Bot.
Refreshes every 5 seconds. Designed to be driven by the bot's dashboard_task.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import cfg
from opportunity_scanner import FundingOpportunity

logger = logging.getLogger(__name__)

console = Console()

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

def _rate_color(rate: float) -> str:
    if rate >= 0.001:
        return "bright_green"
    if rate >= 0.0003:
        return "green"
    if rate >= 0.0001:
        return "yellow"
    return "red"


def _pnl_color(val: float) -> str:
    return "green" if val >= 0 else "red"


def _fmt_rate(rate: float) -> str:
    return f"{rate * 100:.4f}%"


def _fmt_apy(rate: float) -> str:
    return f"{rate * cfg.funding_periods_per_year * 100:.1f}%"


def _fmt_usdc(val: float) -> str:
    return f"${val:,.4f}"


def _time_until(iso_str: str | None) -> str:
    if not iso_str:
        return "—"
    try:
        target = datetime.fromisoformat(iso_str)
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        delta = target - datetime.now(timezone.utc)
        total_secs = int(delta.total_seconds())
        if total_secs < 0:
            return "now"
        h, rem = divmod(total_secs, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return "—"


def _age_str(iso_str: str) -> str:
    try:
        entry = datetime.fromisoformat(iso_str)
        if entry.tzinfo is None:
            entry = entry.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - entry
        total_secs = int(delta.total_seconds())
        d, rem = divmod(total_secs, 86400)
        h, rem2 = divmod(rem, 3600)
        m, _ = divmod(rem2, 60)
        if d > 0:
            return f"{d}d {h:02d}h"
        return f"{h:02d}h {m:02d}m"
    except (ValueError, TypeError):
        return "—"


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _build_header(
    mode: str,
    balance: float,
    uptime_secs: int,
    active_exchanges: list[str],
) -> Panel:
    h, rem = divmod(uptime_secs, 3600)
    m, s = divmod(rem, 60)
    uptime_str = f"{h:02d}:{m:02d}:{s:02d}"
    mode_text = Text(f"  {mode.upper()} MODE  ", style="bold white on red" if mode == "LIVE" else "bold white on blue")
    exchanges = " | ".join(e.upper() for e in active_exchanges) if active_exchanges else "NONE"

    t = Table.grid(padding=(0, 2))
    t.add_row(
        Text("⚡ FUNDING RATE ARB BOT", style="bold bright_cyan"),
        mode_text,
        Text(f"Uptime: {uptime_str}", style="dim"),
        Text(f"Balance: {_fmt_usdc(balance)}", style="bold bright_green"),
        Text(f"Exchanges: {exchanges}", style="dim"),
    )
    return Panel(t, style="bright_cyan")


def _build_opportunities_table(opportunities: list[FundingOpportunity]) -> Panel:
    table = Table(
        title=None,
        show_header=True,
        header_style="bold white",
        border_style="dim",
        expand=True,
    )
    table.add_column("Symbol", style="bold white", width=8)
    table.add_column("Perp Exch", width=8)
    table.add_column("Spot Exch", width=8)
    table.add_column("8h Rate", justify="right", width=10)
    table.add_column("Ann. APY", justify="right", width=10)
    table.add_column("Basis", justify="right", width=8)
    table.add_column("Next Payment", justify="right", width=14)
    table.add_column("Rec. Size", justify="right", width=10)
    table.add_column("Score", justify="right", width=7)

    for opp in opportunities[:5]:
        col = _rate_color(opp.funding_rate)
        table.add_row(
            opp.symbol,
            opp.perp_exchange.upper(),
            opp.spot_exchange.upper(),
            Text(_fmt_rate(opp.funding_rate), style=col),
            Text(_fmt_apy(opp.funding_rate), style=col),
            Text(f"{opp.basis_pct:+.3f}%", style="green" if opp.basis_pct <= 0 else "yellow"),
            _time_until(opp.next_funding_time),
            _fmt_usdc(opp.recommended_size_usdc),
            f"{opp.composite_score:.3f}",
        )

    if not opportunities:
        table.add_row("—", "—", "—", "—", "—", "—", "—", "—", "—")

    return Panel(table, title="[bold]Top Opportunities[/bold]", border_style="green")


def _build_positions_table(positions: list[dict[str, Any]], current_rates: dict[str, float]) -> Panel:
    table = Table(
        show_header=True,
        header_style="bold white",
        border_style="dim",
        expand=True,
    )
    table.add_column("Symbol", style="bold white", width=8)
    table.add_column("Exch (S/P)", width=12)
    table.add_column("Size USDC", justify="right", width=10)
    table.add_column("Entry Rate", justify="right", width=10)
    table.add_column("Curr Rate", justify="right", width=10)
    table.add_column("Funding Coll.", justify="right", width=13)
    table.add_column("Age", width=10)
    table.add_column("Below Thr.", justify="right", width=10)

    for pos in positions:
        symbol = pos.get("symbol", "?")
        curr_rate = current_rates.get(symbol, 0.0)
        entry_rate = pos.get("entry_funding_rate", 0.0)
        funding_coll = pos.get("total_funding_collected", 0.0)
        below_count = pos.get("below_threshold_count", 0)

        table.add_row(
            symbol,
            f"{pos.get('exchange_spot','?')[:4].upper()}/{pos.get('exchange_perp','?')[:4].upper()}",
            _fmt_usdc(pos.get("spot_size", 0.0) * pos.get("entry_spot_price", 0.0)),
            Text(_fmt_rate(entry_rate), style=_rate_color(entry_rate)),
            Text(_fmt_rate(curr_rate), style=_rate_color(curr_rate)),
            Text(_fmt_usdc(funding_coll), style="bright_green"),
            _age_str(pos.get("entry_time", "")),
            Text(
                f"{below_count}/{cfg.exit_consecutive_cycles}",
                style="yellow" if below_count > 0 else "dim",
            ),
        )

    if not positions:
        table.add_row("—", "—", "—", "—", "—", "—", "—", "—")

    return Panel(table, title="[bold]Open Positions[/bold]", border_style="cyan")


def _build_payments_table(recent_payments: list[dict[str, Any]]) -> Panel:
    table = Table(
        show_header=True,
        header_style="bold white",
        border_style="dim",
        expand=True,
    )
    table.add_column("Symbol", style="bold white", width=8)
    table.add_column("Exchange", width=8)
    table.add_column("Amount", justify="right", width=12)
    table.add_column("Rate", justify="right", width=10)
    table.add_column("Cumulative", justify="right", width=12)
    table.add_column("Time", width=22)

    for pmt in recent_payments[:10]:
        symbol = pmt.get("symbol", "?")
        exch = pmt.get("exchange_perp", "?")
        amount = pmt.get("payment_amount", 0.0)
        rate = pmt.get("funding_rate", 0.0)
        cumul = pmt.get("cumulative_total", 0.0)
        ts = pmt.get("timestamp", "")

        table.add_row(
            symbol,
            exch.upper(),
            Text(f"+{_fmt_usdc(amount)}", style="bright_green"),
            _fmt_rate(rate),
            _fmt_usdc(cumul),
            ts[:19].replace("T", " ") if ts else "—",
        )

    if not recent_payments:
        table.add_row("—", "—", "—", "—", "—", "—")

    return Panel(table, title="[bold]Recent Funding Payments[/bold]", border_style="yellow")


def _build_stats_panel(
    daily_stats: dict[str, Any],
    all_time_funding: float,
    risk_daily_pnl: float,
    open_count: int,
) -> Panel:
    t = Table.grid(padding=(0, 3))

    today_funding = daily_stats.get("total_funding_collected", 0.0)
    today_pnl = daily_stats.get("net_pnl", 0.0)
    pos_opened = daily_stats.get("positions_opened", 0)
    pos_closed = daily_stats.get("positions_closed", 0)

    t.add_row(
        Text("Today's Funding:", style="dim"),
        Text(_fmt_usdc(today_funding), style="bright_green"),
        Text("All-Time Funding:", style="dim"),
        Text(_fmt_usdc(all_time_funding), style="bright_green"),
    )
    t.add_row(
        Text("Today's Net P&L:", style="dim"),
        Text(_fmt_usdc(today_pnl), style=_pnl_color(today_pnl)),
        Text("Daily Loss P&L:", style="dim"),
        Text(_fmt_usdc(risk_daily_pnl), style=_pnl_color(risk_daily_pnl)),
    )
    t.add_row(
        Text("Opened Today:", style="dim"),
        Text(str(pos_opened), style="white"),
        Text("Closed Today:", style="dim"),
        Text(str(pos_closed), style="white"),
    )
    t.add_row(
        Text("Open Positions:", style="dim"),
        Text(str(open_count), style="bold white"),
        Text("Max Positions:", style="dim"),
        Text(str(cfg.max_total_positions), style="dim"),
    )

    return Panel(t, title="[bold]Statistics[/bold]", border_style="magenta")


def _build_system_panel(
    last_scan_time: str,
    api_statuses: dict[str, str],
    next_payments: list[tuple[str, str]],
    scan_interval: int,
) -> Panel:
    t = Table.grid(padding=(0, 2))

    t.add_row(
        Text("Last Scan:", style="dim"),
        Text(last_scan_time, style="white"),
        Text(f"Scan Interval: {scan_interval}s", style="dim"),
    )

    api_row_parts: list[Text] = [Text("API Status: ", style="dim")]
    for exch, status in api_statuses.items():
        color = "green" if status == "ok" else "red"
        api_row_parts.append(Text(f"{exch.upper()}:{status} ", style=color))
    t.add_row(*api_row_parts)

    if next_payments:
        payment_strs = [f"{sym}:{_time_until(ts)}" for sym, ts in next_payments[:4]]
        t.add_row(
            Text("Next Payments:", style="dim"),
            Text("  |  ".join(payment_strs), style="cyan"),
        )

    return Panel(t, title="[bold]System[/bold]", border_style="dim")


# ---------------------------------------------------------------------------
# Dashboard state container
# ---------------------------------------------------------------------------


class DashboardState:
    """Mutable state shared between the bot and the dashboard renderer."""

    def __init__(self) -> None:
        self.mode: str = "PAPER"
        self.balance: float = 0.0
        self.start_time: float = 0.0
        self.active_exchanges: list[str] = []
        self.opportunities: list[FundingOpportunity] = []
        self.open_positions: list[dict[str, Any]] = []
        self.recent_payments: list[dict[str, Any]] = []
        self.daily_stats: dict[str, Any] = {}
        self.all_time_funding: float = 0.0
        self.risk_daily_pnl: float = 0.0
        self.last_scan_time: str = "never"
        self.api_statuses: dict[str, str] = {}
        self.current_rates: dict[str, float] = {}  # symbol -> current rate
        self.next_payments: list[tuple[str, str]] = []  # (symbol, next_funding_time)

    def uptime_secs(self) -> int:
        import time
        return int(time.time() - self.start_time) if self.start_time else 0


# ---------------------------------------------------------------------------
# Main dashboard renderer
# ---------------------------------------------------------------------------


class Dashboard:
    REFRESH_INTERVAL = 5.0  # seconds

    def __init__(self, state: DashboardState) -> None:
        self._state = state
        self._live: Live | None = None
        self._running = False

    def _render(self) -> Layout:
        s = self._state
        layout = Layout()

        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=5),
        )
        layout["body"].split_column(
            Layout(name="top"),
            Layout(name="middle"),
            Layout(name="bottom"),
        )
        layout["top"].split_row(
            Layout(name="opps", ratio=3),
            Layout(name="stats", ratio=2),
        )

        layout["header"].update(
            _build_header(s.mode, s.balance, s.uptime_secs(), s.active_exchanges)
        )
        layout["opps"].update(
            _build_opportunities_table(s.opportunities)
        )
        layout["stats"].update(
            _build_stats_panel(
                s.daily_stats,
                s.all_time_funding,
                s.risk_daily_pnl,
                len(s.open_positions),
            )
        )
        layout["middle"].update(
            _build_positions_table(s.open_positions, s.current_rates)
        )
        layout["bottom"].update(
            _build_payments_table(s.recent_payments)
        )
        layout["footer"].update(
            _build_system_panel(
                s.last_scan_time,
                s.api_statuses,
                s.next_payments,
                cfg.scan_interval,
            )
        )
        return layout

    async def run(self) -> None:
        """Run the live dashboard until cancelled."""
        self._running = True
        with Live(
            self._render(),
            console=console,
            refresh_per_second=1,
            screen=True,
        ) as live:
            self._live = live
            while self._running:
                live.update(self._render())
                await asyncio.sleep(self.REFRESH_INTERVAL)

    def stop(self) -> None:
        self._running = False

    def print_startup_banner(
        self,
        mode: str,
        balance: float,
        exchanges: list[str],
        min_rate: float,
        max_positions: int,
    ) -> None:
        banner = Table.grid(padding=(0, 2))
        banner.add_row(Text("━" * 60, style="cyan"))
        banner.add_row(Text("  FUNDING RATE ARBITRAGE BOT", style="bold bright_cyan"))
        banner.add_row(Text("━" * 60, style="cyan"))
        banner.add_row(Text(f"  Mode:           {mode.upper()}", style="bold"))
        banner.add_row(Text(f"  Balance:        {_fmt_usdc(balance)}", style="green"))
        banner.add_row(Text(f"  Exchanges:      {', '.join(e.upper() for e in exchanges)}", style="white"))
        banner.add_row(Text(f"  Min Rate:       {_fmt_rate(min_rate)} / 8h  ({_fmt_apy(min_rate)} APY)", style="yellow"))
        banner.add_row(Text(f"  Max Positions:  {max_positions}", style="white"))
        banner.add_row(Text(f"  Scan Interval:  {cfg.scan_interval}s", style="dim"))
        banner.add_row(Text("━" * 60, style="cyan"))
        console.print(Panel(banner, border_style="bright_cyan"))
