from datetime import datetime, timedelta, timezone

import pytest

from app import main
from app.db.db import SessionLocal
from app.models.model import UserActivity


@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_notification_email", lambda *args, **kwargs: True)


def _signup(client, email: str, admin: bool = False):
    path = "/auth/admin/signup" if admin else "/auth/signup"
    res = client.post(
        path,
        json={
            "firstName": "Analytics", "lastName": "User",
            "email": email,
            "password": "StrongPass123",
            "consentGiven": True,
            "university": "MIT",
            "major": "CS",
            "educationLevel": "bachelors",
        },
    )
    assert res.status_code in (200, 201)
    return res.json()["data"]["accessToken"], res.json()["data"]["user"]["id"]


def _login(client, email: str):
    res = client.post("/auth/login", json={"email": email, "password": "StrongPass123"})
    assert res.status_code == 200
    return res.json()["data"]["accessToken"]


def test_admin_dau_requires_auth(client):
    response = client.get("/admin/analytics/dau-trend")
    assert response.status_code == 401
    dashboard_response = client.get("/admin/analytics/dashboard")
    assert dashboard_response.status_code == 401


def test_admin_dau_requires_admin_role(client, auth_headers):
    token, _ = _signup(client, "normal.analytics@test.com")
    response = client.get("/admin/analytics/dau-trend", headers=auth_headers(token))
    assert response.status_code == 403
    dashboard_response = client.get("/admin/analytics/dashboard", headers=auth_headers(token))
    assert dashboard_response.status_code == 403


def test_admin_dau_trend_with_distinct_users_and_zero_fill(client, auth_headers):
    admin_token, _ = _signup(client, "admin.analytics@test.com", admin=True)
    _signup(client, "dau.user1@test.com")
    _signup(client, "dau.user2@test.com")

    # Two logins from user1 on same day should still count once for that day.
    _login(client, "dau.user1@test.com")
    _login(client, "dau.user1@test.com")
    _login(client, "dau.user2@test.com")

    response = client.get("/admin/analytics/dau-trend?days=3", headers=auth_headers(admin_token))
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["trend"]) == 3
    assert all("date" in item and "dau" in item for item in data["trend"])
    assert all(item["dau"] >= 0 for item in data["trend"])
    assert any(item["dau"] == 0 for item in data["trend"])
    assert data["today_dau"] >= 2


def test_admin_dau_date_range_filters(client, auth_headers):
    admin_token, user_id = _signup(client, "admin.analytics.range@test.com", admin=True)
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        db.add(
            UserActivity(
                user_id=user_id,
                activity_type="login",
                activity_metadata={},
                created_at=now - timedelta(days=2),
            )
        )
        db.add(
            UserActivity(
                user_id=user_id,
                activity_type="login",
                activity_metadata={},
                created_at=now,
            )
        )
        db.commit()
    finally:
        db.close()

    start = (now - timedelta(days=2)).date().isoformat()
    end = now.date().isoformat()
    response = client.get(
        f"/admin/analytics/dau-trend?start_date={start}&end_date={end}",
        headers=auth_headers(admin_token),
    )
    assert response.status_code == 200
    trend = response.json()["data"]["trend"]
    assert len(trend) == 3


def test_admin_dashboard_payload_shape(client, auth_headers):
    admin_token, _ = _signup(client, "admin.dashboard@test.com", admin=True)
    _signup(client, "dashboard.user1@test.com")
    _signup(client, "dashboard.user2@test.com")
    _login(client, "dashboard.user1@test.com")
    _login(client, "dashboard.user2@test.com")

    response = client.get("/admin/analytics/dashboard?days=5&top_limit=3", headers=auth_headers(admin_token))
    assert response.status_code == 200
    data = response.json()["data"]

    assert "summary" in data
    assert "dau_trend" in data
    assert "new_user_trend" in data
    assert "top_universities" in data
    assert "country_distribution" in data
    assert "top_majors" in data
    assert len(data["dau_trend"]) == 5
    assert len(data["new_user_trend"]) == 5
    assert data["summary"]["total_users"] >= 3
