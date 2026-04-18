from unittest.mock import MagicMock, patch


def test_create_checkout_session(client, workspace_a):
    ws_id, token = workspace_a
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/test"
    mock_session.id = "cs_test_123"

    with patch("stripe.checkout.Session.create", return_value=mock_session):
        resp = client.post(
            "/billing/checkout",
            json={"plan_tier": "creator"},
            headers={"Authorization": f"Bearer {token}"},
        )
    assert resp.status_code == 200
    assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"


def test_webhook_subscription_created(client, workspace_a, db):
    ws_id, token = workspace_a
    event = {
        "type": "customer.subscription.created",
        "data": {
            "object": {
                "id": "sub_test_123",
                "customer": "cus_test_123",
                "status": "active",
                "items": {"data": [{"price": {"id": "price_creator_monthly", "nickname": "creator"}}]},
                "current_period_start": 1713100800,
                "current_period_end": 1715692800,
                "metadata": {"workspace_id": str(ws_id)},
            }
        },
    }
    with patch("stripe.Webhook.construct_event", return_value=event):
        resp = client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 200


def test_webhook_subscription_cancelled(client, workspace_a, db):
    ws_id, token = workspace_a
    event = {
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_test_456",
                "customer": "cus_test_456",
                "metadata": {"workspace_id": str(ws_id)},
            }
        },
    }
    with patch("stripe.Webhook.construct_event", return_value=event):
        resp = client.post(
            "/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "t=1,v1=abc"},
        )
    assert resp.status_code == 200
