import pytest

from app import main


@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_notification_email", lambda *args, **kwargs: True)


def _signup_user(client, email: str, role: str = "user"):
    payload = {
        "fullName": "Invite User",
        "email": email,
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors",
    }
    if role == "admin":
        resp = client.post("/auth/admin/signup", json=payload)
    else:
        resp = client.post("/auth/signup", json=payload)
    assert resp.status_code == 201
    return resp.json()["data"]["accessToken"]


def test_invitation_send_and_validate(client, auth_headers):
    token = _signup_user(client, "inviter@university.edu")
    code_resp = client.get("/invitations/code", headers=auth_headers(token))
    assert code_resp.status_code == 200
    assert code_resp.json()["data"]["code"]

    send = client.post("/invitations/send", json={"email": "invitee@university.edu"}, headers=auth_headers(token))
    assert send.status_code == 201
    code = send.json()["data"]["code"]

    me = client.get("/users/me", headers=auth_headers(token))
    assert me.status_code == 200
    assert me.json()["data"]["invitationCode"] == code

    validate = client.get(f"/invitations/validate/{code}")
    assert validate.status_code == 200
    assert validate.json()["data"]["isValid"] is True


def test_invitation_block_same_email_7_days(client, auth_headers):
    token = _signup_user(client, "inviter2@university.edu")
    first = client.post("/invitations/send", json={"email": "same@university.edu"}, headers=auth_headers(token))
    assert first.status_code == 201

    second = client.post("/invitations/send", json={"email": "same@university.edu"}, headers=auth_headers(token))
    assert second.status_code == 409


def test_invitation_cannot_invite_self(client, auth_headers):
    email = "self_inviter@university.edu"
    token = _signup_user(client, email)

    response = client.post("/invitations/send", json={"email": email}, headers=auth_headers(token))

    assert response.status_code == 200
    assert response.json()["detail"] == "User cannot invite itself"
    assert response.json()["data"] == {}


def test_invitation_cannot_invite_existing_user(client, auth_headers):
    token = _signup_user(client, "existing_inviter@university.edu")
    _signup_user(client, "existing_invitee@university.edu")

    response = client.post(
        "/invitations/send",
        json={"email": "existing_invitee@university.edu"},
        headers=auth_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["detail"] == "User already exists"
    assert response.json()["data"] == {}


def test_invitation_daily_limit_enforced(client, auth_headers, monkeypatch):
    from app.services import invitation_service

    monkeypatch.setattr(invitation_service, "INVITATION_DAILY_LIMIT", 2)

    token = _signup_user(client, "inviter3@university.edu")
    r1 = client.post("/invitations/send", json={"email": "a@university.edu"}, headers=auth_headers(token))
    r2 = client.post("/invitations/send", json={"email": "b@university.edu"}, headers=auth_headers(token))
    r3 = client.post("/invitations/send", json={"email": "c@university.edu"}, headers=auth_headers(token))
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r3.status_code == 429


def test_admin_deactivate_invitation_code(client, auth_headers):
    inviter_token = _signup_user(client, "inviter4@university.edu")
    send = client.post(
        "/invitations/send",
        json={"email": "to-deactivate@university.edu"},
        headers=auth_headers(inviter_token),
    )
    code = send.json()["data"]["code"]
    inviter_me = client.get("/users/me", headers=auth_headers(inviter_token))
    originator_id = inviter_me.json()["data"]["id"]

    admin_token = _signup_user(client, "admin.invites@university.edu", role="admin")

    codes = client.get("/admin/invitation-codes?page=1&pageSize=10", headers=auth_headers(admin_token))
    assert codes.status_code == 200
    items = codes.json()["data"]["items"]
    target = next(item for item in items if item["code"] == code and item["originatorUserId"] == originator_id)

    details = client.get(f"/admin/invitation-codes/{target['id']}", headers=auth_headers(admin_token))
    assert details.status_code == 200
    assert details.json()["data"]["code"] == code

    deactivate = client.patch(
        f"/admin/invitation-codes/{target['id']}/deactivate",
        json={"reason": "test"},
        headers=auth_headers(admin_token),
    )
    assert deactivate.status_code == 200

    validate = client.get(f"/invitations/validate/{code}")
    assert validate.status_code == 200
    assert validate.json()["data"]["isValid"] is False
