import pytest
from app import main

@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_notification_email", lambda *args, **kwargs: True)

def _get_token(client, email="user@test.com", role="user"):
    path = "/auth/signup" if role == "user" else "/auth/admin/signup"
    response = client.post(path, json={
        "firstName": "Test", "lastName": "User",
        "email": email,
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    return response.json()["data"]["accessToken"], response.json()["data"]["user"]["id"]

def test_send_notification(client, auth_headers):
    admin_token, _ = _get_token(client, "admin_notify@test.com", role="admin")
    _, user_id = _get_token(client, "user_notify@test.com")
    
    payload = {
        "userIds": [user_id],
        "template": {
            "key": "test-key",
            "subject": "Test Subject",
            "title": "Test Title",
            "body": "Test Body"
        },
        "channels": {"email": True, "inApp": True, "push": True}
    }
    response = client.post("/notifications", headers=auth_headers(admin_token), json=payload)
    assert response.status_code == 201
    assert len(response.json()["data"]["items"]) == 1
    assert response.json()["data"]["items"][0]["type"] == "send"


def test_add_notification_type(client, auth_headers):
    admin_token, _ = _get_token(client, "admin_type@test.com", role="admin")

    response = client.post("/notifications/types", headers=auth_headers(admin_token), json={
        "type": "configuration",
        "name": "Configuration Notification",
        "description": "Setup and configuration updates"
    })

    assert response.status_code == 201
    assert response.json()["data"]["type"] == "configuration"


def test_get_notifications_by_type(client, auth_headers):
    admin_token, _ = _get_token(client, "admin_get_type@test.com", role="admin")
    _, user_id = _get_token(client, "user_get_type@test.com")

    client.post("/notifications", headers=auth_headers(admin_token), json={
        "type": "send",
        "targetType": "direct",
        "userIds": [user_id],
        "template": {"key": "k", "subject": "s", "title": "t", "body": "b"},
        "channels": {"email": False, "inApp": True, "push": False}
    })

    response = client.get("/notifications?type=send", headers=auth_headers(admin_token))
    assert response.status_code == 200
    assert response.json()["data"]["items"][0]["type"] == "send"


def test_broadcast_notification(client, auth_headers):
    admin_token, _ = _get_token(client, "admin_broadcast@test.com", role="admin")
    _get_token(client, "user_broadcast@test.com")

    response = client.post("/notifications", headers=auth_headers(admin_token), json={
        "type": "broadcast",
        "targetType": "broadcast",
        "template": {"key": "broadcast", "subject": "s", "title": "t", "body": "b"},
        "channels": {"email": False, "inApp": True, "push": True}
    })

    assert response.status_code == 201
    assert response.json()["data"]["summary"]["targetType"] == "broadcast"
    assert response.json()["data"]["summary"]["processed"] >= 1


def test_topic_notification(client, auth_headers):
    admin_token, _ = _get_token(client, "admin_topic@test.com", role="admin")
    _get_token(client, "user_topic@test.com")

    response = client.post("/notifications", headers=auth_headers(admin_token), json={
        "type": "topic",
        "targetType": "topic",
        "topic": "CS",
        "template": {"key": "topic", "subject": "s", "title": "t", "body": "b"},
        "channels": {"email": False, "inApp": True, "push": True}
    })

    assert response.status_code == 201
    assert response.json()["data"]["summary"]["targetType"] == "topic"
    assert response.json()["data"]["summary"]["topic"] == "CS"

def test_list_my_notifications(client, auth_headers):
    admin_token, _ = _get_token(client, "admin_list_n@test.com", role="admin")
    user_token, user_id = _get_token(client, "user_list_n@test.com")
    
    client.post("/notifications", headers=auth_headers(admin_token), json={
        "userIds": [user_id],
        "template": {"key": "k", "subject": "s", "title": "t", "body": "b"},
        "channels": {"email": False, "inApp": True, "push": False}
    })
    
    response = client.get("/notifications/me", headers=auth_headers(user_token))
    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) > 0

def test_mark_notification_read(client, auth_headers):
    admin_token, _ = _get_token(client, "admin_read@test.com", role="admin")
    user_token, user_id = _get_token(client, "user_read@test.com")
    
    send_res = client.post("/notifications", headers=auth_headers(admin_token), json={
        "userIds": [user_id],
        "template": {"key": "k", "subject": "s", "title": "t", "body": "b"},
        "channels": {"email": False, "inApp": True, "push": False}
    })
    notif_id = send_res.json()["data"]["items"][0]["id"]
    
    response = client.patch(f"/notifications/{notif_id}/read", headers=auth_headers(user_token))
    assert response.status_code == 200
    assert response.json()["data"]["isRead"] is True
