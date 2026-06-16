# Polymarket Edge Bot — V1 Paper Trading Scanner

Read-only scanner and paper trader for Polymarket crypto Up/Down markets.
**No live trading. No private keys. No paid APIs required.**

---

## What it actually does

Scans Polymarket for short-term BTC/ETH/SOL prediction markets, computes a
fair-value probability using a log-normal price model, compares it to the
live order book ask price, and paper-trades opportunities where the adjusted
edge exceeds a configurable threshold.

Every scan cycle is saved to SQLite. After 1–2 weeks of running you will
have real data on whether the edge hypothesis holds.

---

## Honest limitations

- **You cannot backtest this strategy on historical data** — Polymarket has
  no public historical order book API. V1 is a data collection engine.
- Paper fills are optimistic. Real fills will be harder to obtain.
- The fair value model is a simple log-normal approximation, not an oracle.
- Edge estimates include a built-in cost deduction (delay + slippage +
  safety margin). Even so, treat paper results with skepticism.

---

## Setup

```bash
# 1. Create folder and virtualenv
mkdir -p ~/polymarket_edge_bot
cd ~/polymarket_edge_bot

# 2. Copy project files here (or clone repo)

# 3. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Copy and edit config
cp config.example.json config.json
# Edit config.json — adjust thresholds as needed
```

---

## Run

```bash
# Activate venv first
source .venv/bin/activate

# List active crypto markets (no trading)
python main.py markets

# Start continuous paper scanner (Ctrl+C to stop)
python main.py scan

# Single scan cycle (useful for testing)
python main.py scan --once

# Show paper trading stats
python main.py stats

# Replay last 48h of snapshots
python main.py replay --hours 48

# Verbose debug output
python main.py scan --verbose
```

---

## Sample terminal output

```
08:30:01 INFO    POLYMARKET EDGE SCANNER — PAPER MODE
08:30:01 INFO    symbols=['BTC', 'ETH', 'SOL'] interval=30s
08:30:01 INFO
08:30:01 INFO    [08:30:01 UTC] SCAN #1
08:30:02 INFO      Fetched 87 raw markets from Gamma API
08:30:03 INFO      14 matching crypto Up/Down markets
08:30:03 INFO    -----------------------------------------------------------------
08:30:03 INFO      *** SIGNAL: PAPER_TRADE ***
08:30:03 INFO      Question : Will Bitcoin close above $107,500 by 4PM today?
08:30:03 INFO      Market   : BTC absolute_strike direction=above target=107500.0
08:30:03 INFO      Expiry   : 2026-06-16 16:00 UTC (in 462m)
08:30:03 INFO      Outcome  : YES @ $0.4100 ask | fair=0.5213 | raw_edge=+11.13% adj_edge=+8.63%
08:30:03 INFO      Ref price: $107,231.50 (kraken, 2s old)
08:30:03 INFO      Vol      : 68% ann  | momentum=+0.0124%/min
08:30:03 INFO      Liquidity: $3,420  | ob_age=1s | confidence=0.72
08:30:03 INFO    -----------------------------------------------------------------
08:30:03 INFO      PAPER OPEN  YES | Will Bitcoin close above $107,500 by 4PM today? | price=0.4100 fv=0.5213 edge=8.6% size=$50
08:30:03 INFO    -----------------------------------------------------------------
08:30:04 INFO      WATCH    | Will ETH be above $3,800 this week? | edge=2.1% (threshold 4.0%)
08:30:04 INFO      Cycle complete — signals_this_cycle=1 total_signals=1 open_positions=1 equity=$950.00
```

---

## Config reference

| Key | Default | Description |
|-----|---------|-------------|
| polling_interval_seconds | 30 | Seconds between scans |
| min_edge_pct | 0.04 | Minimum adjusted edge to paper trade (4%) |
| min_fair_value_confidence | 0.55 | Minimum model confidence |
| min_liquidity_usd | 500 | Skip illiquid markets |
| max_spread | 0.08 | Skip wide-spread markets (8%) |
| paper_position_size_usd | 50 | Paper trade size in USD |
| max_trades_per_hour | 20 | Rate limit |
| max_daily_loss_usd | 200 | Daily loss kill switch |

---

## Kill switch

Create a file named `STOP` in the project directory. The scanner will halt
all new trades immediately on the next cycle.

```bash
touch STOP       # halt
rm STOP          # resume
```

---

## Data

- `data/edge_bot.db` — SQLite database with all snapshots, signals, trades
- `data/raw_samples/` — Raw API responses saved on first fetch (for debugging)
- `logs/YYYY-MM-DD.log` — Daily log files

---

## Project structure

```
main.py                 CLI entry point
scanner.py              Main scan loop
polymarket_client.py    Gamma + CLOB API client
crypto_price_client.py  BTC/ETH/SOL reference prices
fair_value.py           Log-normal fair value model
paper_trader.py         Paper position management
risk.py                 Pre-trade risk checks
storage.py              SQLite persistence
replay.py               Snapshot replay and stats
live_trader.py          PLACEHOLDER — not implemented
config.example.json     Configuration reference
requirements.txt        Python dependencies
```

---

## Next steps after 2 weeks of data

1. Run `python main.py stats` and `python main.py replay`
2. Look at: win rate by edge bucket, by expiry bucket, by time of day
3. Check: does paper win rate correlate with model edge?
4. Check: are wins concentrated in high-confidence signals?
5. Only if evidence is compelling: begin designing live execution (separate module)
