"""
NorthSignal SaaS — Main FastAPI Application

Routes:
  GET  /                  Landing page
  GET  /register          Registration form
  POST /register          Create account
  GET  /login             Login form
  POST /login             Authenticate
  POST /logout            Clear session
  GET  /dashboard         Main user dashboard (auth required)
  POST /alerts/create     Create a new alert (auth required)
  POST /alerts/{id}/delete Delete an alert (auth required)
  POST /alerts/{id}/toggle Toggle alert on/off (auth required)
  GET  /settings          Account settings (auth required)
  POST /settings          Update Telegram chat ID (auth required)
  GET  /upgrade/{plan}    Start Stripe checkout
  GET  /billing/portal    Open Stripe billing portal
  GET  /billing/success   Post-checkout success page
  POST /webhook/stripe    Stripe webhook handler
  GET  /prices            JSON endpoint — current BTC/ETH prices (HTMX poll target)
"""
from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from auth import clear_session_cookie, require_auth, get_current_user_id, set_session_cookie
from database import Database, PLAN_LIMITS
from alert_monitor import AlertMonitor
from stripe_billing import (
    create_billing_portal_session,
    create_checkout_session,
    get_plan_from_price_id,
    parse_webhook,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# ── App state ──────────────────────────────────────────────────────────────────

db = Database()
monitor: AlertMonitor = None  # initialised in lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    global monitor
    await db.connect()
    monitor = AlertMonitor(db, TELEGRAM_TOKEN)
    asyncio.create_task(monitor.start())
    logger.info("NorthSignal started")
    yield
    monitor.stop()
    await db.close()
    logger.info("NorthSignal stopped")


app = FastAPI(title="NorthSignal", lifespan=lifespan)
templates = Jinja2Templates(directory="templates")


def _fmt_ts(ts: float) -> str:
    if not ts:
        return "Never"
    return datetime.fromtimestamp(ts).strftime("%d %b %H:%M")


templates.env.filters["fmt_ts"] = _fmt_ts


# ── Landing page ───────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


# ── Auth ───────────────────────────────────────────────────────────────────────

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {"error": None})


@app.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password2: str = Form(...),
):
    if password != password2:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Passwords do not match"}
        )
    if len(password) < 8:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Password must be at least 8 characters"}
        )
    user = await db.create_user(email, password)
    if not user:
        return templates.TemplateResponse(
            request, "register.html", {"error": "Email already registered"}
        )
    response = RedirectResponse("/dashboard", status_code=303)
    set_session_cookie(response, user.id, user.email)
    return response


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
):
    user = await db.verify_password(email, password)
    if not user:
        return templates.TemplateResponse(
            request, "login.html", {"error": "Invalid email or password"}
        )
    response = RedirectResponse("/dashboard", status_code=303)
    set_session_cookie(response, user.id, user.email)
    return response


@app.post("/logout")
async def logout():
    response = RedirectResponse("/", status_code=303)
    clear_session_cookie(response)
    return response


# ── Dashboard ──────────────────────────────────────────────────────────────────

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, user_id: int = Depends(require_auth)):
    user = await db.get_user_by_id(user_id)
    sub = await db.get_subscription(user_id)
    alerts = await db.get_user_alerts(user_id)
    history = await db.get_alert_history(user_id, limit=10)
    prices = monitor.get_current_prices() if monitor else {}
    plan = sub.plan if sub else "free"
    limit = PLAN_LIMITS.get(plan, 1)
    return templates.TemplateResponse(request, "dashboard.html", {
        "user": user,
        "sub": sub,
        "alerts": alerts,
        "history": history,
        "prices": prices,
        "plan": plan,
        "alert_limit": limit,
        "alert_count": len([a for a in alerts if a.enabled]),
    })


# ── Alert management ───────────────────────────────────────────────────────────

@app.post("/alerts/create")
async def create_alert(
    user_id: int = Depends(require_auth),
    asset: str = Form(...),
    condition: str = Form(...),
    threshold: float = Form(...),
    label: str = Form(""),
    cooldown_sec: int = Form(3600),
):
    if asset not in ("BTC", "ETH"):
        raise HTTPException(400, "Invalid asset")
    if condition not in ("above", "below", "change_pct"):
        raise HTTPException(400, "Invalid condition")
    if threshold <= 0:
        raise HTTPException(400, "Threshold must be positive")

    alert = await db.create_alert(user_id, asset, condition, threshold, label, cooldown_sec)
    if not alert:
        # Plan limit hit — redirect to upgrade
        return RedirectResponse("/upgrade/starter?reason=limit", status_code=303)
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/alerts/{alert_id}/delete")
async def delete_alert(alert_id: int, user_id: int = Depends(require_auth)):
    await db.delete_alert(alert_id, user_id)
    return RedirectResponse("/dashboard", status_code=303)


