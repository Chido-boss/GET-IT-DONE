import math
import time
import urllib.request
import urllib.parse
import json

# ── Config ─────────────────────────────────────────────────────────────────────

PAIR             = "XBTUSD"
INTERVAL_MIN     = 60          # 1h in minutes
N_CANDLES        = 1000
STARTING_EQUITY  = 10_000.0
RISK_PCT         = 0.01        # 1% of equity risked per trade
ATR_PERIOD       = 14
ROLL_PERIOD      = 20
COMPRESS_THRESH  = 0.002       # ATR/price < 0.2% = compressed
SL_MULT          = 1.5         # stop loss  = 1.5 × ATR
TP_MULT          = 3.0         # take profit = 3.0 × ATR
TIME_EXIT_BARS   = 10

# ── Data ───────────────────────────────────────────────────────────────────────

def _kraken_get(params: dict) -> dict:
    url = "https://api.kraken.com/0/public/OHLC?" + urllib.parse.urlencode(params)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "breakout-bt/1.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read())
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"Kraken request failed: {exc}") from exc
            time.sleep(2 ** attempt)
    return {}


def fetch_candles(pair: str, interval_min: int, n: int) -> list:
    """
    Paginate Kraken OHLC to collect at least n candles.
    Kraken returns up to 720 candles per call; uses 'last' for next page.
    Returns list of dicts: {time, open, high, low, close, volume}
    """
    # start far enough back to cover n candles plus buffer
    since = int(time.time()) - (n + 100) * interval_min * 60

    seen: dict = {}
    pages = 0
    while True:
        data = _kraken_get({"pair": pair, "interval": interval_min, "since": since})
        if data.get("error"):
            raise RuntimeError(f"Kraken error: {data['error']}")
        result  = data["result"]
        pair_key = next(k for k in result if k != "last")
        batch   = result[pair_key]
        last    = int(result["last"])

        for k in batch:
            ts = int(k[0])
            seen[ts] = {
                "time":   ts,
                "open":   float(k[1]),
                "high":   float(k[2]),
                "low":    float(k[3]),
                "close":  float(k[4]),
                "volume": float(k[6]),
            }

        pages += 1
        if last == since or len(batch) < 2 or pages >= 5:
            break
        since = last

    candles = sorted(seen.values(), key=lambda c: c["time"])
    # drop the last (possibly incomplete) candle
    return candles[:-1]

# ── Indicators ─────────────────────────────────────────────────────────────────

def compute_atr(candles: list, period: int) -> list:
    """Wilder's ATR. Returns list aligned with candles; None until warm-up done."""
    n = len(candles)
    result = [None] * n
    if n < period + 1:
        return result

    trs = []
    for i in range(1, n):
        h, l, pc = candles[i]["high"], candles[i]["low"], candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))

    # seed with simple mean
    result[period] = sum(trs[:period]) / period
    for i in range(period, len(trs)):
        result[i + 1] = (result[i] * (period - 1) + trs[i]) / period

    return result


def rolling_high(candles: list, period: int) -> list:
    """Max of HIGH over the previous `period` bars (not including current bar)."""
    n = len(candles)
    result = [None] * n
    for i in range(period, n):
        result[i] = max(candles[j]["high"] for j in range(i - period, i))
    return result


def rolling_low(candles: list, period: int) -> list:
    """Min of LOW over the previous `period` bars (not including current bar)."""
    n = len(candles)
    result = [None] * n
    for i in range(period, n):
        result[i] = min(candles[j]["low"] for j in range(i - period, i))
    return result

# ── Backtest ───────────────────────────────────────────────────────────────────

