import pytest
from app import main

@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)

def _get_token(client, email="user@test.com", role="user"):
    path = "/auth/signup" if role == "user" else "/auth/admin/signup"
    response = client.post(path, json={
        "fullName": "Test User",
        "email": email,
        "password": "StrongPass123",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    })
    return response.json()["data"]["accessToken"], response.json()["data"]["user"]["id"]

def test_get_me(client, auth_headers):
    token, _ = _get_token(client, "getme@test.com")
    response = client.get("/users/me", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "getme@test.com"

def test_update_me(client, auth_headers):
    token, _ = _get_token(client, "updateme@test.com")
    response = client.patch("/users/me", headers=auth_headers(token), json={"bio": "New Bio"})
    assert response.status_code == 200
    assert response.json()["data"]["bio"] == "New Bio"

def test_change_password(client, auth_headers):
    token, _ = _get_token(client, "changepass@test.com")
    response = client.post("/users/me/change-password", headers=auth_headers(token), json={
        "currentPassword": "StrongPass123",
        "newPassword": "NewStrongPass123"
    })
    assert response.status_code == 200

def test_delete_me(client, auth_headers):
    token, _ = _get_token(client, "deleteme@test.com")
    response = client.delete("/users/me", headers=auth_headers(token))
    assert response.status_code == 200

    me = client.get("/users/me", headers=auth_headers(token))
    assert me.status_code == 401

def test_export_me(client, auth_headers):
    token, _ = _get_token(client, "exportme@test.com")
    response = client.get("/users/me/export", headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "exportme@test.com"

def test_get_public_user(client):
    _, user_id = _get_token(client, "public@test.com")
    response = client.get(f"/users/{user_id}")
    assert response.status_code == 200
    assert response.json()["data"]["fullName"] == "Test User"

def test_admin_list_users(client, auth_headers):
    admin_token, _ = _get_token(client, "adminlist@test.com", role="admin")
    _get_token(client, "user1@test.com")
    response = client.get("/users/", headers=auth_headers(admin_token))
    assert response.status_code == 200
    assert len(response.json()["data"]["items"]) >= 2

def test_admin_create_user(client, auth_headers):
    admin_token, _ = _get_token(client, "admincreate@test.com", role="admin")
    payload = {
        "fullName": "Created By Admin",
        "email": "created@test.com",
        "password": "StrongPass123",
        "role": "user",
        "consentGiven": True,
        "university": "MIT",
        "major": "CS",
        "educationLevel": "bachelors"
    }
    response = client.post("/users/admin", headers=auth_headers(admin_token), json=payload)
    assert response.status_code == 201
    assert response.json()["data"]["email"] == "created@test.com"

def test_admin_get_user(client, auth_headers):
    admin_token, _ = _get_token(client, "adminget@test.com", role="admin")
    _, user_id = _get_token(client, "target@test.com")
    response = client.get(f"/users/admin/{user_id}", headers=auth_headers(admin_token))
    assert response.status_code == 200
    assert response.json()["data"]["email"] == "target@test.com"

def test_admin_update_user(client, auth_headers):
    admin_token, _ = _get_token(client, "adminupdate@test.com", role="admin")
    _, user_id = _get_token(client, "target_update@test.com")
    response = client.patch(f"/users/admin/{user_id}", headers=auth_headers(admin_token), json={"bio": "Admin Bio"})
    assert response.status_code == 200
    assert response.json()["data"]["bio"] == "Admin Bio"

def test_admin_delete_user(client, auth_headers):
    admin_token, _ = _get_token(client, "admindelete@test.com", role="admin")
    _, user_id = _get_token(client, "target_delete@test.com")
    response = client.delete(f"/users/admin/{user_id}", headers=auth_headers(admin_token))
    assert response.status_code == 200
    
    # Verify user is deleted (inactive)
    public = client.get(f"/users/{user_id}")
    assert public.status_code == 404
