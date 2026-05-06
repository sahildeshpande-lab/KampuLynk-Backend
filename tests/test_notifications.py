import os
import tempfile
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

test_db = Path(tempfile.gettempdir()) / f"kampulynk_notifications_{uuid.uuid4().hex}.db"
os.environ["DATABASE_URL"] = f"sqlite:///{test_db.as_posix()}"

from app import main
from app.services.email_service import (
    build_account_created_email_html,
    build_otp_email_html,
    build_password_changed_email_html,
)


@pytest.fixture(scope="module", autouse=True)
def cleanup_test_db():
    yield
    main.engine.dispose()
    test_db.unlink(missing_ok=True)



def _auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def _signup(client, email):
    response = client.post(
        "/auth/signup",
        json={
            "fullName": "Test User",
            "email": email,
            "password": "StrongPass123",
            "consentGiven": True,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def _admin_signup(client, email):
    response = client.post(
        "/auth/admin/signup",
        json={
            "fullName": "Admin User",
            "email": email,
            "password": "StrongPass123",
            "consentGiven": True,
        },
    )
    assert response.status_code == 201
    return response.json()["data"]


def test_signup_sends_random_otp_and_verifies_email(monkeypatch):
    sent_otps = []
    account_created_emails = []
    password_changed_emails = []
    monkeypatch.setattr(main, "send_otp_email", lambda _email, otp: sent_otps.append(otp) or True)
    monkeypatch.setattr(
        main,
        "send_account_created_email",
        lambda _email, full_name=None: account_created_emails.append(full_name) or True,
    )
    monkeypatch.setattr(
        main,
        "send_password_changed_email",
        lambda _email, full_name=None: password_changed_emails.append(full_name) or True,
    )

    client = TestClient(main.app)
    email = f"otp.{uuid.uuid4().hex}@university.edu"
    _signup(client, email)

    assert len(sent_otps) == 1
    assert sent_otps[0].isdigit()
    assert len(sent_otps[0]) == 6
    assert "#E13C4B" in build_otp_email_html(sent_otps[0])
    assert "Account Created Successfully" in build_account_created_email_html("Test User")
    assert "Password Changed Successfully" in build_password_changed_email_html("Test User")

    verify = client.post("/auth/verify-otp", json={"email": email, "otp": sent_otps[0]})
    assert verify.status_code == 200
    assert verify.json()["message"] == "Email verified"
    assert account_created_emails == ["Test User"]

    password_email = f"password.{uuid.uuid4().hex}@university.edu"
    password_user = _signup(client, password_email)
    change_password = client.post(
        "/users/me/change-password",
        headers=_auth_headers(password_user["accessToken"]),
        json={"currentPassword": "StrongPass123", "newPassword": "EvenStronger123"},
    )
    assert change_password.status_code == 200
    assert password_changed_emails == ["Test User"]


def test_admin_can_send_notification_and_user_can_read_it(monkeypatch):
    sent_emails = []

    def fake_send_notification_email(to_email, subject, title, body, html_body=None):
        sent_emails.append(
            {"to": to_email, "subject": subject, "title": title, "body": body, "htmlBody": html_body}
        )
        return True

    monkeypatch.setattr(main, "send_notification_email", fake_send_notification_email)

    client = TestClient(main.app)
    admin = _admin_signup(client, f"admin.{uuid.uuid4().hex}@university.edu")
    user = _signup(client, f"notify.{uuid.uuid4().hex}@university.edu")
    user_id = user["user"]["id"]

    send_response = client.post(
        "/notifications",
        headers=_auth_headers(admin["accessToken"]),
        json={
            "userIds": [user_id],
            "template": {
                "key": "campus-update",
                "subject": "KampuLynk campus update",
                "title": "New campus update",
                "body": "A new campus update is available.",
            },
            "channels": {"email": True, "inApp": True, "push": True},
        },
    )

    assert send_response.status_code == 201
    notification = send_response.json()["data"]["items"][0]
    assert notification["deliveryStatus"]["email"] == "sent"
    assert notification["deliveryStatus"]["inApp"] == "created"
    assert notification["deliveryStatus"]["push"] == "queued"
    assert len(sent_emails) == 1

    inbox = client.get("/notifications/me", headers=_auth_headers(user["accessToken"]))
    assert inbox.status_code == 200
    assert inbox.json()["data"]["items"][0]["title"] == "New campus update"

    mark_read = client.patch(
        f"/notifications/{notification['id']}/read",
        headers=_auth_headers(user["accessToken"]),
    )
    assert mark_read.status_code == 200
    assert mark_read.json()["data"]["isRead"] is True
