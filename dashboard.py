"""
Rich terminal dashboard for the Polymarket arbitrage bot.

Runs in a separate asyncio task, reading from shared state.
Refreshes every second using rich.live.Live.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from rich import box
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from config import cfg

console = Console()


# ── Shared state structures ────────────────────────────────────────────────────

@dataclass
class AssetDisplayState:
    asset: str
    binance_price: float = 0.0
    polymarket_prob: float = 0.0
    cex_implied_prob: float = 0.0
    current_edge_pct: float = 0.0
    status: str = "STARTING"  # "ACTIVE", "PAUSED", "NO SIGNAL", "STARTING"
    velocity: float = 0.0
    volume_ratio: float = 1.0
    last_update: float = 0.0


@dataclass
class OpenPositionDisplay:
    asset: str
    contract_id: str
    direction: str
    entry_price: float
    size_usdc: float
    current_edge_pct: float
    unrealised_pnl: float
    time_open_sec: float
    entry_time: float = field(default_factory=time.time)


@dataclass
class TradeDisplay:
    timestamp: float
    asset: str
    direction: str
    size_usdc: float
    pnl: Optional[float]
    outcome: str  # "WIN", "LOSS", "OPEN", "PAPER"


@dataclass
class SystemStatusDisplay:
    binance_ws_connected: bool = False
    binance_last_msg_sec: float = 0.0
    polymarket_connected: bool = False
    polymarket_last_poll_sec: float = 0.0
    last_signal_time: float = 0.0
    api_rate_limit_remaining: int = 10
    uptime_sec: float = 0.0
    start_time: float = field(default_factory=time.time)


@dataclass
class DashboardState:
    """
    Shared mutable state updated by the trading tasks,
    read by the dashboard renderer.
    """
    mode: str = "PAPER"
    portfolio_value: float = cfg.PAPER_STARTING_BALANCE
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    drawdown_pct: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    wins: int = 0
    losses: int = 0

    assets: Dict[str, AssetDisplayState] = field(
        default_factory=lambda: {
            "BTC": AssetDisplayState("BTC"),
            "ETH": AssetDisplayState("ETH"),
        }
    )
    open_positions: List[OpenPositionDisplay] = field(default_factory=list)
    last_trades: List[TradeDisplay] = field(default_factory=list)
    system: SystemStatusDisplay = field(default_factory=SystemStatusDisplay)
    kill_switch: bool = False


# ── Renderer ──────────────────────────────────────────────────────────────────

class Dashboard:
    """Async dashboard that renders to terminal using Rich Live."""

    REFRESH_RATE = 1.0  # seconds

    def __init__(self, state: DashboardState) -> None:
        self._state = state
        self._running = False

    async def run(self) -> None:
        """Main dashboard loop. Runs until cancelled."""
        self._running = True
        self._state.system.start_time = time.time()

        with Live(
            self._render(),
            console=console,
            refresh_per_second=1,
            screen=True,
        ) as live:
            while self._running:
                try:
                    self._state.system.uptime_sec = (
                        time.time() - self._state.system.start_time
                    )
                    live.update(self._render())
                    await asyncio.sleep(self.REFRESH_RATE)
                except asyncio.CancelledError:
                    break
                except Exception:
                    # Dashboard errors should never crash the bot
                    await asyncio.sleep(self.REFRESH_RATE)

    async def stop(self) -> None:
        self._running = False

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="middle", size=12),
            Layout(name="positions", size=12),
            Layout(name="trades", size=14),
            Layout(name="footer", size=5),
        )

        layout["middle"].split_row(
            Layout(name="portfolio", ratio=1),
            Layout(name="assets", ratio=2),
        )

        layout["header"].update(self._render_header())
        layout["portfolio"].update(self._render_portfolio())
        layout["assets"].update(self._render_assets())
        layout["positions"].update(self._render_positions())
        layout["trades"].update(self._render_trades())
        layout["footer"].update(self._render_system_status())

        return layout

    def _render_header(self) -> Panel:
        s = self._state
        uptime = _format_duration(s.system.uptime_sec)
        mode_style = "bold red" if s.mode == "LIVE" else "bold cyan"
        ks_text = " [bold red]⚠ KILL SWITCH[/bold red]" if s.kill_switch else ""
        text = Text()
        text.append("  Polymarket Latency Arbitrage Bot  ", style="bold white on dark_blue")
        text.append(f"  [{s.mode}]", style=mode_style)
        text.append(f"  Uptime: {uptime}", style="dim")
        text.append(ks_text)
        return Panel(text, style="bold")

    def _render_portfolio(self) -> Panel:
        s = self._state
        pnl_style = "green" if s.daily_pnl >= 0 else "red"
        pnl_sign = "+" if s.daily_pnl >= 0 else ""

        table = Table(box=None, show_header=False, padding=(0, 1))
        table.add_column("Key", style="dim")
        table.add_column("Value")

        table.add_row("Portfolio", f"[bold white]${s.portfolio_value:.2f}[/bold white]")
        table.add_row(
            "Daily P&L",
            f"[{pnl_style}]{pnl_sign}${s.daily_pnl:.4f} ({pnl_sign}{s.daily_pnl_pct:.1%})[/{pnl_style}]",
        )
        dd_style = "red" if s.drawdown_pct > 0.10 else "yellow" if s.drawdown_pct > 0.05 else "green"
        table.add_row("Drawdown", f"[{dd_style}]{s.drawdown_pct:.1%}[/{dd_style}]")
        table.add_row("Win Rate", f"{s.win_rate:.1%} ({s.wins}W / {s.losses}L)")
        table.add_row("Trades", str(s.total_trades))

        return Panel(table, title="[bold]Portfolio[/bold]", border_style="blue")

    def _render_assets(self) -> Panel:
        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Asset", width=6)
        table.add_column("Price", width=12)
        table.add_column("PM Prob", width=9)
        table.add_column("CEX Prob", width=9)
        table.add_column("Edge", width=8)
        table.add_column("Vel ($/s)", width=10)
        table.add_column("Vol Ratio", width=10)
        table.add_column("Status", width=12)

        for asset_name, asset in self._state.assets.items():
            edge_style = (
                "bold green" if asset.current_edge_pct >= cfg.MIN_EDGE_PCT
                else "yellow" if asset.current_edge_pct >= cfg.LAG_THRESHOLD_BASE
                else "dim"
            )
            status_style = (
                "bold green" if asset.status == "ACTIVE"
                else "bold red" if asset.status == "PAUSED"
                else "dim"
            )
            age = time.time() - asset.last_update if asset.last_update > 0 else 999
            stale = age > 10

            table.add_row(
                f"[bold]{asset_name}[/bold]",
                f"{'[dim]' if stale else ''}${asset.binance_price:,.2f}{'[/dim]' if stale else ''}",
                f"{asset.polymarket_prob:.3f}",
                f"{asset.cex_implied_prob:.3f}",
                f"[{edge_style}]{asset.current_edge_pct:.1f}%[/{edge_style}]",
                f"{asset.velocity:+.2f}",
                f"{asset.volume_ratio:.2f}x",
                f"[{status_style}]{asset.status}[/{status_style}]",
            )

        return Panel(table, title="[bold]Asset Status[/bold]", border_style="blue")

    def _render_positions(self) -> Panel:
        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Asset", width=6)
        table.add_column("Dir", width=5)
        table.add_column("Entry", width=8)
        table.add_column("Size", width=10)
        table.add_column("Edge", width=8)
        table.add_column("Unreal. P&L", width=12)
        table.add_column("Open", width=10)

        positions = self._state.open_positions
        if not positions:
            table.add_row(
                "[dim]—", "—", "—", "—", "—", "—", "—[/dim]",
            )
        else:
            for pos in positions[:10]:  # max 10 rows
                pnl_style = "green" if pos.unrealised_pnl >= 0 else "red"
                pnl_sign = "+" if pos.unrealised_pnl >= 0 else ""
                table.add_row(
                    f"[bold]{pos.asset}[/bold]",
                    pos.direction,
                    f"{pos.entry_price:.4f}",
                    f"${pos.size_usdc:.2f}",
                    f"{pos.current_edge_pct:.1f}%",
                    f"[{pnl_style}]{pnl_sign}${pos.unrealised_pnl:.4f}[/{pnl_style}]",
                    _format_duration(pos.time_open_sec),
                )

        return Panel(
            table,
            title=f"[bold]Open Positions ({len(positions)})[/bold]",
            border_style="blue",
        )

    def _render_trades(self) -> Panel:
        table = Table(
            box=box.SIMPLE_HEAD,
            show_header=True,
            header_style="bold cyan",
            expand=True,
        )
        table.add_column("Time (UTC)", width=20)
        table.add_column("Asset", width=6)
        table.add_column("Dir", width=5)
        table.add_column("Size", width=10)
        table.add_column("P&L", width=12)
        table.add_column("Outcome", width=10)

        trades = self._state.last_trades[-10:][::-1]  # last 10, newest first
        if not trades:
            table.add_row("[dim]—", "—", "—", "—", "—", "—[/dim]")
        else:
            for t in trades:
                dt = datetime.fromtimestamp(t.timestamp, tz=timezone.utc)
                ts_str = dt.strftime("%m-%d %H:%M:%S")
                pnl_str = f"${t.pnl:+.4f}" if t.pnl is not None else "—"
                outcome_style = (
                    "bold green" if t.outcome == "WIN"
                    else "bold red" if t.outcome == "LOSS"
                    else "cyan" if t.outcome == "PAPER"
                    else "dim"
                )
                table.add_row(
                    ts_str,
                    f"[bold]{t.asset}[/bold]",
                    t.direction,
                    f"${t.size_usdc:.2f}",
                    pnl_str,
                    f"[{outcome_style}]{t.outcome}[/{outcome_style}]",
                )

        return Panel(table, title="[bold]Last 10 Trades[/bold]", border_style="blue")

    def _render_system_status(self) -> Panel:
        s = self._state.system
        now = time.time()

        def age_str(last_ts: float) -> str:
            if last_ts == 0:
                return "[red]NEVER[/red]"
            age = now - last_ts
            if age < 3:
                return f"[green]{age:.1f}s ago[/green]"
            elif age < 30:
                return f"[yellow]{age:.1f}s ago[/yellow]"
            return f"[red]{age:.1f}s ago[/red]"

        binance_status = "[green]CONNECTED[/green]" if s.binance_ws_connected else "[red]DISCONNECTED[/red]"
        poly_status = "[green]CONNECTED[/green]" if s.polymarket_connected else "[yellow]POLLING[/yellow]"

        parts = [
            f"Binance WS: {binance_status} | Last msg: {age_str(s.binance_last_msg_sec)}",
            f"Polymarket: {poly_status} | Last poll: {age_str(s.polymarket_last_poll_sec)}",
            f"Last signal: {age_str(s.last_signal_time)} | Rate limit: {s.api_rate_limit_remaining}/10 rps",
        ]
        text = "\n".join(parts)

        return Panel(text, title="[bold]System Status[/bold]", border_style="dim")


# ── Helpers ────────────────────────────────────────────────────────────────────

def _format_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"
