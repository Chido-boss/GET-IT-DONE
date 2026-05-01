"""
funding_extremes_backtest.py — Funding Rate Extremes Reversal

Strategy  : Counter-trend entry when funding hits 5th/95th rolling percentile
            (90-day window) with 2 consecutive extreme observations required.
Exits     : Funding normalises past 40th/60th percentile, 3% SL, or 72h time exit.
Data      : Kraken Futures API (funding) + Kraken Spot OHLC (1h bars).
"""

from __future__ import annotations
import bisect
import json
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone


# ── Config ─────────────────────────────────────────────────────────────────────

FUTURES_SYMBOL   = "PI_XBTUSD"
SPOT_PAIR        = "XBTUSD"
STARTING_EQUITY  = 10_000.0
RISK_PCT         = 0.01          # fraction of equity risked per trade
STOP_PCT         = 0.03          # 3% price stop loss
WINDOW_DAYS      = 90            # rolling percentile window
LOW_PCTILE       = 5             # extreme low → go long
HIGH_PCTILE      = 95            # extreme high → go short
EXIT_LOW_PCTILE  = 40            # normalization exit threshold for longs
EXIT_HIGH_PCTILE = 60            # normalization exit threshold for shorts
CONSEC_REQUIRED  = 2             # consecutive extremes before entry
TIME_EXIT_HOURS  = 72            # max hours in a trade


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _get(url: str) -> dict | list:
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "funding-bt/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"Request failed after 4 attempts: {exc}") from exc
            time.sleep(2 ** attempt)
    return {}


# ── Timestamp helpers ──────────────────────────────────────────────────────────

def _parse_ts(ts_str: str) -> datetime:
    s = ts_str.rstrip("Z")
    if "." in s:
        s = s.split(".")[0]
    dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S")
    return dt.replace(tzinfo=timezone.utc)


def _snap_hour(dt: datetime) -> datetime:
    return dt.replace(minute=0, second=0, microsecond=0)


# ── Data fetching ──────────────────────────────────────────────────────────────

def fetch_funding_rates() -> list[dict]:
    """
    Fetch all historical funding rates for PI_XBTUSD from Kraken Futures.
    Returns list of {ts: datetime, rate: float} sorted oldest-first.
    """
    url = ("https://futures.kraken.com/derivatives/api/v3/historicalfundingrates"
           "?symbol=" + FUTURES_SYMBOL)
    data = _get(url)
    rates = []
    for row in data.get("rates", []):
        rates.append({"ts": _parse_ts(row["timestamp"]), "rate": float(row["fundingRate"])})
    rates.sort(key=lambda r: r["ts"])
    return rates


def fetch_ohlc(n_candles: int = 2000) -> list[dict]:
    """
    Fetch hourly OHLC from Kraken Spot for XBTUSD.
    Returns list of {ts, open, high, low, close} sorted oldest-first.
    """
    since = int(time.time()) - (n_candles + 50) * 3600
    url = ("https://api.kraken.com/0/public/OHLC?"
           + urllib.parse.urlencode({"pair": SPOT_PAIR, "interval": 60, "since": since}))
    data = _get(url)
    if data.get("error"):
        raise RuntimeError(f"Kraken OHLC error: {data['error']}")
    result   = data["result"]
    pair_key = next(k for k in result if k != "last")
    candles  = []
    for k in result[pair_key]:
        ts = datetime.fromtimestamp(int(k[0]), tz=timezone.utc)
        candles.append({
            "ts":    ts,
            "open":  float(k[1]),
            "high":  float(k[2]),
            "low":   float(k[3]),
            "close": float(k[4]),
        })
    return candles[:-1]  # drop last incomplete candle


# ── Rolling percentile ─────────────────────────────────────────────────────────

def _percentile(sorted_vals: list[float], p: float) -> float:
    """Linear interpolation percentile on a pre-sorted list. p in [0, 100]."""
    n = len(sorted_vals)
    if n == 0:
        return 0.0
    if n == 1:
        return sorted_vals[0]
    idx = p / 100.0 * (n - 1)
    lo  = int(idx)
    hi  = lo + 1
    if hi >= n:
        return sorted_vals[-1]
    return sorted_vals[lo] + (idx - lo) * (sorted_vals[hi] - sorted_vals[lo])


def build_window_fn(rates: list[dict]):
    """Returns window(i) → sorted funding rates within WINDOW_DAYS of rates[i]."""
    f_unix = [r["ts"].timestamp() for r in rates]
    f_vals = [r["rate"] for r in rates]

    def window(i: int) -> list[float]:
        cutoff = f_unix[i] - WINDOW_DAYS * 86400
        left   = bisect.bisect_left(f_unix, cutoff)
        return sorted(f_vals[left : i + 1])

    return window


# ── P&L helper ─────────────────────────────────────────────────────────────────

def _calc_pnl(position: dict, exit_price: float) -> float:
    sz = position["size_usd"]
    ep = position["entry"]
    if position["direction"] == "long":
        return sz * (exit_price - ep) / ep
    return sz * (ep - exit_price) / ep


