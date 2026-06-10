import pytest

from app import main


@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)


def _get_token(client, email, full_name="Test User", university=None, major=None, location=None, visibility="public"):
    parts = full_name.split(" ", 1)
    first_name = parts[0]
    last_name = parts[1] if len(parts) > 1 else ""
    response = client.post(
        "/auth/signup",
        json={
            "firstName": first_name,
            "lastName": last_name,
            "email": email,
            "password": "StrongPass123",
            "consentGiven": True,
            "university": university,
            "major": major,
            "educationLevel": "bachelors",
        },
    )
    token = response.json()["data"]["accessToken"]

    if visibility:
        client.patch(
            "/users/me/visibility",
            headers={"Authorization": f"Bearer {token}"},
            json={"profileVisibility": visibility},
        )
    if location:
        client.patch(
            "/users/me",
            headers={"Authorization": f"Bearer {token}"},
            json={"location": location},
        )

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
    assert any(item["firstName"] == "Alice" and item["lastName"] == "User" for item in res.json()["data"]["items"])


def test_user_recommendations_requires_auth(client):
    res = client.get("/discovery/users/recommendations")
    assert res.status_code == 401


def test_user_recommendations_rank_by_mutuals_and_paginate(client, auth_headers):
    token_a, user_a = _get_token(client, "reco_a@test.com", full_name="Reco A")
    token_b, user_b = _get_token(client, "reco_b@test.com", full_name="Reco B")
    token_c, user_c = _get_token(client, "reco_c@test.com", full_name="Reco C")
    token_d, user_d = _get_token(client, "reco_d@test.com", full_name="Reco D")
    token_e, user_e = _get_token(client, "reco_e@test.com", full_name="Reco E")

    client.post(f"/users/{user_b}/lynkup/request", headers=auth_headers(token_a))
    client.post(f"/users/{user_a}/lynkup/request", headers=auth_headers(token_b))
    client.post(f"/users/{user_c}/lynkup/request", headers=auth_headers(token_a))
    client.post(f"/users/{user_a}/lynkup/request", headers=auth_headers(token_c))

    client.post(f"/users/{user_d}/lynkup/request", headers=auth_headers(token_b))
    client.post(f"/users/{user_b}/lynkup/request", headers=auth_headers(token_d))
    client.post(f"/users/{user_e}/lynkup/request", headers=auth_headers(token_b))
    client.post(f"/users/{user_b}/lynkup/request", headers=auth_headers(token_e))
    client.post(f"/users/{user_e}/lynkup/request", headers=auth_headers(token_c))
    client.post(f"/users/{user_c}/lynkup/request", headers=auth_headers(token_e))

    res = client.get("/discovery/users/recommendations?limit=1&offset=0", headers=auth_headers(token_a))
    assert res.status_code == 200
    body = res.json()["data"]
    assert body["limit"] == 1
    assert body["offset"] == 0
    assert body["total"] >= 2
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] in {user_d, user_e}
    assert body["items"][0]["mutualConnections"] >= 1


def test_post_recommendations_from_academic_interests(client, auth_headers):
    token_reader, _ = _get_token(client, "post_reco_reader@test.com", full_name="Reader")
    token_writer_match, _ = _get_token(client, "post_reco_writer_match@test.com", full_name="Writer Match")
    token_writer_other, _ = _get_token(client, "post_reco_writer_other@test.com", full_name="Writer Other")

    _set_interests(client, token_reader, ["AI", "Robotics"])
    _set_interests(client, token_writer_match, ["AI"])
    _set_interests(client, token_writer_other, ["History"])

    match_post = client.post(
        "/posts",
        headers=auth_headers(token_writer_match),
        json={"content": "Post for AI readers", "status": "published"},
    )
    assert match_post.status_code == 201
    match_id = match_post.json()["data"]["id"]

    other_post = client.post(
        "/posts",
        headers=auth_headers(token_writer_other),
        json={"content": "Unrelated post", "status": "published"},
    )
    assert other_post.status_code == 201
    other_id = other_post.json()["data"]["id"]

    res = client.get("/discovery/posts/recommendations?limit=20&offset=0", headers=auth_headers(token_reader))
    assert res.status_code == 200
    body = res.json()["data"]
    ids = [item["id"] for item in body["items"]]
    assert match_id in ids
    assert other_id not in ids