def run(candles: list) -> tuple:
    atr_vals = compute_atr(candles, ATR_PERIOD)
    hh_vals  = rolling_high(candles, ROLL_PERIOD)
    ll_vals  = rolling_low(candles, ROLL_PERIOD)

    equity       = STARTING_EQUITY
    equity_curve = [equity]
    position     = None       # dict or None
    pending      = None       # signal waiting to enter next bar open
    trades       = []

    for i in range(len(candles)):
        c   = candles[i]
        atr = atr_vals[i]
        hh  = hh_vals[i]
        ll  = ll_vals[i]

        # ── 1. Execute pending entry at this bar's open ───────────────────────
        if pending is not None and position is None:
            entry_p  = c["open"]
            sig_atr  = pending["atr"]
            direction = pending["direction"]
            sl = entry_p - SL_MULT * sig_atr if direction == "long" else entry_p + SL_MULT * sig_atr
            tp = entry_p + TP_MULT * sig_atr if direction == "long" else entry_p - TP_MULT * sig_atr
            risk_amt = equity * RISK_PCT
            stop_pct = SL_MULT * sig_atr / entry_p
            size_usd = risk_amt / stop_pct if stop_pct > 0 else 0.0
            position = {
                "direction":  direction,
                "entry":      entry_p,
                "entry_bar":  i,
                "sl":         sl,
                "tp":         tp,
                "size_usd":   size_usd,
                "signal_bar": pending["signal_bar"],
            }
            pending = None

        # ── 2. Check exit on open position ────────────────────────────────────
        if position is not None:
            bars_held   = i - position["entry_bar"]
            direction   = position["direction"]
            sl          = position["sl"]
            tp          = position["tp"]
            exit_price  = None
            exit_reason = None

            if direction == "long":
                if c["low"] <= sl and c["high"] >= tp:
                    exit_price, exit_reason = sl, "stop_loss"   # SL takes priority
                elif c["low"] <= sl:
                    exit_price, exit_reason = sl, "stop_loss"
                elif c["high"] >= tp:
                    exit_price, exit_reason = tp, "take_profit"
                elif bars_held >= TIME_EXIT_BARS:
                    exit_price, exit_reason = c["close"], "time_exit"
            else:  # short
                if c["high"] >= sl and c["low"] <= tp:
                    exit_price, exit_reason = sl, "stop_loss"
                elif c["high"] >= sl:
                    exit_price, exit_reason = sl, "stop_loss"
                elif c["low"] <= tp:
                    exit_price, exit_reason = tp, "take_profit"
                elif bars_held >= TIME_EXIT_BARS:
                    exit_price, exit_reason = c["close"], "time_exit"

            if exit_price is not None:
                entry_p  = position["entry"]
                size_usd = position["size_usd"]
                if direction == "long":
                    pnl = size_usd * (exit_price - entry_p) / entry_p
                else:
                    pnl = size_usd * (entry_p - exit_price) / entry_p
                equity += pnl
                trades.append({
                    "bar":       i,
                    "direction": direction,
                    "entry":     entry_p,
                    "exit":      exit_price,
                    "reason":    exit_reason,
                    "bars_held": bars_held,
                    "size_usd":  size_usd,
                    "pnl":       round(pnl, 4),
                    "equity":    round(equity, 4),
                })
                position = None

        equity_curve.append(equity)

        # ── 3. Look for new signal at close (enter next bar) ──────────────────
        if position is not None or pending is not None:
            continue
        if atr is None or hh is None or ll is None:
            continue

        close = c["close"]

        # Compression filter
        if atr / close >= COMPRESS_THRESH:
            continue

        # Breakout
        if close > hh:
            pending = {"direction": "long",  "atr": atr, "signal_bar": i}
        elif close < ll:
            pending = {"direction": "short", "atr": atr, "signal_bar": i}

    # ── Force-close any open position at last bar close ───────────────────────
    if position is not None:
        last_c    = candles[-1]
        exit_price = last_c["close"]
        direction  = position["direction"]
        entry_p    = position["entry"]
        size_usd   = position["size_usd"]
        pnl = (size_usd * (exit_price - entry_p) / entry_p
               if direction == "long"
               else size_usd * (entry_p - exit_price) / entry_p)
        equity += pnl
        trades.append({
            "bar":       len(candles) - 1,
            "direction": direction,
            "entry":     entry_p,
            "exit":      exit_price,
            "reason":    "end_of_data",
            "bars_held": len(candles) - 1 - position["entry_bar"],
            "size_usd":  size_usd,
            "pnl":       round(pnl, 4),
            "equity":    round(equity, 4),
        })
        equity_curve.append(equity)

    return trades, equity, equity_curve

# ── Stats ──────────────────────────────────────────────────────────────────────

def max_drawdown_pct(curve: list) -> float:
    peak = curve[0]
    max_dd = 0.0
    for eq in curve:
        if eq > peak:
            peak = eq
        dd = (peak - eq) / peak * 100
        if dd > max_dd:
            max_dd = dd
    return max_dd

# ── Output ─────────────────────────────────────────────────────────────────────

def print_summary(trades: list, final_equity: float, curve: list) -> None:
    n       = len(trades)
    wins    = [t for t in trades if t["pnl"] > 0]
    losses  = [t for t in trades if t["pnl"] <= 0]
    g_profit = sum(t["pnl"] for t in wins)
    g_loss   = abs(sum(t["pnl"] for t in losses))
    total_ret = (final_equity - STARTING_EQUITY) / STARTING_EQUITY * 100
    win_rate  = len(wins) / n * 100 if n else 0.0
    pf        = g_profit / g_loss if g_loss > 0 else float("inf")
    max_dd    = max_drawdown_pct(curve)

    W = 68
    sep  = "=" * W
    dash = "-" * W
    print(f"\n{sep}")
    print(f"  BREAKOUT BACKTEST  |  XBTUSD 1h  |  Compression + Donchian")
    print(sep)
    print(f"  Starting equity :  ${STARTING_EQUITY:>12,.2f}")
    print(f"  Ending equity   :  ${final_equity:>12,.2f}")
    print(f"  Total return    :  {total_ret:>+12.2f}%")
    print(f"  Total trades    :  {n:>12}")
    print(f"  Win rate        :  {win_rate:>12.1f}%")
    print(f"  Profit factor   :  {pf:>12.2f}")
    print(f"  Max drawdown    :  {max_dd:>12.2f}%")
    print(sep)

    if not trades:
        print("  No trades.\n")
        return

    hdr = (f"  {'#':>4}  {'Dir':5}  {'Entry':>10}  {'Exit':>10}  "
           f"{'Bars':>5}  {'Reason':<12}  {'P&L':>10}  {'Equity':>12}")
    print(f"\n{hdr}")
    print(f"  {dash}")
    for idx, t in enumerate(trades, 1):
        sign = "+" if t["pnl"] >= 0 else ""
        print(
            f"  {idx:>4}  {t['direction']:5}  "
            f"{t['entry']:>10.2f}  {t['exit']:>10.2f}  "
            f"{t['bars_held']:>5}  {t['reason']:<12}  "
            f"{sign}${t['pnl']:>8.2f}  ${t['equity']:>10.2f}"
        )
    print()

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    print(f"Fetching {N_CANDLES}+ candles for {PAIR} (1h) from Kraken...")
    candles = fetch_candles(PAIR, INTERVAL_MIN, N_CANDLES)
    print(f"Got {len(candles)} candles  "
          f"({time.strftime('%Y-%m-%d', time.gmtime(candles[0]['time']))} "
          f"→ {time.strftime('%Y-%m-%d', time.gmtime(candles[-1]['time']))})")
    print("Running backtest...")
    trades, final_equity, curve = run(candles)
    print_summary(trades, final_equity, curve)


if __name__ == "__main__":
    main()
