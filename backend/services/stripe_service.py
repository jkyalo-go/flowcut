import logging
import os

import stripe

logger = logging.getLogger(__name__)

stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
if not stripe.api_key:
    logger.warning("STRIPE_SECRET_KEY is not set — Stripe calls will fail")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
if not STRIPE_WEBHOOK_SECRET:
    logger.warning("STRIPE_WEBHOOK_SECRET is not set — webhook verification will fail")

PLAN_PRICE_MAP = {
    "creator": os.getenv("STRIPE_PRICE_CREATOR", "price_creator_monthly"),
    "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro_monthly"),
    "agency": os.getenv("STRIPE_PRICE_AGENCY", "price_agency_monthly"),
}


def create_checkout_session(workspace_id: str, plan_tier: str, success_url: str, cancel_url: str):
    price_id = PLAN_PRICE_MAP.get(plan_tier)
    if not price_id:
        raise ValueError(f"Unknown plan tier: {plan_tier}")
    return stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        metadata={"workspace_id": workspace_id},
        success_url=success_url,
        cancel_url=cancel_url,
    )


def construct_webhook_event(payload: bytes, sig_header: str) -> dict:
    """Construct and verify a Stripe webhook event.

    Hard-fails with ValueError when STRIPE_WEBHOOK_SECRET is not configured.
    This is intentional — a silently-unverified webhook is worse than a
    downed webhook because an attacker can forge events for free.
    """
    if not STRIPE_WEBHOOK_SECRET:
        raise ValueError(
            "STRIPE_WEBHOOK_SECRET is not set; refusing to process unverified webhook payloads"
        )
    return stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
