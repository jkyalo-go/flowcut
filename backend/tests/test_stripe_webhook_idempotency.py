"""Stripe webhook deduplicates by event.id."""
from unittest.mock import patch

_FAKE_EVENT = {
    "id": "evt_test_123",
    "type": "customer.subscription.created",
    "data": {
        "object": {
            "id": "sub_test",
            "customer": "cus_test",
            "metadata": {"workspace_id": None},  # filled per-test
            "status": "active",
            "items": {"data": [{"price": {"id": "price_creator_monthly"}}]},
        }
    },
}


def _event_for(ws_id: str) -> dict:
    event = {**_FAKE_EVENT}
    event["data"] = {"object": {**_FAKE_EVENT["data"]["object"]}}
    event["data"]["object"]["metadata"] = {"workspace_id": ws_id}
    return event


def test_same_event_processed_once(client, workspace_a, db):
    ws_id, _ = workspace_a
    event = _event_for(ws_id)

    # Bypass HMAC verification — we're testing idempotency
    with patch("services.stripe_service.STRIPE_WEBHOOK_SECRET", "test-secret"), \
         patch("stripe.Webhook.construct_event", return_value=event):
        r1 = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"})
        r2 = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"})

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json().get("idempotent") is True

    from domain.enterprise import StripeEvent
    rows = db.query(StripeEvent).filter(StripeEvent.event_id == "evt_test_123").all()
    assert len(rows) == 1


def test_webhook_hardfails_when_secret_missing(monkeypatch, client):
    # The actual construct_webhook_event raises ValueError when secret is empty.
    import services.stripe_service as s
    monkeypatch.setattr(s, "STRIPE_WEBHOOK_SECRET", "")
    r = client.post("/billing/webhook", content=b"{}", headers={"stripe-signature": "sig"})
    assert r.status_code == 400
    assert "WEBHOOK_SECRET" in r.json()["detail"] or "not set" in r.json()["detail"].lower()
