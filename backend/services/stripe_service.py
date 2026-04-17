import os
import stripe

PLAN_PRICE_MAP = {
    "creator": os.getenv("STRIPE_PRICE_CREATOR", "price_creator_monthly"),
    "pro": os.getenv("STRIPE_PRICE_PRO", "price_pro_monthly"),
    "agency": os.getenv("STRIPE_PRICE_AGENCY", "price_agency_monthly"),
}


def init_stripe():
    stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")


def create_checkout_session(workspace_id: str, plan_tier: str, success_url: str, cancel_url: str):
    init_stripe()
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
    init_stripe()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
