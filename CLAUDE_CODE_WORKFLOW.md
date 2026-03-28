# Claude Code Workflow — 3–5x Speed Multiplier for Client Work

How to use Claude Code to deliver client projects faster than any competitor.

---

## The Core Principle

> Claude Code doesn't replace your skill. It removes the repetitive parts so you can focus on the parts that require your brain.

You still:
- Architect the solution
- Make judgment calls
- Review and test output
- Handle edge cases
- Communicate with clients

Claude Code handles:
- Scaffolding boilerplate
- Writing repetitive modules (DB layer, config, logging setup)
- Generating tests
- Writing documentation
- Refactoring for consistency
- Finding bugs in code you're reviewing

---

## Workflow 1: New Client Project (Telegram Bot Example)

**Client says:** "I want a Telegram bot that monitors my Binance portfolio and alerts me when any coin drops more than 5% in an hour."

**Old way:** 8–12 hours

**Claude Code way:**

```
Step 1 (5 min): Write a full spec in your head, then tell Claude Code:

"Build a Python Telegram bot with the following:
- Polls Binance REST API every 5 minutes for portfolio balances
- Tracks price of each coin over rolling 1hr window
- Sends Telegram alert if any coin drops >5% in that window
- Config via .env file (TELEGRAM_TOKEN, CHAT_ID, BINANCE_API_KEY, BINANCE_SECRET)
- Uses python-telegram-bot library and python-binance
- SQLite to store price history
- Proper logging with file + console handlers
- Graceful shutdown on SIGINT
- requirements.txt included"

Step 2 (20 min): Claude Code generates all files. You read through them.

Step 3 (30 min): Set up test environment, run it, fix anything that doesn't work.

Step 4 (15 min): Add any client-specific tweaks.

Total: ~70 minutes vs. 8 hours
```

**You deliver in 24hrs, competitor takes 2 weeks. You charge the same £500.**

---

## Workflow 2: Inheriting Client's Existing Codebase

Client has a messy existing codebase and wants features added.

```
Step 1: Read the entire codebase into Claude Code context

Step 2: Ask Claude Code to explain the architecture:
"Summarise what this codebase does, its main components, and any obvious issues."

Step 3: Before touching anything, ask:
"What are the risks of adding [feature X] to this codebase?"

Step 4: Ask for implementation plan:
"How would you add [feature] with minimal changes to existing code?"

Step 5: Implement with Claude Code generating the specific changes
```

Time to understand unfamiliar codebase: **30 mins** vs. **2 days**

---

## Workflow 3: Code Auditing (High-Value Service, £500–£2000)

Clients with existing bots/systems will pay for security and performance audits.

```
"Review this codebase for:
1. Security vulnerabilities (hardcoded secrets, injection risks, auth issues)
2. Performance bottlenecks
3. Unhandled exceptions that could cause silent failures
4. Race conditions or concurrency issues
5. Memory leaks or resource exhaustion
Give me a prioritised list with severity ratings and fix recommendations."
```

You review the output, add your judgment, deliver a PDF report. 3–4 hours work, charge £750–£1500.

---

## Workflow 4: SaaS Feature Development

For your own products, use Claude Code as your co-founder.

**Sprint workflow:**
```
Monday: Define the feature clearly
  "I need to add Stripe subscription billing to my FastAPI app.
   Users should be able to subscribe at £9.99/month or £29.99/month.
   Current stack: FastAPI, SQLite, Jinja2 templates, deployed on Railway."

Claude Code scaffolds:
- Stripe webhook endpoint
- Subscription model in DB
- Middleware to check subscription status
- Billing portal redirect
- Upgrade/downgrade flow

Tuesday: Integrate, test with Stripe test mode
Wednesday: Fix edge cases, write tests
Thursday: Deploy
Friday: Monitor, fix bugs
```

One developer shipping like a team of 3.

---

## Workflow 5: Rapid Prototyping for Client Demos

Before writing a proposal, build a prototype to win the deal.

```
Client meeting on Monday.
You want to show up Tuesday with a working demo.

That evening:
1. Define the core 20% that demonstrates the value
2. Claude Code scaffolds it in 1–2 hours
3. Polish the UI just enough
4. Deploy to Railway or Render (5 min, free)

Client sees working software on Day 2.
Competitors send a written proposal.

You get the contract.
```

---

## Workflow 6: Documentation (Clients Love This, Most Devs Skip It)

```
"Generate comprehensive documentation for this codebase including:
- Project overview
- Architecture diagram (as ASCII or Mermaid)
- Setup instructions
- Configuration reference (all .env variables)
- API reference for each public function
- Deployment guide for Railway/Render/VPS"
```

Takes 15 minutes. Adds perceived value. Justifies higher rate.
Clients who get proper docs come back for more work.

---

## What Claude Code is NOT Good For

Be honest about limitations:

- **Novel algorithm design** — you need to architect new approaches yourself
- **Domain expertise** — understanding WHAT to build for a niche (financial, medical, legal)
- **Client communication** — that's your relationship
- **Production debugging** — for complex runtime issues, you still need to think
- **Security-critical systems** — always review output carefully, especially auth/crypto code

---

## Rate Setting Strategy

Your time = (output / hours) × quality

Claude Code increases output per hour dramatically.

**Rate progression:**
```
Month 1:   £60/hr  → establish presence, get reviews
Month 2-3: £80/hr  → after 5+ good reviews
Month 4-6: £100/hr → after first £10k month
Month 6+:  £120-150/hr → specialist reputation established
```

**Fixed price vs. hourly:**
- Fixed price for well-defined projects (you benefit from speed)
- Hourly for vague/evolving projects (protects you)

**The speed advantage on fixed price:**
- Client pays £1,500 for a trading bot
- You deliver in 15 hours (with Claude Code) vs. 40 hours (without)
- Effective rate: £100/hr vs. £37.50/hr
- Same revenue, more projects, happier clients

---

## Building Your Reputation Stack

In order of impact:

1. **Upwork JSS (Job Success Score)** — every job you complete builds this. 90%+ opens doors.
2. **GitHub public repos** — your bot project, cleaned up, is your calling card
3. **Twitter presence** — "build in public" posts showing real work
4. **LinkedIn** — for B2B / startup clients
5. **Testimonials** — ask every satisfied client for a written testimonial

---

## The 90-Day Target

```
Week 1-2:   First client (even at low rate to build reviews)
Week 3-4:   First £1,000 month
Month 2:    £2,000-3,000 month, 3+ Upwork reviews
Month 3:    £4,000-5,000 month, rate increase to £80/hr
            Start building SaaS product on the side
```

The compounding effect: each good review → better proposals → higher rates → more selective → better clients → higher rates.

---

*Claude Code is a tool. Your judgment, reliability, and communication are the product.*
