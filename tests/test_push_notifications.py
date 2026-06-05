import uuid

import pytest

from app import main
from app.db.db import SessionLocal
from app.models.model import User, UserDevice
from app.services.push_service import PushDeliveryResult


@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_notification_email", lambda *args, **kwargs: True)


def _email(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}@test.com"


def _get_token(client, email: str | None = None, role: str = "user"):
    path = "/auth/signup" if role == "user" else "/auth/admin/signup"
    response = client.post(path, json={
        "fullName": "Push Test User",
        "email": email or _email("push_user"),
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors",
    })
    assert response.status_code == 201
    return response.json()["data"]["accessToken"], response.json()["data"]["user"]["id"]


def test_register_device_upserts_duplicate_token(client, auth_headers):
    token, user_id = _get_token(client)

    first = client.post(
        "/devices/register",
        headers=auth_headers(token),
        json={"token": "fcm-token-1", "platform": "android", "deviceName": "Pixel"},
    )
    assert first.status_code == 201
    assert first.json()["data"]["created"] is True
    assert first.json()["data"]["device"]["userId"] == user_id

    second = client.post(
        "/devices/register",
        headers=auth_headers(token),
        json={"token": "fcm-token-1", "platform": "ios", "deviceName": "iPhone"},
    )
    assert second.status_code == 201
    assert second.json()["data"]["created"] is False
    assert second.json()["data"]["device"]["platform"] == "ios"


def test_deactivate_device_token(client, auth_headers):
    token, _ = _get_token(client)
    client.post(
        "/devices/register",
        headers=auth_headers(token),
        json={"token": "fcm-token-delete", "platform": "android"},
    )

    response = client.request(
        "DELETE",
        "/devices/token",
        headers=auth_headers(token),
        json={"token": "fcm-token-delete"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["isActive"] is False


def test_direct_push_dispatch_updates_delivery_status(client, auth_headers, monkeypatch):
    sent_payloads = []

    class FakePushService:
        def send_multicast_sync(self, tokens, title, body, data=None):
            sent_payloads.append({"tokens": tokens, "title": title, "body": body, "data": data})
            return PushDeliveryResult(
                status="sent",
                success_count=len(tokens),
                provider_message_ids=["projects/test/messages/1"],
            )

    monkeypatch.setattr("app.services.push_dispatcher.push_service", FakePushService())
    admin_token, _ = _get_token(client, role="admin")
    user_token, user_id = _get_token(client)
    client.post(
        "/devices/register",
        headers=auth_headers(user_token),
        json={"token": "fcm-token-direct", "platform": "android"},
    )

    response = client.post("/notifications", headers=auth_headers(admin_token), json={
        "type": "send",
        "targetType": "direct",
        "userIds": [user_id],
        "template": {"key": "direct-key", "subject": "Subject", "title": "Title", "body": "Body"},
        "channels": {"email": False, "inApp": True, "push": True},
    })

    assert response.status_code == 201
    delivery_status = response.json()["data"]["items"][0]["deliveryStatus"]
    assert delivery_status["push"] == "sent"
    assert delivery_status["pushDetails"]["successCount"] == 1
    assert sent_payloads[0]["tokens"] == ["fcm-token-direct"]
    assert sent_payloads[0]["data"]["notification_id"] == response.json()["data"]["items"][0]["id"]
    assert sent_payloads[0]["data"]["action"] == "open_notification"


def test_topic_push_reuses_existing_targeting(client, auth_headers, monkeypatch):
    class FakePushService:
        def send_multicast_sync(self, tokens, title, body, data=None):
            return PushDeliveryResult(status="sent", success_count=len(tokens))

    monkeypatch.setattr("app.services.push_dispatcher.push_service", FakePushService())
    admin_token, _ = _get_token(client, role="admin")
    user_token, _ = _get_token(client)
    client.post(
        "/devices/register",
        headers=auth_headers(user_token),
        json={"token": "fcm-token-topic", "platform": "android"},
    )

    response = client.post("/notifications", headers=auth_headers(admin_token), json={
        "type": "topic",
        "targetType": "topic",
        "topic": "CS",
        "template": {"key": "topic-key", "subject": "Subject", "title": "Title", "body": "Body"},
        "channels": {"email": False, "inApp": True, "push": True},
    })

    assert response.status_code == 201
    assert response.json()["data"]["summary"]["targetType"] == "topic"
    push_statuses = [item["deliveryStatus"]["push"] for item in response.json()["data"]["items"]]
    assert "sent" in push_statuses


def test_invalid_push_token_is_deactivated(client, auth_headers, monkeypatch):
    class FakePushService:
        def send_multicast_sync(self, tokens, title, body, data=None):
            return PushDeliveryResult(
                status="failed",
                failure_count=len(tokens),
                invalid_tokens=tokens,
                failure_reason="Unregistered token",
            )

    monkeypatch.setattr("app.services.push_dispatcher.push_service", FakePushService())
    admin_token, _ = _get_token(client, role="admin")
    user_token, user_id = _get_token(client)
    client.post(
        "/devices/register",
        headers=auth_headers(user_token),
        json={"token": "fcm-token-invalid", "platform": "android"},
    )

    response = client.post("/notifications", headers=auth_headers(admin_token), json={
        "type": "send",
        "targetType": "direct",
        "userIds": [user_id],
        "template": {"key": "invalid-key", "subject": "Subject", "title": "Title", "body": "Body"},
        "channels": {"email": False, "inApp": True, "push": True},
    })
    assert response.status_code == 201
    assert response.json()["data"]["items"][0]["deliveryStatus"]["push"] == "failed"

    db = SessionLocal()
    try:
        device = db.query(UserDevice).filter(UserDevice.device_token == "fcm-token-invalid").first()
        assert device is not None
        assert device.is_active is False
    finally:
        db.close()


def test_security_push_copy_does_not_include_otp(client, auth_headers, monkeypatch):
    sent_payloads = []

    class FakePushService:
        def send_multicast_sync(self, tokens, title, body, data=None):
            sent_payloads.append({"title": title, "body": body, "data": data})
            return PushDeliveryResult(status="sent", success_count=len(tokens))

    monkeypatch.setattr("app.services.push_dispatcher.push_service", FakePushService())
    user_token, user_id = _get_token(client)
    client.post(
        "/devices/register",
        headers=auth_headers(user_token),
        json={"token": "fcm-token-security", "platform": "android"},
    )

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        email = user.email
    finally:
        db.close()

    response = client.post("/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    assert sent_payloads
    assert "one-time password" in sent_payloads[-1]["body"].lower()
    assert not any(char.isdigit() for char in sent_payloads[-1]["body"])