# ── Backtest ───────────────────────────────────────────────────────────────────

def run(rates: list[dict], candles: list[dict]) -> tuple[list[dict], float, list[float]]:
    """
    Bar-by-bar simulation.
    Signal at funding observation T → entry at next candle open after T.
    Exits: SL (intra-bar) > time exit (72h) > normalization (at funding times).
    """
    window_fn = build_window_fn(rates)

    # Pre-compute percentile bands for every funding observation
    rate_info: list[dict | None] = []
    for i, fr in enumerate(rates):
        sw = window_fn(i)
        if len(sw) < 10:
            rate_info.append(None)
            continue
        rate_info.append({
            "ts":   fr["ts"],
            "rate": fr["rate"],
            "p5":   _percentile(sw, LOW_PCTILE),
            "p95":  _percentile(sw, HIGH_PCTILE),
            "p40":  _percentile(sw, EXIT_LOW_PCTILE),
            "p60":  _percentile(sw, EXIT_HIGH_PCTILE),
        })

    # Detect signals from consecutive extremes
    signals: list[dict] = []
    consec_long = consec_short = 0
    for ri in rate_info:
        if ri is None:
            continue
        if ri["rate"] <= ri["p5"]:
            consec_long  += 1
            consec_short  = 0
        elif ri["rate"] >= ri["p95"]:
            consec_short += 1
            consec_long   = 0
        else:
            consec_long = consec_short = 0

        if consec_long >= CONSEC_REQUIRED:
            signals.append({"direction": "long",  "signal_ts": ri["ts"]})
            consec_long = 0
        elif consec_short >= CONSEC_REQUIRED:
            signals.append({"direction": "short", "signal_ts": ri["ts"]})
            consec_short = 0

    # Hour-keyed lookup used for normalization exit checks
    rate_lookup: dict[datetime, dict] = {}
    for ri in rate_info:
        if ri is not None:
            rate_lookup[_snap_hour(ri["ts"])] = ri

    # ── Main simulation ───────────────────────────────────────────────────────
    candle_list  = sorted(candles, key=lambda c: c["ts"])
    equity       = STARTING_EQUITY
    equity_curve = [equity]
    position     = None
    pending      = None
    sig_idx      = 0
    trades: list[dict] = []

    for c in candle_list:
        c_ts = c["ts"]

        # Consume signals that fired before this candle
        while sig_idx < len(signals) and signals[sig_idx]["signal_ts"] < c_ts:
            sig = signals[sig_idx]
            sig_idx += 1
            if position is None and pending is None:
                pending = sig   # take the first eligible signal only

        # Execute pending entry at this candle's open
        if pending is not None and position is None:
            ep        = c["open"]
            direction = pending["direction"]
            sl        = ep * (1 - STOP_PCT) if direction == "long" else ep * (1 + STOP_PCT)
            sz        = (equity * RISK_PCT) / STOP_PCT
            position  = {
                "direction": direction,
                "entry":     ep,
                "entry_ts":  c_ts,
                "sl":        sl,
                "size_usd":  sz,
            }
            pending = None

        # Check exits
        if position is not None:
            direction  = position["direction"]
            sl         = position["sl"]
            hours_held = (c_ts - position["entry_ts"]).total_seconds() / 3600
            exit_price = None
            exit_reason = None

            # 1. Stop loss (intra-bar)
            if direction == "long" and c["low"] <= sl:
                exit_price, exit_reason = sl, "stop_loss"
            elif direction == "short" and c["high"] >= sl:
                exit_price, exit_reason = sl, "stop_loss"

            # 2. Time exit
            if exit_price is None and hours_held >= TIME_EXIT_HOURS:
                exit_price, exit_reason = c["close"], "time_exit"

            # 3. Funding normalization (only at funding observation hours)
            if exit_price is None:
                ri = rate_lookup.get(_snap_hour(c_ts))
                if ri is not None:
                    if (direction == "long"  and ri["rate"] >= ri["p40"]) or \
                       (direction == "short" and ri["rate"] <= ri["p60"]):
                        exit_price, exit_reason = c["close"], "normalization"

            if exit_price is not None:
                pnl    = _calc_pnl(position, exit_price)
                equity += pnl
                equity_curve.append(equity)
                trades.append({
                    "direction":  direction,
                    "entry":      position["entry"],
                    "entry_ts":   position["entry_ts"].strftime("%Y-%m-%d %H:%M"),
                    "exit":       round(exit_price, 2),
                    "exit_ts":    c_ts.strftime("%Y-%m-%d %H:%M"),
                    "hours_held": round(hours_held, 1),
                    "reason":     exit_reason,
                    "size_usd":   round(position["size_usd"], 2),
                    "pnl":        round(pnl, 4),
                    "equity":     round(equity, 4),
                })
                position = None

    # Force-close any open position at last candle
    if position is not None:
        last_c     = candle_list[-1]
        exit_price = last_c["close"]
        hours_held = (last_c["ts"] - position["entry_ts"]).total_seconds() / 3600
        pnl        = _calc_pnl(position, exit_price)
        equity    += pnl
        equity_curve.append(equity)
        trades.append({
            "direction":  position["direction"],
            "entry":      position["entry"],
            "entry_ts":   position["entry_ts"].strftime("%Y-%m-%d %H:%M"),
            "exit":       round(exit_price, 2),
            "exit_ts":    last_c["ts"].strftime("%Y-%m-%d %H:%M"),
            "hours_held": round(hours_held, 1),
            "reason":     "end_of_data",
            "size_usd":   round(position["size_usd"], 2),
            "pnl":        round(pnl, 4),
            "equity":     round(equity, 4),
        })

    return trades, equity, equity_curve