@app.post("/alerts/{alert_id}/toggle")
async def toggle_alert(alert_id: int, enabled: int = Form(...), user_id: int = Depends(require_auth)):
    await db.toggle_alert(alert_id, user_id, bool(enabled))
    return RedirectResponse("/dashboard", status_code=303)


# ── Settings ───────────────────────────────────────────────────────────────────

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, user_id: int = Depends(require_auth)):
    user = await db.get_user_by_id(user_id)
    sub = await db.get_subscription(user_id)
    return templates.TemplateResponse(request, "settings.html", {
        "user": user,
        "sub": sub,
        "saved": False,
    })


@app.post("/settings", response_class=HTMLResponse)
async def save_settings(
    request: Request,
    telegram_chat_id: str = Form(""),
    user_id: int = Depends(require_auth),
):
    await db.update_telegram_chat_id(user_id, telegram_chat_id.strip())
    user = await db.get_user_by_id(user_id)
    sub = await db.get_subscription(user_id)
    return templates.TemplateResponse(request, "settings.html", {
        "user": user,
        "sub": sub,
        "saved": True,
    })


# ── Billing ────────────────────────────────────────────────────────────────────

@app.get("/upgrade/{plan}", response_class=HTMLResponse)
async def upgrade(plan: str, request: Request, user_id: int = Depends(require_auth)):
    if plan not in ("starter", "pro"):
        raise HTTPException(400, "Invalid plan")
    user = await db.get_user_by_id(user_id)
    url = create_checkout_session(
        user_id=user_id,
        email=user.email,
        plan=plan,
        success_url=f"{BASE_URL}/billing/success?plan={plan}",
        cancel_url=f"{BASE_URL}/dashboard",
    )
    if not url:
        return templates.TemplateResponse(
            request, "error.html",
            {"message": "Stripe not configured. Set STRIPE_SECRET_KEY."},
        )
    return RedirectResponse(url, status_code=303)


@app.get("/billing/portal")
async def billing_portal(user_id: int = Depends(require_auth)):
    sub = await db.get_subscription(user_id)
    if not sub or not sub.stripe_customer_id:
        return RedirectResponse("/dashboard", status_code=303)
    url = create_billing_portal_session(sub.stripe_customer_id, f"{BASE_URL}/dashboard")
    if not url:
        return RedirectResponse("/dashboard", status_code=303)
    return RedirectResponse(url, status_code=303)


@app.get("/billing/success", response_class=HTMLResponse)
async def billing_success(request: Request, plan: str = "starter", user_id: int = Depends(require_auth)):
    return templates.TemplateResponse(request, "billing_success.html", {
        "plan": plan,
    })


# ── Stripe webhook ─────────────────────────────────────────────────────────────

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event_type, obj = parse_webhook(payload, sig)
    except ValueError as exc:
        logger.warning("Stripe webhook rejected: %s", exc)
        raise HTTPException(400, str(exc))

    if event_type == "checkout.session.completed":
        user_id = int(obj.get("metadata", {}).get("user_id", 0))
        plan = obj.get("metadata", {}).get("plan", "starter")
        customer_id = obj.get("customer", "")
        sub_id = obj.get("subscription", "")
        if user_id:
            await db.upsert_subscription(
                user_id=user_id,
                plan=plan,
                status="active",
                stripe_customer_id=customer_id,
                stripe_sub_id=sub_id,
            )
            logger.info("User %d upgraded to %s", user_id, plan)

    elif event_type == "customer.subscription.updated":
        sub_id = obj.get("id", "")
        status_ = obj.get("status", "active")
        period_end = obj.get("current_period_end", 0)
        items = obj.get("items", {}).get("data", [])
        price_id = items[0]["price"]["id"] if items else ""
        plan = get_plan_from_price_id(price_id)
        # Find user by stripe subscription ID
        async with db._conn.execute(
            "SELECT user_id FROM subscriptions WHERE stripe_sub_id = ?", (sub_id,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            await db.upsert_subscription(
                user_id=row[0],
                plan=plan,
                status=status_,
                current_period_end=period_end,
            )

    elif event_type == "customer.subscription.deleted":
        sub_id = obj.get("id", "")
        async with db._conn.execute(
            "SELECT user_id FROM subscriptions WHERE stripe_sub_id = ?", (sub_id,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            await db.upsert_subscription(row[0], plan="free", status="cancelled")
            logger.info("User %d downgraded to free (subscription cancelled)", row[0])

    return JSONResponse({"status": "ok"})


# ── Live price endpoint (polled by HTMX) ──────────────────────────────────────

@app.get("/prices")
async def get_prices(user_id: Optional[int] = Depends(get_current_user_id)):
    prices = monitor.get_current_prices() if monitor else {}
    return JSONResponse(prices)


from typing import Optional
