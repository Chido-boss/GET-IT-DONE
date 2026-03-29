"""
Main orchestrator for the Funding Rate Arbitrage Bot.

Usage:
    python bot.py                         # Paper mode (safe default)
    python bot.py --live --confirm --yes  # Live trading (all three flags required)
    python bot.py --no-dashboard          # Paper mode, no Rich TUI (plain logs only)
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Any

import httpx

from config import cfg
from database import Database
from dashboard import Dashboard, DashboardState
from exchange_client import ExchangeClient
from opportunity_scanner import (
    FundingOpportunity,
    check_basis_exit,
    check_exit_conditions,
    scan_opportunities,
)
from risk_manager import RiskManager

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Telegram notifier
# ---------------------------------------------------------------------------


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str) -> None:
        self._token = token
        self._chat_id = chat_id
        self._client = httpx.AsyncClient()

    async def send(self, message: str) -> None:
        url = f"https://api.telegram.org/bot{self._token}/sendMessage"
        try:
            await self._client.post(
                url,
                json={"chat_id": self._chat_id, "text": message, "parse_mode": "HTML"},
                timeout=5.0,
            )
        except Exception as exc:
            logger.warning("Telegram send failed: %s", exc)

    async def close(self) -> None:
        await self._client.aclose()


# ---------------------------------------------------------------------------
# Bot
# ---------------------------------------------------------------------------


class FundingRateBot:
    def __init__(self, live_mode: bool = False, show_dashboard: bool = True) -> None:
        if live_mode and cfg.paper_mode:
            raise RuntimeError(
                "Cannot run live: PAPER_MODE=True in config/env. "
                "Set PAPER_MODE=False and pass --live --confirm --yes."
            )
        self._live = live_mode
        self._show_dashboard = show_dashboard
        self._start_time = time.time()
        self._running = False

        self.db = Database()
        self.exchange = ExchangeClient(cfg)
        self.risk = RiskManager()
        self.dash_state = DashboardState()
        self.dashboard = Dashboard(self.dash_state)
        self.notifier: TelegramNotifier | None = (
            TelegramNotifier(cfg.telegram_bot_token, cfg.telegram_chat_id)
            if cfg.telegram_enabled
            else None
        )

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------

    async def start(self) -> None:
        cfg.setup_logging()
        logger.info("Funding Rate Bot starting (mode=%s)", "LIVE" if self._live else "PAPER")

        await self.db.init_db()
        await self.db.reset_daily_stats()

        balance = await self.exchange.get_balance()
        self.risk.set_portfolio_value(balance)

        # Sync open position count
        open_positions = await self.db.get_open_positions()
        self.risk.sync_open_count(len(open_positions))

        # Determine active exchanges
        active_exchanges: list[str] = []
        if self.exchange.bybit:
            active_exchanges.append("bybit")
        if self.exchange.okx:
            active_exchanges.append("okx")
        if not active_exchanges:
            active_exchanges.append("coinglass-only")

        # Populate dashboard state
        self.dash_state.mode = "LIVE" if self._live else "PAPER"
        self.dash_state.balance = balance
        self.dash_state.start_time = self._start_time
        self.dash_state.active_exchanges = active_exchanges

        # Print startup banner (before dashboard takes over screen)
        self.dashboard.print_startup_banner(
            mode="LIVE" if self._live else "PAPER",
            balance=balance,
            exchanges=active_exchanges,
            min_rate=cfg.min_funding_rate,
            max_positions=cfg.max_total_positions,
        )

        if self.notifier:
            await self.notifier.send(
                f"🤖 <b>Funding Rate Bot Started</b>\n"
                f"Mode: {'LIVE' if self._live else 'PAPER'}\n"
                f"Balance: ${balance:,.2f}\n"
                f"Exchanges: {', '.join(active_exchanges)}"
            )

        self._running = True

    async def stop(self) -> None:
        logger.info("Bot stopping...")
        self._running = False
        if self.notifier:
            await self.notifier.send("⛔ <b>Funding Rate Bot Stopped</b>")
            await self.notifier.close()
        await self.exchange.close()
        await self.db.close()
        logger.info("Bot stopped cleanly.")

    # ------------------------------------------------------------------
    # Core async tasks
    # ------------------------------------------------------------------

    async def funding_scanner_task(self) -> None:
        """
        Periodically scan for new opportunities and open positions when gates pass.
        Runs every SCAN_INTERVAL seconds.
        """
        logger.info("Scanner task started (interval=%ds)", cfg.scan_interval)
        while self._running:
            try:
                await self._run_scan()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Scanner task error: %s", exc, exc_info=True)
            await asyncio.sleep(cfg.scan_interval)

    async def _run_scan(self) -> None:
        open_symbols = await self.db.get_open_symbols()
        opportunities = await scan_opportunities(
            self.exchange, self.risk, open_symbols
        )
        balance = await self.exchange.get_balance()
        self.risk.set_portfolio_value(balance)

        now_str = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")
        self.dash_state.last_scan_time = now_str
        self.dash_state.opportunities = opportunities
        self.dash_state.balance = balance

        # Log all snapshots to DB for later analysis
        for opp in opportunities[:20]:
            await self.db.log_funding_snapshot(
                exchange=opp.perp_exchange,
                symbol=opp.perp_symbol,
                funding_rate=opp.funding_rate,
                annualized_rate=opp.annualized_rate,
                next_funding_time=opp.next_funding_time,
            )

        # Try to open positions for the best opportunities
        for opp in opportunities:
            if not self._running:
                break
            allowed, reason = self.risk.check_gates(opp, balance)
            if not allowed:
                logger.debug("Gate denied %s: %s", opp.symbol, reason)
                continue

            size = self.risk.compute_position_size(opp, balance)
            if size < cfg.min_position_usdc:
                logger.debug("Size too small for %s: %.2f", opp.symbol, size)
                continue

            await self._open_position(opp, size)
            balance -= size  # approximate balance decrease
            # Only open one per scan cycle to be conservative
            break

    async def position_monitor_task(self) -> None:
        """
        Check exit conditions on all open positions every 60 seconds.
        """
        logger.info("Position monitor task started")
        while self._running:
            try:
                await self._check_all_exits()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Monitor task error: %s", exc, exc_info=True)
            await asyncio.sleep(60)

    async def _check_all_exits(self) -> None:
        positions = await self.db.get_open_positions()
        self.dash_state.open_positions = positions
        self.risk.sync_open_count(len(positions))

        # Build current-rates lookup from latest snapshots
        top_opps = await self.db.get_top_opportunities(limit=50)
        current_rates: dict[str, float] = {}
        for row in top_opps:
            # row["symbol"] is the perp symbol; convert to base for dashboard
            current_rates[row["symbol"]] = row["funding_rate"]
        self.dash_state.current_rates = current_rates

        for pos in positions:
            pos_id = pos["id"]
            symbol = pos["symbol"]
            perp_exchange = pos["exchange_perp"]
            spot_exchange = pos["exchange_spot"]

            # Look up current funding rate (use perp_symbol if we have it)
            curr_rate = 0.0
            perp_sym_key = self.exchange.to_perp_symbol(perp_exchange, symbol)
            for row in top_opps:
                if row["exchange"] == perp_exchange and row["symbol"] == perp_sym_key:
                    curr_rate = row["funding_rate"]
                    break

            should_exit, reason = check_exit_conditions(
                pos, curr_rate, pos.get("below_threshold_count", 0)
            )

            if curr_rate < cfg.exit_funding_rate:
                new_count = await self.db.increment_below_threshold(pos_id)
                logger.info(
                    "Position %s below threshold: count=%d/%d",
                    symbol, new_count, cfg.exit_consecutive_cycles,
                )
            else:
                await self.db.reset_below_threshold(pos_id)

            # Check basis exit
            if not should_exit:
                try:
                    _, curr_spot = await self.exchange.get_best_spot_price(symbol)
                    perp_sym = self.exchange.to_perp_symbol(perp_exchange, symbol)
                    curr_perp = await self.exchange.get_perp_price(perp_exchange, perp_sym)
                    if curr_spot > 0 and curr_perp > 0:
                        should_exit, reason = check_basis_exit(
                            pos["entry_spot_price"],
                            pos["entry_perp_price"],
                            curr_spot,
                            curr_perp,
                        )
                except Exception as exc:
                    logger.debug("Basis check error for %s: %s", symbol, exc)
                    curr_spot = curr_perp = 0.0

            if should_exit:
                await self._close_position(pos, reason)

    async def funding_payment_task(self) -> None:
        """
        Every 30 minutes, simulate/record funding payments for open positions.
        In live mode, payments are credited automatically by the exchange,
        but we still track them in the DB.
        """
        logger.info("Funding payment task started")
        while self._running:
            try:
                await self._process_funding_payments()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Funding payment task error: %s", exc, exc_info=True)
            await asyncio.sleep(30 * 60)  # every 30 minutes

    async def _process_funding_payments(self) -> None:
        positions = await self.db.get_open_positions()
        if not positions:
            return

        # Get current rates for payment simulation
        top_opps = await self.db.get_top_opportunities(limit=100)
        symbol_rates: dict[str, float] = {r["symbol"]: r["funding_rate"] for r in top_opps}

        if cfg.paper_mode and self.exchange.paper:
            # Paper simulator handles the 8h interval check internally
            payments = self.exchange.simulate_funding_payments(symbol_rates)
            for symbol, amount in payments:
                # Find the DB position for this symbol
                for pos in positions:
                    if pos["symbol"] == symbol:
                        rate = symbol_rates.get(
                            self.exchange.to_perp_symbol(pos["exchange_perp"], symbol),
                            pos["entry_funding_rate"],
                        )
                        await self.db.log_funding_payment(pos["id"], amount, rate)
                        self.risk.update_pnl(amount)
                        logger.info(
                            "[PAPER] Logged funding payment: %s %.4f USDC", symbol, amount
                        )
                        if self.notifier:
                            await self.notifier.send(
                                f"💰 <b>Funding Payment</b>\n"
                                f"Symbol: {symbol}\n"
                                f"Amount: ${amount:.4f}\n"
                                f"Rate: {rate * 100:.4f}%"
                            )
                        break
        else:
            # Live mode: payments are credited by exchange automatically.
            # We estimate and log them for tracking purposes.
            now = datetime.now(timezone.utc)
            for pos in positions:
                symbol = pos["symbol"]
                perp_exchange = pos["exchange_perp"]
                perp_sym = self.exchange.to_perp_symbol(perp_exchange, symbol)
                rate = symbol_rates.get(perp_sym, pos["entry_funding_rate"])
                # Approximate: spot_size (base qty) * rate * spot_price
                approx_amount = pos["spot_size"] * rate * pos["entry_spot_price"]
                if approx_amount > 0:
                    await self.db.log_funding_payment(pos["id"], approx_amount, rate)
                    self.risk.update_pnl(approx_amount)

        # Refresh recent payments for dashboard
        self.dash_state.recent_payments = await self.db.get_recent_payments(10)

    async def dashboard_task(self) -> None:
        """Drive the Rich TUI dashboard."""
        if not self._show_dashboard:
            return
        try:
            await self.dashboard.run()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Dashboard error: %s", exc, exc_info=True)

    async def daily_reset_task(self) -> None:
        """
        At midnight UTC, reset daily P&L stats and update risk manager reference balance.
        """
        logger.info("Daily reset task started")
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                # Seconds until next midnight UTC
                secs_until_midnight = (
                    (23 - now.hour) * 3600
                    + (59 - now.minute) * 60
                    + (60 - now.second)
                )
                await asyncio.sleep(secs_until_midnight)
                if not self._running:
                    break
                logger.info("Midnight UTC – performing daily reset")
                await self.db.reset_daily_stats()
                balance = await self.exchange.get_balance()
                self.risk.set_portfolio_value(balance)
                self.dash_state.daily_stats = await self.db.get_daily_stats()
                self.dash_state.all_time_funding = await self.db.get_all_time_funding()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Daily reset error: %s", exc, exc_info=True)
                await asyncio.sleep(3600)  # retry in an hour

    # ------------------------------------------------------------------
    # Position open / close helpers
    # ------------------------------------------------------------------

    async def _open_position(
        self,
        opp: FundingOpportunity,
        size_usdc: float,
    ) -> None:
        logger.info(
            "Opening position: %s | perp=%s spot=%s | size=%.2f USDC | rate=%.6f",
            opp.symbol, opp.perp_exchange, opp.spot_exchange, size_usdc, opp.funding_rate,
        )
        try:
            await self.exchange.open_position(
                symbol=opp.symbol,
                spot_exchange=opp.spot_exchange,
                perp_exchange=opp.perp_exchange,
                size_usdc=size_usdc,
                spot_price=opp.spot_price,
                perp_price=opp.perp_price,
                funding_rate=opp.funding_rate,
                perp_symbol=opp.perp_symbol,
            )
        except Exception as exc:
            logger.error("Failed to open position for %s: %s", opp.symbol, exc)
            return

        base_qty = size_usdc / opp.spot_price if opp.spot_price > 0 else 0.0
        pos_id = await self.db.open_position(
            symbol=opp.symbol,
            exchange_spot=opp.spot_exchange,
            exchange_perp=opp.perp_exchange,
            spot_size=base_qty,
            perp_size=base_qty,
            entry_spot_price=opp.spot_price,
            entry_perp_price=opp.perp_price,
            entry_funding_rate=opp.funding_rate,
            paper_mode=cfg.paper_mode,
        )
        await self.db.log_trade(
            symbol=opp.symbol,
            action="open",
            spot_exchange=opp.spot_exchange,
            perp_exchange=opp.perp_exchange,
            spot_price=opp.spot_price,
            perp_price=opp.perp_price,
            size_usdc=size_usdc,
            reason=f"funding_rate={opp.funding_rate:.6f}",
            paper_mode=cfg.paper_mode,
        )
        self.risk.register_opened()
        self.dash_state.balance = await self.exchange.get_balance()

        proj = self.risk.estimate_returns(opp, size_usdc, days=30)
        logger.info(
            "Position opened: id=%d symbol=%s | 30d projected net: $%.2f (%.1f%% APY)",
            pos_id, opp.symbol, proj.net_projected_return, proj.projected_apy * 100,
        )

        if self.notifier:
            await self.notifier.send(
                f"✅ <b>Position Opened</b>\n"
                f"Symbol: {opp.symbol}\n"
                f"Perp: {opp.perp_exchange.upper()} | Spot: {opp.spot_exchange.upper()}\n"
                f"Size: ${size_usdc:,.2f}\n"
                f"Rate: {opp.funding_rate * 100:.4f}% / 8h ({opp.annualized_rate * 100:.1f}% APY)\n"
                f"30d Projected: ${proj.net_projected_return:.2f}"
            )

    async def _close_position(self, pos: dict[str, Any], reason: str) -> None:
        symbol = pos["symbol"]
        pos_id = pos["id"]
        logger.info("Closing position %s (id=%d): %s", symbol, pos_id, reason)

        perp_sym = self.exchange.to_perp_symbol(pos["exchange_perp"], symbol)
        try:
            spot_price, perp_price = await self.exchange.close_position(
                symbol=symbol,
                spot_exchange=pos["exchange_spot"],
                perp_exchange=pos["exchange_perp"],
                spot_size=pos["spot_size"],
                perp_symbol=perp_sym,
            )
        except Exception as exc:
            logger.error("Failed to close position %s (id=%d): %s", symbol, pos_id, exc)
            return

        # Use entry prices as fallback for P&L calculation
        if not spot_price:
            spot_price = pos["entry_spot_price"]
        if not perp_price:
            perp_price = pos["entry_perp_price"]

        funding_collected = pos.get("total_funding_collected", 0.0)
        perp_pnl = (pos["entry_perp_price"] - perp_price) * pos["perp_size"]
        spot_pnl = (spot_price - pos["entry_spot_price"]) * pos["spot_size"]
        pnl = funding_collected + perp_pnl + spot_pnl

        await self.db.close_position(pos_id, spot_price, perp_price, reason, pnl)
        await self.db.log_trade(
            symbol=symbol,
            action="close",
            spot_exchange=pos["exchange_spot"],
            perp_exchange=pos["exchange_perp"],
            spot_price=spot_price,
            perp_price=perp_price,
            size_usdc=pos["spot_size"] * pos["entry_spot_price"],
            reason=reason,
            pnl=pnl,
            paper_mode=cfg.paper_mode,
        )
        self.risk.register_closed()
        self.risk.update_pnl(pnl)
        self.dash_state.balance = await self.exchange.get_balance()

        logger.info(
            "Position closed: %s | funding=%.4f | basis_pnl=%.4f | total_pnl=%.4f",
            symbol, funding_collected, perp_pnl + spot_pnl, pnl,
        )

        if self.notifier:
            pnl_emoji = "🟢" if pnl >= 0 else "🔴"
            await self.notifier.send(
                f"{pnl_emoji} <b>Position Closed</b>\n"
                f"Symbol: {symbol}\n"
                f"Reason: {reason}\n"
                f"Funding Collected: ${funding_collected:.4f}\n"
                f"Total P&L: ${pnl:.4f}"
            )

    # ------------------------------------------------------------------
    # Main run loop
    # ------------------------------------------------------------------

    async def run(self) -> None:
        await self.start()

        loop = asyncio.get_running_loop()
        stop_event = asyncio.Event()

        def _handle_signal(sig: signal.Signals) -> None:
            logger.info("Received signal %s – shutting down", sig.name)
            stop_event.set()

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, _handle_signal, sig)

        tasks = [
            asyncio.create_task(self.funding_scanner_task(), name="scanner"),
            asyncio.create_task(self.position_monitor_task(), name="monitor"),
            asyncio.create_task(self.funding_payment_task(), name="payments"),
            asyncio.create_task(self.daily_reset_task(), name="daily_reset"),
        ]
        if self._show_dashboard:
            tasks.append(asyncio.create_task(self.dashboard_task(), name="dashboard"))

        # Wait for stop signal
        try:
            await stop_event.wait()
        except asyncio.CancelledError:
            pass
        finally:
            logger.info("Cancelling tasks...")
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.stop()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Funding Rate Arbitrage Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python bot.py                         # Paper mode (default, safe)
  python bot.py --live --confirm --yes  # Live trading (all 3 flags required)
  python bot.py --no-dashboard          # Paper mode, no Rich TUI
""",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Enable live trading (requires --confirm and --yes)",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm intent to trade with real money",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Final confirmation for live trading",
    )
    parser.add_argument(
        "--no-dashboard",
        action="store_true",
        help="Disable the Rich TUI dashboard (use plain log output)",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()

    live_mode = False
    if args.live:
        if not (args.confirm and args.yes):
            print(
                "\n[ERROR] Live trading requires ALL THREE flags: --live --confirm --yes\n"
                "This safety requirement protects against accidental live execution.\n"
            )
            sys.exit(1)
        if cfg.paper_mode:
            print(
                "\n[ERROR] PAPER_MODE=True in your config/env.\n"
                "Set PAPER_MODE=False in .env to enable live trading.\n"
            )
            sys.exit(1)
        print(
            "\n⚠️  LIVE MODE ACTIVATED – real funds will be used.\n"
            "Starting in 5 seconds. Press Ctrl+C to abort.\n"
        )
        await asyncio.sleep(5)
        live_mode = True

    show_dashboard = not args.no_dashboard
    bot = FundingRateBot(live_mode=live_mode, show_dashboard=show_dashboard)
    await bot.run()


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        print("\nInterrupted by user.")


if __name__ == "__main__":
    main()