# ── Stats ──────────────────────────────────────────────────────────────────────

def max_drawdown_pct(curve: list[float]) -> float:
    peak   = curve[0]
    max_dd = 0.0
    for eq in curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd


# ── Output ─────────────────────────────────────────────────────────────────────

def print_summary(trades: list[dict], final_equity: float, curve: list[float]) -> None:
    n        = len(trades)
    wins     = [t for t in trades if t["pnl"] > 0]
    losses   = [t for t in trades if t["pnl"] <= 0]
    g_profit = sum(t["pnl"] for t in wins)
    g_loss   = abs(sum(t["pnl"] for t in losses))
    total_ret = (final_equity - STARTING_EQUITY) / STARTING_EQUITY * 100
    win_rate  = len(wins) / n * 100 if n else 0.0
    pf        = g_profit / g_loss if g_loss > 0 else float("inf")
    max_dd    = max_drawdown_pct(curve)

    by_dir: dict[str, list] = {"long": [], "short": []}
    by_exit: dict[str, list] = {}
    for t in trades:
        by_dir[t["direction"]].append(t["pnl"])
        by_exit.setdefault(t["reason"], []).append(t["pnl"])

    W   = 72
    sep = "=" * W
    print(f"\n{sep}")
    print(f"  FUNDING RATE EXTREMES REVERSAL  |  PI_XBTUSD  |  1h spot bars")
    print(sep)
    print(f"  Starting equity :  ${STARTING_EQUITY:>12,.2f}")
    print(f"  Ending equity   :  ${final_equity:>12,.2f}")
    print(f"  Total return    :  {total_ret:>+12.2f}%")
    print(f"  Total trades    :  {n:>12}")
    print(f"  Win rate        :  {win_rate:>12.1f}%")
    print(f"  Profit factor   :  {pf:>12.2f}")
    print(f"  Max drawdown    :  {max_dd:>12.2f}%")
    print(sep)
    for d in ("long", "short"):
        ps = by_dir[d]
        if ps:
            wr = sum(1 for p in ps if p > 0) / len(ps) * 100
            print(f"  {d.capitalize():<6} trades   :  {len(ps):>4}   "
                  f"win rate {wr:.1f}%   net ${sum(ps):>+9.2f}")
    print(sep)
    for reason, ps in sorted(by_exit.items()):
        print(f"  Exit [{reason:<16}] :  {len(ps):>4} trades   net ${sum(ps):>+9.2f}")
    print(sep)

    if not trades:
        print("  No trades.\n")
        return

    hdr = (f"\n  {'#':>4}  {'Dir':5}  {'Entry':16}  {'Exit':16}  "
           f"{'Hrs':>5}  {'Reason':<16}  {'P&L':>10}  {'Equity':>12}")
    print(hdr)
    print(f"  {'-' * W}")
    for idx, t in enumerate(trades, 1):
        sign = "+" if t["pnl"] >= 0 else ""
        print(
            f"  {idx:>4}  {t['direction']:5}  "
            f"{t['entry_ts']:16}  {t['exit_ts']:16}  "
            f"{t['hours_held']:>5.1f}  {t['reason']:<16}  "
            f"{sign}${t['pnl']:>8.2f}  ${t['equity']:>10.2f}"
        )
    print()


# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching funding rates for {FUTURES_SYMBOL} from Kraken Futures...")
    rates = fetch_funding_rates()
    print(f"Got {len(rates)} funding rate observations  "
          f"({rates[0]['ts'].strftime('%Y-%m-%d')} "
          f"-> {rates[-1]['ts'].strftime('%Y-%m-%d')})")

    print(f"Fetching hourly OHLC for {SPOT_PAIR} from Kraken Spot...")
    candles = fetch_ohlc(n_candles=2000)
    print(f"Got {len(candles)} 1h candles  "
          f"({candles[0]['ts'].strftime('%Y-%m-%d')} "
          f"-> {candles[-1]['ts'].strftime('%Y-%m-%d')})")

    print("Running backtest...")
    trades, final_equity, curve = run(rates, candles)
    print_summary(trades, final_equity, curve)


if __name__ == "__main__":
    main()
