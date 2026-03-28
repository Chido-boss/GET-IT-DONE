# Portfolio Pitch — Polymarket Latency Arbitrage Bot

Use this as your **Upwork portfolio description**, **LinkedIn post**, **direct outreach**, or **Twitter thread**.

---

## The 60-Second Pitch (for clients)

> I built a production-grade automated trading system in Python that monitors Polymarket (prediction markets) for pricing inefficiencies against Binance real-time data.
>
> The system processes live price feeds via WebSocket, calculates multi-factor edge scores using momentum, volume, and orderbook data, manages risk automatically, and sends real-time Telegram alerts — all running asynchronously with zero downtime.
>
> This is the kind of system I build for clients.

---

## Technical Breakdown (for technical clients / CTOs)

### Architecture
- **Async Python** (asyncio) — single event loop, multiple coordinated tasks
- **Real-time data ingestion** — Binance WebSocket for BTC/ETH price feeds
- **Prediction market client** — Polymarket CLOB API + Gamma API integration
- **Edge detection engine** — multi-factor confidence scoring model
- **Risk management layer** — Kelly criterion position sizing, daily loss limits, drawdown kill switch
- **Persistent storage** — SQLite via aiosqlite (non-blocking)
- **Live dashboard** — Rich terminal UI with real-time state updates
- **Alert system** — Telegram bot integration for trade signals and P&L updates
- **Graceful shutdown** — SIGINT/SIGTERM handling, position cleanup

### Intelligence Layer
```
Inputs:
  - 30s price change % on BTC/ETH
  - Velocity ($/sec)
  - Acceleration ($/sec²)
  - Volume ratio vs. 24hr average
  - Orderbook depth and imbalance

Model:
  - Sigmoid-based CEX implied probability
  - ATR-adaptive lag threshold
  - Multi-factor confidence: momentum(30%) + volume(25%) + edge(25%) + time(20%)
  - Deduplication within 500ms windows

Output:
  - EdgeResult with direction, edge%, confidence, liquidity flag
  - Tradeable if edge > 5%, confidence > 85%, liquidity ok, >60s to expiry
```

### Risk Controls
- Max position: 8% of portfolio per trade
- Daily loss limit: 20%
- Per-asset loss limit: 10%
- Total drawdown kill: 40% (shuts down and alerts)
- Three-flag system required to enable live trading (prevents accidental activation)

### Lines of Code
| Module | Lines | Purpose |
|---|---|---|
| `bot.py` | 869 | Main orchestrator, asyncio event loop |
| `polymarket_client.py` | 602 | Polymarket API client |
| `edge_calculator.py` | 404 | Core signal generation |
| `database.py` | 387 | SQLite persistence layer |
| `dashboard.py` | 366 | Real-time terminal UI |
| `binance_feed.py` | 326 | WebSocket price feed |
| `risk_manager.py` | 319 | Position sizing & limits |
| `telegram_alerts.py` | 204 | Alert delivery |
| `config.py` | 188 | Environment-based config |
| **Total** | **3,665** | Production-ready |

---

## What This Demonstrates to Clients

| Skill | Evidence |
|---|---|
| Production Python | asyncio, type hints, dataclasses, proper logging |
| Financial systems | Kelly criterion, ATR, orderbook analysis, risk management |
| Real-time data | WebSocket feeds, sub-second latency handling |
| API integration | REST + WebSocket, auth, error handling |
| Database design | SQLite schema, async queries, historical records |
| System design | Event-driven architecture, graceful shutdown, config management |
| DevOps awareness | .env secrets management, logging levels, paper/live modes |

---

## How to Use This on Upwork

**Portfolio image:** Screenshot of the Rich dashboard running (paper mode, real-time P&L, positions table)

**Project description:**
```
Polymarket Latency Arbitrage Bot — Python/asyncio

Built a production-grade automated trading system that detects pricing
inefficiencies between Binance (centralized exchange) and Polymarket
(decentralized prediction market).

Tech: Python 3.11, asyncio, WebSockets, SQLite, REST APIs, Telegram Bot API,
Rich terminal UI

Features:
• Real-time BTC/ETH price feeds via Binance WebSocket
• Multi-factor edge detection with adaptive thresholds
• Kelly criterion position sizing with full risk management
• Live terminal dashboard + Telegram alerts
• Paper trading mode for strategy validation
• 3,665 lines of production code across 9 modules

This system runs continuously, handles network interruptions gracefully,
and has processed thousands of market evaluations in paper testing.
```

---

## Twitter Thread Hook (Build in Public)

```
Thread: I built a Polymarket latency arb bot in Python 🧵

Polymarket trades on predictions. Binance trades on crypto prices.
When crypto moves fast, Polymarket is slow to update.

That's the gap I built a bot to exploit.

Here's the full architecture 👇

1/ The core idea:
BTC pumps 2% in 30 seconds on Binance.
Polymarket's "BTC above X by 4pm" market still shows 45% YES.
Real probability? Closer to 70%.

That's your edge.

2/ The signal engine uses:
- Price velocity ($/second)
- Acceleration
- Volume ratio vs 24hr average
- Orderbook depth
- ATR-adaptive thresholds

Combined into a 0–1 confidence score.

3/ Risk management:
- Kelly criterion sizing (half-Kelly for safety)
- 8% max position size
- 20% daily loss kill switch
- 40% total drawdown = emergency shutdown

Built so it CAN'T blow up silently.

4/ Tech stack:
- Python asyncio (single event loop, no threading)
- WebSockets for Binance feed
- SQLite for persistence
- Rich for terminal dashboard
- Telegram for alerts

5/ Paper trading results are promising.
Now looking for partners with capital to run this live.

DMs open if you trade on Polymarket. 🎯
```

---

## Direct Outreach Template (LinkedIn / Discord)

**For prediction market traders:**
```
Hey [Name],

I see you're active on Polymarket. I'm a Python developer based in Gateshead, UK.

I just finished building a latency arbitrage bot that monitors Polymarket for
price lags vs. Binance real-time data. It's been running in paper mode for [X weeks]
and flagging interesting opportunities.

Would you be open to a 15-minute call to discuss a potential rev-share arrangement?
You'd provide the capital and Polymarket account; I provide the system and host it.

Happy to walk you through the architecture.

Best,
[Your name]
```

**For crypto startups (Upwork/LinkedIn):**
```
Hi [Name],

I noticed you're [hiring/building] in the crypto trading space.

I recently built a production-grade trading system for Polymarket in Python —
3,600+ lines covering real-time WebSocket feeds, multi-factor signal generation,
risk management, and Telegram alerts.

If you need Python automation, API integrations, or trading infrastructure built,
I'd love to help. I typically deliver faster than quoted.

Happy to share code samples or hop on a quick call.

[Your name]
```

---

*This is your most powerful selling tool. Lead every pitch with it.*
