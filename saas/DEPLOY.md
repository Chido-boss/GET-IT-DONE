# Deploy CryptoWatch to Railway (Free → Paid)

## 5-minute deployment

### 1. Push to GitHub
```bash
git add saas/
git commit -m "Add CryptoWatch SaaS"
git push
```

### 2. Create Railway project
1. Go to railway.app → New Project → Deploy from GitHub repo
2. Select this repo, set root directory to `saas/`
3. Railway auto-detects `railway.toml` and builds with nixpacks

### 3. Set environment variables in Railway dashboard
Copy from `saas/.env.example` and fill in real values:
- `SESSION_SECRET` — generate with: `python -c "import secrets; print(secrets.token_hex(32))"`
- `PW_SALT` — same as above
- `BASE_URL` — your Railway app URL (e.g. `https://cryptowatch.up.railway.app`)
- `HTTPS` — `true`
- `TELEGRAM_BOT_TOKEN` — from @BotFather on Telegram
- Stripe keys (see below)

### 4. Set up Stripe (10 minutes)
1. Create account at stripe.com (free)
2. Dashboard → Products → Add Product
3. Create "Starter" product with £9.99/month recurring price → copy Price ID
4. Create "Pro" product with £24.99/month recurring price → copy Price ID
5. Developers → Webhooks → Add endpoint:
   - URL: `https://your-app.up.railway.app/webhook/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`
6. Copy the webhook signing secret

### 5. Set up Telegram bot (2 minutes)
1. Open Telegram → search @BotFather → `/newbot`
2. Give it a name and username
3. Copy the token → set as `TELEGRAM_BOT_TOKEN`
4. Users connect their own chat IDs via Settings page

### 6. Verify deployment
- Visit your Railway URL — landing page should load
- Register an account
- Go to Settings → add your Telegram chat ID (get from @userinfobot)
- Create a test alert
- Railway logs should show "Alert monitor started"

---

## Railway pricing
- Hobby plan: $5/month → covers a low-traffic SaaS comfortably
- At 10 paying subscribers (£9.99/mo each) = ~£100/mo revenue covers 20x hosting cost
- At 100 subscribers: £1,000/mo revenue, still on $5/mo hosting

## Custom domain
Railway → Settings → Domains → Add custom domain (free)
Point your domain's CNAME to Railway's provided hostname.

---

## Going from 0 to first paying customer

1. Deploy the app (follow steps above)
2. Post in crypto communities (Reddit, Discord, Twitter):
   *"Built a free crypto price alert bot for Telegram — BTC/ETH price alerts, no app needed. £0 to start."*
3. First 10 free users → ask for feedback → iterate
4. When free users hit the 1-alert limit, they upgrade
5. £9.99 × 10 users = £100/month — covers all infrastructure with profit
6. Scale from there
