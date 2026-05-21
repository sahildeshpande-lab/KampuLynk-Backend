def _signup(client, email: str, *, admin: bool = False) -> tuple[str, str]:
    endpoint = "/auth/admin/signup" if admin else "/auth/signup"
    res = client.post(
        endpoint,
        json={
            "fullName": "Spam Admin User",
            "email": email,
            "password": "StrongPass123",
            "consentGiven": True,
            "university": "MIT",
            "major": "CS",
            "educationLevel": "bachelors",
        },
    )
    assert res.status_code in (200, 201)
    payload = res.json()["data"]
    return payload["accessToken"], payload["user"]["id"]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_spam_word_crud_and_moderation_scan(client):
    admin_token, _ = _signup(client, "spamwords.admin@test.com", admin=True)
    user_token, _ = _signup(client, "spamwords.user@test.com")

    create_res = client.post(
        "/admin/spam-words",
        headers=_bearer(admin_token),
        json={"keyword": "totally-new-scam-keyword", "type": "spam", "isActive": True},
    )
    assert create_res.status_code == 201
    keyword_id = create_res.json()["data"]["id"]

    list_res = client.get("/admin/spam-words?type=spam", headers=_bearer(admin_token))
    assert list_res.status_code == 200
    assert any(item["id"] == keyword_id for item in list_res.json()["data"]["items"])

    update_res = client.patch(
        f"/admin/spam-words/{keyword_id}",
        headers=_bearer(admin_token),
        json={"keyword": "totally-new-scam-keyword-v2"},
    )
    assert update_res.status_code == 200
    assert update_res.json()["data"]["keyword"] == "totally-new-scam-keyword-v2"

    blocked_post = client.post(
        "/posts",
        headers=_bearer(user_token),
        json={"content": "This post contains totally-new-scam-keyword-v2", "status": "published"},
    )
    assert blocked_post.status_code == 400
    assert "blocked by content safety checks" in blocked_post.json()["message"].lower()


def test_spam_words_management_requires_admin(client):
    user_token, _ = _signup(client, "spamwords.nonadmin@test.com")
    res = client.get("/admin/spam-words", headers=_bearer(user_token))
    assert res.status_code == 403
