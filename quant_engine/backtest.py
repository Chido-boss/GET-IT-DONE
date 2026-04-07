"""
backtest.py — Offline historical backtester.

Usage:
    python backtest.py                           # BTC/1h, last 1000 candles
    python backtest.py --symbol ETHUSDT --candles 2000
    python backtest.py --interval 4h --candles 500
    python backtest.py --show-trades             # print every trade

Output:
    Total return, CAGR, win rate, profit factor, max drawdown, Sharpe ratio
"""

from __future__ import annotations
import argparse
import math
from datetime import datetime, timezone
from typing import Optional

from config import cfg, Config
from data import fetch_candles_since
from indicators import compute
from strategy import generate, check_exit
from risk import RiskManager


# ── Backtest engine ────────────────────────────────────────────────────────────

class BacktestResult:
    def __init__(self) -> None:
        self.trades: list[dict] = []
        self.equity_curve: list[float] = []
        self.starting_equity: float = 0.0
        self.ending_equity: float = 0.0
        self.n_candles: int = 0

    # ── Metrics ───────────────────────────────────────────────────────────────

    @property
    def total_return_pct(self) -> float:
        if self.starting_equity <= 0:
            return 0.0
        return (self.ending_equity - self.starting_equity) / self.starting_equity * 100

    @property
    def n_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        wins = sum(1 for t in self.trades if t["pnl"] > 0)
        return wins / len(self.trades) * 100

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t["pnl"] for t in self.trades if t["pnl"] > 0)
        gross_loss   = abs(sum(t["pnl"] for t in self.trades if t["pnl"] < 0))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def sharpe_ratio(self) -> float:
        """
        Simplified Sharpe using per-trade returns (not time-series).
        Annualised assuming ~3 trades per month = 36/year.
        """
        if len(self.trades) < 2:
            return 0.0
        returns = [t["pnl"] / t["size_usd"] for t in self.trades if t["size_usd"] > 0]
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        var_r  = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_r  = math.sqrt(var_r) if var_r > 0 else 1e-9
        trades_per_year = 36  # rough estimate
        return (mean_r / std_r) * math.sqrt(trades_per_year)

    @property
    def avg_win(self) -> float:
        wins = [t["pnl"] for t in self.trades if t["pnl"] > 0]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t["pnl"] for t in self.trades if t["pnl"] < 0]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def expectancy(self) -> float:
        """Average PnL per trade in USD."""
        if not self.trades:
            return 0.0
        return sum(t["pnl"] for t in self.trades) / len(self.trades)

    # ── Report ────────────────────────────────────────────────────────────────

    def print_report(self, show_trades: bool = False) -> None:
        sep = "─" * 60
        print(f"\n{sep}")
        print(f"  BACKTEST RESULTS — {cfg.symbol} {cfg.interval}")
        print(sep)
        print(f"  Candles tested:     {self.n_candles}")
        print(f"  Starting equity:    ${self.starting_equity:,.2f}")
        print(f"  Ending equity:      ${self.ending_equity:,.2f}")
        print(f"  Total return:       {self.total_return_pct:+.2f}%")
        print(f"  Total trades:       {self.n_trades}")
        print(f"  Win rate:           {self.win_rate:.1f}%")
        print(f"  Profit factor:      {self.profit_factor:.2f}")
        print(f"  Max drawdown:       {self.max_drawdown_pct:.2f}%")
        print(f"  Sharpe ratio:       {self.sharpe_ratio:.2f}")
        print(f"  Expectancy/trade:   ${self.expectancy:,.2f}")
        print(f"  Avg win:            ${self.avg_win:,.2f}")
        print(f"  Avg loss:           ${self.avg_loss:,.2f}")
        print(sep)

        if show_trades and self.trades:
            print(f"\n  {'#':>4}  {'Dir':5}  {'Entry':>10}  {'Exit':>10}  "
                  f"{'Size':>10}  {'P&L':>10}  {'Reason'}")
            print("  " + "─" * 72)
            for i, t in enumerate(self.trades, 1):
                sign = "+" if t["pnl"] >= 0 else ""
                print(
                    f"  {i:>4}  {t['direction']:5}  "
                    f"{t['entry_price']:>10.2f}  {t['exit_price']:>10.2f}  "
                    f"${t['size_usd']:>9.2f}  "
                    f"{sign}${t['pnl']:>8.2f}  {t['reason']}"
                )
            print()


