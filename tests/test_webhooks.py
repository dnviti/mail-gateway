import json
from unittest.mock import patch


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_webhook_invalid_signature(client):
    with patch("app.api.webhooks.verify_webhook_signature", return_value=None):
        response = client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "invalid"},
        )
        assert response.status_code == 400


def test_webhook_unhandled_event(client):
    mock_event = {"type": "charge.succeeded", "data": {"object": {}}}
    with patch("app.api.webhooks.verify_webhook_signature", return_value=mock_event):
        response = client.post(
            "/webhooks/stripe",
            content=b"{}",
            headers={"Stripe-Signature": "valid"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ignored"
