"""
Polymarket Latency Arbitrage Bot — Main Orchestrator.

Usage:
  python bot.py                          # Paper mode (default)
  python bot.py --paper                  # Explicit paper mode
  python bot.py --live --confirm --yes   # Live mode (all 3 flags required)

Architecture:
  - Single asyncio event loop
  - Multiple tasks coordinated via asyncio.Queue
  - Graceful shutdown on SIGINT/SIGTERM
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional

from config import cfg
from database import Database, DailyStatsRecord, PositionRecord, TradeRecord
from binance_feed import BinanceFeed, PriceUpdate
from polymarket_client import PolymarketClient, MarketInfo, Orderbook
from edge_calculator import EdgeCalculator, EdgeResult
from risk_manager import RiskManager, TradeResult
from telegram_alerts import TelegramAlerter
from dashboard import Dashboard, DashboardState, AssetDisplayState, OpenPositionDisplay, TradeDisplay

# ── Logging setup ──────────────────────────────────────────────────────────────

def setup_logging() -> None:
    fmt = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
    datefmt = "%Y-%m-%dT%H:%M:%SZ"

    logging.Formatter.converter = time.gmtime  # Force UTC in logs

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Console handler (INFO+)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(ch)

    # File handler (DEBUG+)
    fh = logging.FileHandler(cfg.LOG_FILE, mode="a", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    root.addHandler(fh)


logger = logging.getLogger("bot")


# ── Active position tracker ────────────────────────────────────────────────────

class ActivePosition:
    """Tracks an open position through its lifecycle."""

    def __init__(
        self,
        db_id: int,
        market: MarketInfo,
        direction: str,
        entry_price: float,
        size_usdc: float,
        edge_result: EdgeResult,
        token_id: str,
    ) -> None:
        self.db_id = db_id
        self.market = market
        self.direction = direction
        self.entry_price = entry_price
        self.size_usdc = size_usdc
        self.entry_edge = edge_result.edge_pct
        self.entry_confidence = edge_result.confidence
        self.entry_time = time.time()
        self.token_id = token_id
        self.current_edge: float = edge_result.edge_pct
        self.unrealised_pnl: float = 0.0


# ── Main bot class ─────────────────────────────────────────────────────────────

class ArbitrageBot:
    """
    Main orchestrator. Manages all tasks and coordinates the trading pipeline.
    """

    # Task restart backoff
    _TASK_BACKOFF = [2, 5, 10, 30, 60]

    def __init__(self) -> None:
        self._db = Database()
        self._polymarket = PolymarketClient()
        self._risk = RiskManager(initial_portfolio=cfg.PAPER_STARTING_BALANCE)
        self._edge_calc = EdgeCalculator()
        self._telegram = TelegramAlerter()

        # Queues
        self._price_queue: asyncio.Queue[PriceUpdate] = asyncio.Queue(maxsize=500)
        self._signal_queue: asyncio.Queue[tuple] = asyncio.Queue(maxsize=100)

        # Dashboard state (shared mutable, written by tasks, read by dashboard)
        self._dash_state = DashboardState(
            mode="PAPER" if cfg.PAPER_MODE else "LIVE",
            portfolio_value=cfg.PAPER_STARTING_BALANCE,
        )
        self._dashboard = Dashboard(self._dash_state)

        # Binance feed
        self._binance_feed = BinanceFeed(self._price_queue)

        # Active positions: market_id -> ActivePosition
        self._positions: Dict[str, ActivePosition] = {}
        self._positions_lock = asyncio.Lock()

        # Market cache
        self._markets: Dict[str, MarketInfo] = {}

        # Shutdown event
        self._shutdown = asyncio.Event()

        # Signal dedup: track entry times
        self._entry_times: Dict[str, float] = {}

        # Start time
        self._start_time = time.time()

    # ── Entry point ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Start all tasks and run until shutdown."""
        await self._db.init_db()
        await self._print_startup_banner()

        async with self._polymarket, self._telegram:
            # Initial portfolio sync
            balance = await self._polymarket.get_portfolio_balance()
            self._risk.update_portfolio_value(balance)
            self._dash_state.portfolio_value = balance

            await self._telegram.startup_notification(
                mode="PAPER" if cfg.PAPER_MODE else "LIVE",
                portfolio_value=balance,
            )

            tasks = [
                asyncio.create_task(self._binance_feed_task(), name="binance_feed"),
                asyncio.create_task(self._polymarket_monitor_task(), name="poly_monitor"),
                asyncio.create_task(self._signal_detection_task(), name="signal_detect"),
                asyncio.create_task(self._execution_task(), name="execution"),
                asyncio.create_task(self._position_monitor_task(), name="position_monitor"),
                asyncio.create_task(self._daily_reset_task(), name="daily_reset"),
                asyncio.create_task(self._dashboard_task(), name="dashboard"),
                asyncio.create_task(self._telegram_summary_task(), name="tg_summary"),
            ]

            try:
                # Wait for shutdown signal
                await self._shutdown.wait()
            except asyncio.CancelledError:
                pass
            finally:
                logger.info("Initiating graceful shutdown...")
                await self._graceful_shutdown(tasks)

    # ── Task: Binance feed ─────────────────────────────────────────────────────

    async def _binance_feed_task(self) -> None:
        """Maintains Binance WebSocket, pushes price updates to queue."""
        backoff_idx = 0
        while not self._shutdown.is_set():
            try:
                await self._binance_feed.run()
                backoff_idx = 0
            except asyncio.CancelledError:
                break
            except Exception as exc:
                wait = self._TASK_BACKOFF[min(backoff_idx, len(self._TASK_BACKOFF) - 1)]
                logger.error("BinanceFeed task crashed (%s), restarting in %ds", exc, wait)
                backoff_idx += 1
                await asyncio.sleep(wait)

    # ── Task: Polymarket market monitor ───────────────────────────────────────

    async def _polymarket_monitor_task(self) -> None:
        """
        Polls Polymarket CLOB every 5 seconds to refresh market state.
        Updates market cache and dashboard.
        """
        poll_interval = 5.0
        backoff_idx = 0

        while not self._shutdown.is_set():
            try:
                markets = await self._polymarket.get_markets()
                if markets:
                    for m in markets:
                        self._markets[m.market_id] = m
                    self._dash_state.system.polymarket_last_poll_sec = time.time()
                    self._dash_state.system.polymarket_connected = True
                    logger.debug("Refreshed %d Polymarket markets", len(markets))
                    backoff_idx = 0
                await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                wait = self._TASK_BACKOFF[min(backoff_idx, len(self._TASK_BACKOFF) - 1)]
                logger.warning("Polymarket monitor error (%s), retry in %ds", exc, wait)
                self._dash_state.system.polymarket_connected = False
                backoff_idx += 1
                await asyncio.sleep(wait)

    # ── Task: Signal detection ─────────────────────────────────────────────────

    async def _signal_detection_task(self) -> None:
        """
        Consumes price updates from the Binance queue.
        For each update, checks all relevant Polymarket markets and computes edges.
        Pushes actionable signals to signal_queue.
        """
        while not self._shutdown.is_set():
            try:
                update: PriceUpdate = await asyncio.wait_for(
                    self._price_queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Update dashboard asset state
            asset_dash = self._dash_state.assets.get(update.asset)
            if asset_dash:
                asset_dash.binance_price = update.price
                asset_dash.velocity = update.velocity
                asset_dash.volume_ratio = update.volume_ratio
                asset_dash.last_update = update.timestamp
                self._dash_state.system.binance_ws_connected = True
                self._dash_state.system.binance_last_msg_sec = update.timestamp

            # Skip if no markets loaded yet
            if not self._markets:
                continue

            # Find markets matching this asset
            asset_markets = [
                m for m in self._markets.values()
                if m.asset == update.asset and m.active and not m.closed
            ]

            for market in asset_markets:
                # Skip low liquidity markets
                if market.liquidity < cfg.MIN_MARKET_LIQUIDITY:
                    continue

                # Skip if we already have a position in this market
                if market.market_id in self._positions:
                    continue

                # Determine contract duration
                contract_type = market.contract_type
                duration_sec = 300 if "5min" in contract_type else 900

                # Fetch orderbook (lightweight, cached indirectly via compute_edge)
                try:
                    token_id = (
                        market.yes_token_id
                        if market.yes_price > 0
                        else market.no_token_id
                    )
                    orderbook = await self._polymarket.get_orderbook(token_id)
                except Exception:
                    orderbook = None

                # Compute edge
                try:
                    edge_result = self._edge_calc.compute_edge(
                        asset=update.asset,
                        binance_data=update,
                        market=market,
                        orderbook=orderbook,
                        contract_duration_sec=duration_sec,
                    )
                except Exception as exc:
                    logger.debug("Edge calc error for %s: %s", market.market_id[:12], exc)
                    continue

                if edge_result is None:
                    continue

                # Update dashboard edge display
                if asset_dash:
                    asset_dash.polymarket_prob = market.yes_price
                    asset_dash.cex_implied_prob = edge_result.implied_cex_prob
                    asset_dash.current_edge_pct = edge_result.edge_pct

                if edge_result.tradeable:
                    logger.info(
                        "Signal: %s %s %s edge=%.1f%% conf=%.1%% time=%.0fs",
                        update.asset, market.contract_type, edge_result.direction,
                        edge_result.edge_pct, edge_result.confidence,
                        edge_result.time_to_expiry_sec,
                    )
                    self._dash_state.system.last_signal_time = time.time()
                    if asset_dash:
                        asset_dash.status = "ACTIVE"

                    try:
                        self._signal_queue.put_nowait((edge_result, market, orderbook))
                    except asyncio.QueueFull:
                        logger.warning("Signal queue full, dropping signal")
                else:
                    if asset_dash and asset_dash.status not in ("PAUSED",):
                        asset_dash.status = "NO SIGNAL"

    # ── Task: Execution ────────────────────────────────────────────────────────

    async def _execution_task(self) -> None:
        """
        Receives signals from signal_queue.
        Runs risk checks, sizes positions, and executes orders.
        """
        while not self._shutdown.is_set():
            try:
                item = await asyncio.wait_for(
                    self._signal_queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            edge_result, market, orderbook = item

            try:
                await self._execute_signal(edge_result, market, orderbook)
            except Exception as exc:
                logger.error("Execution error for signal %s: %s", market.market_id[:12], exc)

    async def _execute_signal(
        self,
        edge_result: EdgeResult,
        market: MarketInfo,
        orderbook: Optional[Orderbook],
    ) -> None:
        """Handle a single actionable signal: size, check, execute, log."""
        asset = edge_result.asset

        # Get current portfolio value
        portfolio_value = await self._polymarket.get_portfolio_balance()
        if portfolio_value == 0 and cfg.PAPER_MODE:
            # In paper mode, use risk manager's tracked value
            portfolio_value = self._risk.state.portfolio_value

        self._risk.update_portfolio_value(portfolio_value)

        # Determine entry price based on direction
        token_id = (
            market.yes_token_id if edge_result.direction == "YES"
            else market.no_token_id
        )
        entry_price = (
            market.yes_price if edge_result.direction == "YES"
            else market.no_price
        )
        if entry_price <= 0:
            entry_price = 0.5

        # Compute position size
        size_usdc = self._risk.compute_kelly_size(
            edge_pct=edge_result.edge_pct,
            confidence=edge_result.confidence,
            portfolio_value=portfolio_value,
            entry_price=entry_price,
        )

        # Slippage pre-check: verify enough liquidity at target price
        if orderbook:
            side = "BUY" if edge_result.direction == "YES" else "BUY"
            available = orderbook.available_at_levels(side, n_levels=3)
            if available < size_usdc:
                size_usdc = min(size_usdc, available * 0.8)  # Don't take >80% of available
                logger.debug("Size reduced to %.2f due to liquidity limit", size_usdc)

        # Risk gate check
        allowed, reason = self._risk.check_risk_gates(
            asset=asset,
            edge_result=edge_result,
            proposed_size=size_usdc,
        )

        if not allowed:
            logger.debug("Risk gate blocked: %s", reason)
            # Update dashboard asset status if paused
            if "paused" in reason.lower() or "kill" in reason.lower():
                dash_asset = self._dash_state.assets.get(asset)
                if dash_asset:
                    dash_asset.status = "PAUSED"
            return

        # Place order
        order = await self._polymarket.place_order(
            market_id=market.market_id,
            token_id=token_id,
            side="BUY",
            size_usdc=size_usdc,
            price=entry_price,
            order_type="GTC",
        )

        if order is None:
            logger.warning("Order placement failed for %s", market.market_id[:12])
            return

        # Log position to DB
        now = datetime.now(tz=timezone.utc)
        pos_record = PositionRecord(
            id=None,
            contract_id=market.market_id,
            asset=asset,
            direction=edge_result.direction,
            entry_price=order.filled_price,
            size_usdc=size_usdc,
            entry_edge=edge_result.edge_pct,
            entry_confidence=edge_result.confidence,
            entry_time=now,
            status="open",
        )
        db_id = await self._db.log_position_open(pos_record)

        # Track in memory
        active_pos = ActivePosition(
            db_id=db_id,
            market=market,
            direction=edge_result.direction,
            entry_price=order.filled_price,
            size_usdc=size_usdc,
            edge_result=edge_result,
            token_id=token_id,
        )

        async with self._positions_lock:
            self._positions[market.market_id] = active_pos

        self._risk.register_position_opened()
        self._dash_state.system.last_signal_time = time.time()

        # Update dashboard open positions
        self._update_dashboard_positions()

        # Alert
        await self._telegram.trade_opened(
            asset=asset,
            direction=edge_result.direction,
            size_usdc=size_usdc,
            edge_pct=edge_result.edge_pct,
            confidence=edge_result.confidence,
            entry_price=order.filled_price,
            paper_mode=cfg.PAPER_MODE,
        )

        logger.info(
            "Position opened: %s %s %s size=%.2f edge=%.1f%% conf=%.1%% db_id=%d",
            asset, market.contract_type, edge_result.direction,
            size_usdc, edge_result.edge_pct, edge_result.confidence, db_id,
        )

    # ── Task: Position monitor ────────────────────────────────────────────────

    async def _position_monitor_task(self) -> None:
        """
        Monitors open positions. Handles early exits when:
        - Edge compresses to <2% after entry → exit for profit
        - Contract within 60s of expiry → hold to expiry
        - Edge has inverted with high confidence → exit early
        """
        while not self._shutdown.is_set():
            try:
                await asyncio.sleep(2.0)
                await self._check_open_positions()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Position monitor error: %s", exc)

    async def _check_open_positions(self) -> None:
        """Evaluate all open positions for exit criteria."""
        async with self._positions_lock:
            market_ids = list(self._positions.keys())

        for market_id in market_ids:
            async with self._positions_lock:
                pos = self._positions.get(market_id)
            if pos is None:
                continue

            market = pos.market
            time_held = time.time() - pos.entry_time
            time_to_expiry = EdgeCalculator._parse_time_to_expiry(market.end_date_iso)

            # Refresh market price
            try:
                bid, ask = await self._polymarket.get_market_price(pos.token_id)
                if bid is not None and ask is not None:
                    current_price = (bid + ask) / 2
                else:
                    current_price = pos.entry_price
            except Exception:
                current_price = pos.entry_price

            # Current edge estimation (simplified: price moved toward or away from 0.5)
            if pos.direction == "YES":
                # We bought YES; if price went up, edge compressed (good for us)
                price_delta = current_price - pos.entry_price
            else:
                price_delta = pos.entry_price - current_price

            # Estimate current edge as fraction of entry edge remaining
            edge_remaining_pct = pos.entry_edge * (1 - min(price_delta / 0.1, 1.0))
            pos.current_edge = max(0.0, edge_remaining_pct)

            # Estimate unrealised P&L
            if pos.direction == "YES":
                pos.unrealised_pnl = (current_price - pos.entry_price) * (pos.size_usdc / pos.entry_price)
            else:
                pos.unrealised_pnl = (pos.entry_price - current_price) * (pos.size_usdc / pos.entry_price)

            # Exit conditions
            should_exit = False
            exit_reason = ""

            # 1. Edge compressed to < 2% → take profit
            if pos.current_edge < 2.0 and time_held > 10:
                should_exit = True
                exit_reason = f"Edge compressed to {pos.current_edge:.1f}%"

            # 2. Contract expired
            elif time_to_expiry <= 0:
                should_exit = True
                exit_reason = "Contract expired"

            # 3. Hold to expiry if > 50% of entry edge remains
            elif time_to_expiry <= 60 and pos.current_edge > (pos.entry_edge * 0.5):
                # Hold — close to expiry and still good edge
                pass

            if should_exit:
                await self._close_position(market_id, current_price, exit_reason)

        # Update dashboard
        self._update_dashboard_positions()

    async def _close_position(
        self,
        market_id: str,
        exit_price: float,
        reason: str,
    ) -> None:
        """Close a position, log the trade, update risk state."""
        async with self._positions_lock:
            pos = self._positions.pop(market_id, None)
        if pos is None:
            return

        # Calculate P&L
        if pos.direction == "YES":
            pnl = (exit_price - pos.entry_price) * (pos.size_usdc / pos.entry_price)
        else:
            pnl = (pos.entry_price - exit_price) * (pos.size_usdc / pos.entry_price)

        hold_duration = time.time() - pos.entry_time
        outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "EVEN"

        # Log to DB
        now = datetime.now(tz=timezone.utc)
        trade_record = TradeRecord(
            id=None,
            timestamp=now,
            asset=pos.market.asset,
            contract_id=market_id,
            direction=pos.direction,
            entry_price=pos.entry_price,
            exit_price=exit_price,
            size_usdc=pos.size_usdc,
            pnl=pnl,
            edge_at_entry=pos.entry_edge,
            confidence_at_entry=pos.entry_confidence,
            hold_duration_sec=hold_duration,
            outcome=outcome,
            paper_mode=cfg.PAPER_MODE,
        )
        await self._db.log_trade(trade_record)
        await self._db.log_position_close(pos.db_id, exit_price, pnl, outcome)

        # Update risk state
        trade_result = TradeResult(
            asset=pos.market.asset,
            pnl=pnl,
            size_usdc=pos.size_usdc,
            edge_at_entry=pos.entry_edge,
            paper_mode=cfg.PAPER_MODE,
        )
        self._risk.update_pnl(trade_result)
        self._risk.register_position_closed()

        # Check if kill switch just triggered
        if self._risk.state.kill_switch_triggered:
            await self._telegram.kill_switch_triggered(
                reason=self._risk.state.kill_switch_reason,
                daily_pnl=self._risk.state.daily_pnl,
            )

        # Update dashboard stats
        self._dash_state.portfolio_value = self._risk.state.portfolio_value
        self._dash_state.daily_pnl = self._risk.state.daily_pnl
        self._dash_state.daily_pnl_pct = self._risk.state.daily_pnl_pct
        self._dash_state.drawdown_pct = self._risk.state.current_drawdown_pct
        self._dash_state.total_trades += 1
        if outcome == "WIN":
            self._dash_state.wins += 1
        elif outcome == "LOSS":
            self._dash_state.losses += 1
        total = self._dash_state.wins + self._dash_state.losses
        if total > 0:
            self._dash_state.win_rate = self._dash_state.wins / total

        # Update kill switch in dashboard
        self._dash_state.kill_switch = self._risk.state.kill_switch_triggered

        # Add to trade history display
        self._dash_state.last_trades.append(TradeDisplay(
            timestamp=time.time(),
            asset=pos.market.asset,
            direction=pos.direction,
            size_usdc=pos.size_usdc,
            pnl=pnl,
            outcome="PAPER" if cfg.PAPER_MODE else outcome,
        ))
        if len(self._dash_state.last_trades) > 50:
            self._dash_state.last_trades = self._dash_state.last_trades[-50:]

        # Alert
        await self._telegram.trade_closed(
            asset=pos.market.asset,
            direction=pos.direction,
            size_usdc=pos.size_usdc,
            pnl=pnl,
            hold_duration_sec=hold_duration,
            outcome=outcome,
            paper_mode=cfg.PAPER_MODE,
        )

        logger.info(
            "Position closed: %s %s %s pnl=%.4f hold=%.0fs reason='%s'",
            pos.market.asset, pos.direction, market_id[:12],
            pnl, hold_duration, reason,
        )

    # ── Task: Daily reset ─────────────────────────────────────────────────────

    async def _daily_reset_task(self) -> None:
        """Runs a daily reset at midnight UTC."""
        while not self._shutdown.is_set():
            now = datetime.now(tz=timezone.utc)
            # Calculate seconds until next midnight UTC
            next_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
            # next_midnight is today's midnight if we're past it; add a day
            from datetime import timedelta
            next_midnight = next_midnight + timedelta(days=1)
            wait_sec = (next_midnight - now).total_seconds()

            try:
                await asyncio.sleep(min(wait_sec, 3600))  # Wake up at least hourly
                now_check = datetime.now(tz=timezone.utc)
                if now_check.hour == 0 and now_check.minute < 5:
                    self._risk.reset_daily()
                    self._dash_state.daily_pnl = 0.0
                    self._dash_state.daily_pnl_pct = 0.0
                    logger.info("Daily reset completed.")
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Daily reset error: %s", exc)

    # ── Task: Dashboard ───────────────────────────────────────────────────────

    async def _dashboard_task(self) -> None:
        """Runs the Rich terminal dashboard."""
        try:
            await self._dashboard.run()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            # Dashboard failures are non-fatal
            logger.warning("Dashboard crashed (non-fatal): %s", exc)

    # ── Task: Telegram daily summary ──────────────────────────────────────────

    async def _telegram_summary_task(self) -> None:
        """Sends daily summary at 23:55 UTC."""
        while not self._shutdown.is_set():
            now = datetime.now(tz=timezone.utc)
            if now.hour == 23 and now.minute == 55:
                try:
                    stats = await self._db.get_daily_stats()
                    wins = stats.wins if stats else self._dash_state.wins
                    losses = stats.losses if stats else self._dash_state.losses
                    total = wins + losses
                    win_rate = wins / total if total > 0 else 0.0
                    net_pnl = stats.net_pnl if stats else self._dash_state.daily_pnl

                    await self._telegram.daily_summary(
                        total_trades=total,
                        wins=wins,
                        losses=losses,
                        net_pnl=net_pnl,
                        win_rate=win_rate,
                        portfolio_value=self._risk.state.portfolio_value,
                        max_drawdown=self._risk.state.current_drawdown_pct,
                        paper_mode=cfg.PAPER_MODE,
                    )
                except Exception as exc:
                    logger.error("Telegram summary error: %s", exc)
                await asyncio.sleep(120)  # Avoid sending twice
            else:
                await asyncio.sleep(60)

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _update_dashboard_positions(self) -> None:
        """Sync open positions to dashboard display state."""
        display_positions = []
        for pos in self._positions.values():
            time_open = time.time() - pos.entry_time
            display_positions.append(OpenPositionDisplay(
                asset=pos.market.asset,
                contract_id=pos.market.market_id[:12],
                direction=pos.direction,
                entry_price=pos.entry_price,
                size_usdc=pos.size_usdc,
                current_edge_pct=pos.current_edge,
                unrealised_pnl=pos.unrealised_pnl,
                time_open_sec=time_open,
                entry_time=pos.entry_time,
            ))
        self._dash_state.open_positions = display_positions

    async def _close_all_positions(self) -> None:
        """Close all open positions at current market prices (used on shutdown)."""
        async with self._positions_lock:
            market_ids = list(self._positions.keys())

        for market_id in market_ids:
            async with self._positions_lock:
                pos = self._positions.get(market_id)
            if pos is None:
                continue
            try:
                bid, ask = await self._polymarket.get_market_price(pos.token_id)
                exit_price = bid if bid else pos.entry_price
                await self._close_position(market_id, exit_price, "bot_shutdown")
            except Exception as exc:
                logger.error("Error closing position %s on shutdown: %s", market_id[:12], exc)

    async def _graceful_shutdown(self, tasks: list) -> None:
        """Shut down cleanly: close positions, alert, stop tasks."""
        logger.info("Closing all open positions...")
        await self._close_all_positions()

        portfolio_value = self._risk.state.portfolio_value
        await self._telegram.shutdown_notification(
            reason="User requested shutdown",
            portfolio_value=portfolio_value,
        )

        # Cancel all tasks
        for task in tasks:
            if not task.done():
                task.cancel()

        # Wait for tasks to finish
        await asyncio.gather(*tasks, return_exceptions=True)

        # Close DB
        await self._db.close()
        logger.info("Shutdown complete. Final portfolio: $%.2f", portfolio_value)

    def _shutdown_signal_handler(self) -> None:
        """Handle SIGINT/SIGTERM by setting the shutdown event."""
        logger.info("Shutdown signal received.")
        self._shutdown.set()

    async def _print_startup_banner(self) -> None:
        """Print configuration banner (with masked secrets)."""
        masked = cfg.masked_repr()
        logger.info("=" * 65)
        logger.info("  POLYMARKET LATENCY ARBITRAGE BOT")
        logger.info("  Mode: %s", "PAPER" if cfg.PAPER_MODE else "LIVE")
        logger.info("=" * 65)
        for key, val in masked.items():
            logger.info("  %-30s = %s", key, val)
        logger.info("=" * 65)


# ── CLI ────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Polymarket Latency Arbitrage Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python bot.py                         # Paper mode (default)\n"
            "  python bot.py --paper                 # Explicit paper mode\n"
            "  python bot.py --live --confirm --yes  # Live trading\n"
        ),
    )
    parser.add_argument("--paper", action="store_true", help="Paper mode (default)")
    parser.add_argument("--live", action="store_true", help="Enable live trading (requires --confirm --yes)")
    parser.add_argument("--confirm", action="store_true", help="Confirm live trading")
    parser.add_argument("--yes", action="store_true", help="Final confirmation for live trading")
    return parser.parse_args()


async def _main() -> None:
    setup_logging()
    args = parse_args()

    if args.live:
        if not (args.confirm and args.yes):
            print("ERROR: Live trading requires all three flags: --live --confirm --yes")
            sys.exit(1)
        logger.warning("LIVE TRADING MODE ENABLED — real funds at risk!")
        cfg.enable_live_mode()
    else:
        cfg.PAPER_MODE = True
        logger.info("Running in PAPER mode.")

    bot = ArbitrageBot()

    # Install signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, bot._shutdown_signal_handler)

    await bot.run()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as exc:
        logging.exception("Fatal error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()