# ── Runner ────────────────────────────────────────────────────────────────────

def run_backtest(cfg: Config, n_candles: int) -> BacktestResult:
    print(f"Fetching {n_candles} candles for {cfg.symbol} {cfg.interval}...")
    candles = fetch_candles_since(cfg.symbol, cfg.interval, n_candles)
    if len(candles) < 60:
        raise RuntimeError(f"Only {len(candles)} candles returned — need at least 60")
    print(f"Fetched {len(candles)} candles. Running simulation...")

    risk   = RiskManager(cfg)
    result = BacktestResult()
    result.starting_equity = cfg.starting_equity
    result.n_candles = len(candles)

    equity         = cfg.starting_equity
    position       = None      # dict or None
    bars_since_exit = 9999

    for i in range(len(candles)):
        # Build a rolling window up to bar i
        window = candles[: i + 1]
        if len(window) < 2:
            result.equity_curve.append(equity)
            continue

        inds = compute(window, cfg)
        if inds is None:
            result.equity_curve.append(equity)
            continue

        price = inds["price"]
        sig   = generate(inds, cfg, bars_since_exit)

        # ── Exit check ────────────────────────────────────────────────────────
        if position is not None:
            should_exit, reason = check_exit(position, price, sig)
            if should_exit:
                # Apply slippage + commission
                if position["direction"] == "long":
                    exit_price = price * (1.0 - cfg.slippage_pct)
                else:
                    exit_price = price * (1.0 + cfg.slippage_pct)

                pnl = risk.realized_pnl(
                    direction      = position["direction"],
                    entry_price    = position["entry_price"],
                    exit_price     = exit_price,
                    size_usd       = position["size_usd"],
                    slippage_pct   = 0.0,
                    commission_pct = cfg.commission_pct,
                )
                equity += pnl
                result.trades.append({
                    "bar":         i,
                    "direction":   position["direction"],
                    "entry_price": position["entry_price"],
                    "exit_price":  exit_price,
                    "size_usd":    position["size_usd"],
                    "pnl":         round(pnl, 4),
                    "reason":      reason,
                })
                position = None
                bars_since_exit = 0

        # ── Entry check ───────────────────────────────────────────────────────
        if position is None and sig.direction is not None:
            # Apply entry slippage
            if sig.direction == "long":
                entry_price = price * (1.0 + cfg.slippage_pct)
            else:
                entry_price = price * (1.0 - cfg.slippage_pct)

            size_usd = risk.position_size_usd(equity, entry_price, inds["atr"])
            sl = risk.stop_loss(sig.direction, entry_price, inds["atr"])
            tp = risk.take_profit(sig.direction, entry_price, inds["atr"])

            position = {
                "direction":   sig.direction,
                "entry_price": entry_price,
                "size_usd":    size_usd,
                "stop_loss":   sl,
                "take_profit": tp,
                "entry_bar":   i,
            }
        elif position is None:
            bars_since_exit = min(bars_since_exit + 1, 9999)

        result.equity_curve.append(equity)

    # Force-close any open position at last price
    if position is not None:
        last_price = candles[-1]["close"]
        pnl = risk.realized_pnl(
            position["direction"], position["entry_price"], last_price,
            position["size_usd"], cfg.slippage_pct, cfg.commission_pct
        )
        equity += pnl
        result.trades.append({
            "bar":         len(candles) - 1,
            "direction":   position["direction"],
            "entry_price": position["entry_price"],
            "exit_price":  last_price,
            "size_usd":    position["size_usd"],
            "pnl":         round(pnl, 4),
            "reason":      "end_of_data",
        })

    result.ending_equity = round(equity, 4)
    return result


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Quant Engine Backtester")
    p.add_argument("--symbol",   default=cfg.symbol,            help="e.g. ETHUSDT")
    p.add_argument("--interval", default=cfg.interval,           help="e.g. 1h 4h 1d")
    p.add_argument("--candles",  type=int, default=cfg.backtest_candles, help="Number of candles")
    p.add_argument("--show-trades", action="store_true",         help="Print every trade")
    args = p.parse_args()

    cfg.symbol   = args.symbol
    cfg.interval = args.interval

    result = run_backtest(cfg, args.candles)
    result.print_report(show_trades=args.show_trades)


if __name__ == "__main__":
    main()
