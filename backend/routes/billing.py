import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import get_db
from domain.enterprise import WorkspaceSubscription, SubscriptionPlan
from domain.shared import SubscriptionStatus
from dependencies import get_current_workspace
from services.stripe_service import create_checkout_session, construct_webhook_event

router = APIRouter(prefix="/billing", tags=["billing"])

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@router.post("/checkout")
def checkout(payload: dict, db: Session = Depends(get_db), workspace=Depends(get_current_workspace)):
    plan_tier = payload.get("plan_tier", "creator")
    stripe_session = create_checkout_session(
        workspace_id=str(workspace.id),
        plan_tier=plan_tier,
        success_url=f"{FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{FRONTEND_URL}/billing/cancel",
    )
    return {"checkout_url": stripe_session.url, "session_id": stripe_session.id}


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    try:
        event = construct_webhook_event(payload, sig)
    except Exception as e:
        raise HTTPException(400, f"Webhook error: {e}")

    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "customer.subscription.created":
        _handle_sub_created(obj, db)
    elif etype == "customer.subscription.updated":
        _handle_sub_updated(obj, db)
    elif etype == "customer.subscription.deleted":
        _handle_sub_deleted(obj, db)

    return {"status": "ok"}


def _handle_sub_created(obj: dict, db: Session):
    ws_id = obj.get("metadata", {}).get("workspace_id")
    if not ws_id:
        return
    plan_tier = _extract_plan_tier(obj)

    sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
    if not sub:
        # Resolve plan_id — fall back to first active plan if available
        plan = (
            db.query(SubscriptionPlan)
            .filter(SubscriptionPlan.key == plan_tier)
            .first()
        )
        if plan is None:
            plan = db.query(SubscriptionPlan).first()
        if plan is None:
            # No plans seeded; skip subscription insert to avoid constraint error
            return
        sub = WorkspaceSubscription(workspace_id=ws_id, plan_id=plan.id)
        db.add(sub)

    sub.stripe_subscription_id = obj["id"]
    sub.stripe_customer_id = obj["customer"]
    sub.status = SubscriptionStatus.ACTIVE
    if obj.get("current_period_start"):
        sub.current_period_start = datetime.fromtimestamp(obj["current_period_start"])
    if obj.get("current_period_end"):
        sub.current_period_end = datetime.fromtimestamp(obj["current_period_end"])
    db.commit()

    from domain.identity import Workspace
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if ws:
        ws.plan_tier = plan_tier
        db.commit()


def _handle_sub_updated(obj: dict, db: Session):
    sub = db.query(WorkspaceSubscription).filter(
        WorkspaceSubscription.stripe_subscription_id == obj["id"]
    ).first()
    if not sub:
        ws_id = obj.get("metadata", {}).get("workspace_id")
        if not ws_id:
            return
        sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
        if not sub:
            return
        sub.stripe_subscription_id = obj["id"]
        sub.stripe_customer_id = obj.get("customer")
    raw_status = obj.get("status", "")
    try:
        sub.status = SubscriptionStatus(raw_status)
    except ValueError:
        pass
    db.commit()


def _handle_sub_deleted(obj: dict, db: Session):
    ws_id = obj.get("metadata", {}).get("workspace_id")
    if not ws_id:
        return
    sub = db.query(WorkspaceSubscription).filter(WorkspaceSubscription.workspace_id == ws_id).first()
    if sub:
        sub.status = SubscriptionStatus.CANCELLED
        db.commit()
    from domain.identity import Workspace
    ws = db.query(Workspace).filter(Workspace.id == ws_id).first()
    if ws:
        ws.plan_tier = "starter"
        db.commit()


def _extract_plan_tier(obj: dict) -> str:
    try:
        price_id = obj["items"]["data"][0]["price"]["id"]
        for tier, pid in {"creator": "price_creator", "pro": "price_pro", "agency": "price_agency"}.items():
            if pid in price_id:
                return tier
    except (KeyError, IndexError):
        pass
    return "starter"
