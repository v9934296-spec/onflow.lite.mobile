"""RevenueCat transfer events must not be silently acknowledged."""

from fastapi.testclient import TestClient


def test_transfer_event_fails_closed_without_app_user_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/webhooks/revenuecat",
        json={
            "event": {
                "id": "evt-transfer-guard",
                "type": "TRANSFER",
                "event_timestamp_ms": 1_000,
                "transferred_from": ["source-user"],
                "transferred_to": ["destination-user"],
            }
        },
    )

    assert response.status_code == 503, response.text
    detail = response.json()["detail"].lower()
    assert "authoritative subscriber reconciliation" in detail
