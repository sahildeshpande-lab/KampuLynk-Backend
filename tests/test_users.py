import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request

import pytest


@pytest.fixture(scope="session")
def api_server(tmp_path_factory):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    db_file = tmp_path_factory.mktemp("db") / "kampulynk_users.db"
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"

    process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    base_url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{base_url}/", timeout=0.5) as response:
                if response.status == 200:
                    break
        except Exception:
            time.sleep(0.1)
    else:
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        raise RuntimeError(f"API server did not start\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}")

    yield base_url, db_file

    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def _auth_headers(access_token):
    return {"Authorization": f"Bearer {access_token}"}


def test_user_management_flow_with_playwright_api(playwright, api_server):
    base_url, db_file = api_server
    request = playwright.request.new_context(base_url=base_url)

    signup = request.post(
        "/auth/signup",
        data={
            "fullName": "Alice Johnson",
            "email": "alice@university.edu",
            "password": "StrongPass123",
            "university": "MIT",
            "major": "Computer Science",
            "minor": "Mathematics",
            "educationLevel": "phd",
            "invitationCode": "LYNK-2026",
            "consentGiven": True,
        },
    )
    assert signup.status == 201
    signup_data = signup.json()
    assert signup_data["status"] is True
    access_token = signup_data["data"]["accessToken"]
    refresh_token = signup_data["data"]["refreshToken"]
    alice_id = signup_data["data"]["user"]["id"]
    assert signup_data["data"]["user"]["profileVisibility"] == "public"

    verify = request.post("/auth/verify-otp", data={"email": "alice@university.edu", "otp": "123456"})
    assert verify.status == 200

    login = request.post("/auth/login", data={"email": "alice@university.edu", "password": "StrongPass123"})
    assert login.status == 200
    access_token = login.json()["data"]["accessToken"]

    me = request.get("/users/me", headers=_auth_headers(access_token))
    assert me.status == 200
    assert me.json()["data"]["isEmailVerified"] is True

    update = request.patch(
        "/users/me",
        headers=_auth_headers(access_token),
        data={
            "profilePhotoUrl": "https://storage.googleapis.com/profile.png",
            "bannerPhotoUrl": "https://storage.googleapis.com/banner.png",
            "bio": "Researching distributed systems and consensus algorithms.",
            "academicInterests": ["distributed systems", "blockchain", "algorithms"],
            "graduationDate": "2027-05",
            "location": "Cambridge, MA",
            "notificationPreferences": {"email": True, "push": True, "inApp": True},
            "onlinePresence": True,
            "welcomeMessage": "Welcome to KampuLynk.",
        },
    )
    assert update.status == 200
    updated_user = update.json()["data"]
    assert updated_user["bio"].startswith("Researching")
    assert updated_user["completenessScore"] >= 80

    public_profile = request.get(f"/users/{alice_id}")
    assert public_profile.status == 200
    assert public_profile.json()["data"]["connectionsCount"] == 0

    refresh = request.post("/auth/refresh", data={"refreshToken": refresh_token})
    assert refresh.status == 200

    admin_signup = request.post(
        "/auth/admin/signup",
        data={
            "fullName": "Admin User",
            "email": "admin@university.edu",
            "password": "StrongPass123",
            "consentGiven": True,
        },
    )
    assert admin_signup.status == 201
    admin_token = admin_signup.json()["data"]["accessToken"]

    users = request.get("/users/", headers=_auth_headers(admin_token))
    assert users.status == 200
    assert any(user["email"] == "alice@university.edu" for user in users.json()["data"])

    admin_get = request.get(f"/users/admin/{alice_id}", headers=_auth_headers(admin_token))
    assert admin_get.status == 200
    assert admin_get.json()["data"]["email"] == "alice@university.edu"

    admin_create = request.post(
        "/users/admin",
        headers=_auth_headers(admin_token),
        data={
            "fullName": "Bob Student",
            "email": "bob@university.edu",
            "password": "StrongPass123",
            "role": "user",
            "consentGiven": True,
        },
    )
    assert admin_create.status == 201
    bob_id = admin_create.json()["data"]["id"]

    admin_update = request.patch(
        f"/users/admin/{bob_id}",
        headers=_auth_headers(admin_token),
        data={"major": "AI"},
    )
    assert admin_update.status == 200
    assert admin_update.json()["data"]["major"] == "AI"

    admin_delete = request.delete(f"/users/admin/{bob_id}", headers=_auth_headers(admin_token))
    assert admin_delete.status == 200
    assert admin_delete.json()["status"] is True

    blocked_admin = request.get("/users/", headers=_auth_headers(access_token))
    assert blocked_admin.status == 403

    change_password = request.post(
        "/users/me/change-password",
        headers=_auth_headers(access_token),
        data={"currentPassword": "StrongPass123", "newPassword": "EvenStronger123"},
    )
    assert change_password.status == 200

    logout = request.post("/auth/logout", headers=_auth_headers(access_token))
    assert logout.status == 200

    after_logout = request.get("/users/me", headers=_auth_headers(access_token))
    assert after_logout.status == 401
