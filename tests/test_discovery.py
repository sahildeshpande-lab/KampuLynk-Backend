import pytest

from app import main


@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)


def _get_token(client, email, full_name="Test User", university=None, major=None, location=None, visibility="public"):
    response = client.post(
        "/auth/signup",
        json={
            "fullName": full_name,
            "email": email,
            "password": "StrongPass123",
            "consentGiven": True,
            "university": university,
            "major": major,
            "educationLevel": "bachelors",
        },
    )
    token = response.json()["data"]["accessToken"]

    patch = {"profileVisibility": visibility}
    if location:
        patch["location"] = location
    client.patch("/users/me", headers={"Authorization": f"Bearer {token}"}, json=patch)

    return token, response.json()["data"]["user"]["id"]


def _set_interests(client, token, interests):
    client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"academicInterests": interests},
    )


def test_discovery_search_and_filters(client, auth_headers):
    token_a, user_a = _get_token(client, "disc_a@test.com", full_name="Alice")
    token_b, user_b = _get_token(
        client,
        "disc_b@test.com",
        full_name="Bob MIT",
        university="MIT",
        major="Computer Science",
        location="USA",
        visibility="public",
    )
    token_c, user_c = _get_token(
        client,
        "disc_c@test.com",
        full_name="Charlie Stanford",
        university="Stanford",
        major="Biology",
        location="India",
        visibility="public",
    )
    token_d, user_d = _get_token(
        client,
        "disc_d@test.com",
        full_name="Private Person",
        university="MIT",
        major="CS",
        location="USA",
        visibility="private",
    )

    _set_interests(client, token_b, ["AI", "Robotics"])
    _set_interests(client, token_c, ["Genetics"])
    _set_interests(client, token_d, ["AI"])

    # Anonymous keyword search should not return private profiles
    res = client.get("/discovery/users/search", params={"q": "MIT"})
    assert res.status_code == 200
    ids = [item["id"] for item in res.json()["data"]["items"]]
    assert user_b in ids
    assert user_d not in ids

    # Filter by university
    res = client.get("/discovery/users/filter", params={"university": "Stanford"})
    assert res.status_code == 200
    ids = [item["id"] for item in res.json()["data"]["items"]]
    assert user_c in ids
    assert user_b not in ids

    # Interest + hashtag search
    res = client.get("/discovery/users/filter", params={"interest": "Genetics"})
    assert res.status_code == 200
    ids = [item["id"] for item in res.json()["data"]["items"]]
    assert user_c in ids

    res = client.get("/discovery/users/search", params={"hashtag": "#AI"})
    assert res.status_code == 200
    ids = [item["id"] for item in res.json()["data"]["items"]]
    assert user_b in ids
    assert user_d not in ids

    # Authenticated search excludes self by default
    res = client.get("/discovery/users/search", headers=auth_headers(token_a), params={"q": "Alice"})
    assert res.status_code == 200
    ids = [item["id"] for item in res.json()["data"]["items"]]
    assert user_a not in ids


def test_search_rejects_filter_params(client):
    res = client.get("/discovery/users/search", params={"major": "Computer Science"})
    assert res.status_code == 400
    assert "Use /discovery/users/filter" in res.json()["message"]


def test_search_username_support(client):
    _get_token(client, "alice_user123@test.com", full_name="Alice User")
    res = client.get("/discovery/users/search", params={"username": "alice_user123"})
    assert res.status_code == 200
    assert any(item["fullName"] == "Alice User" for item in res.json()["data"]["items"])
