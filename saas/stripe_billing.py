"""
Stripe billing integration for CryptoWatch SaaS.

Plans:
  starter  — £9.99/month  — 10 alerts
  pro      — £24.99/month — unlimited alerts

Setup:
  1. Create products/prices in Stripe Dashboard
  2. Set STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET in .env
  3. Set STRIPE_STARTER_PRICE_ID, STRIPE_PRO_PRICE_ID in .env
  4. Point Stripe webhook to: https://your-domain.com/webhook/stripe
     Events to enable: customer.subscription.updated, customer.subscription.deleted,
                       checkout.session.completed
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import stripe

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

PRICE_IDS = {
    "starter": os.getenv("STRIPE_STARTER_PRICE_ID", ""),
    "pro":     os.getenv("STRIPE_PRO_PRICE_ID", ""),
}

PLAN_NAMES = {
    "starter": "Starter — £9.99/month",
    "pro":     "Pro — £24.99/month",
}


def create_checkout_session(
    user_id: int,
    email: str,
    plan: str,
    success_url: str,
    cancel_url: str,
) -> Optional[str]:
    """Create a Stripe Checkout session. Returns the checkout URL."""
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        logger.error("No price ID configured for plan: %s", plan)
        return None
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=email,
            metadata={"user_id": str(user_id), "plan": plan},
            success_url=success_url,
            cancel_url=cancel_url,
        )
        return session.url
    except stripe.StripeError as exc:
        logger.error("Stripe checkout error: %s", exc)
        return None


def create_billing_portal_session(stripe_customer_id: str, return_url: str) -> Optional[str]:
    """Returns Stripe billing portal URL so users can manage/cancel subscriptions."""
    try:
        session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )
        return session.url
    except stripe.StripeError as exc:
        logger.error("Stripe portal error: %s", exc)
        return None


def parse_webhook(payload: bytes, sig_header: str):
    """
    Parse and verify a Stripe webhook event.
    Returns (event_type, data_object) or raises ValueError on failure.
    """
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        return event["type"], event["data"]["object"]
    except stripe.SignatureVerificationError as exc:
        raise ValueError(f"Webhook signature invalid: {exc}") from exc


def get_plan_from_price_id(price_id: str) -> str:
    """Reverse lookup: Stripe price ID → plan name."""
    for plan, pid in PRICE_IDS.items():
        if pid and pid == price_id:
            return plan
    return "free"
