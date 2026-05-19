import pytest

from app import main
from app.db.db import SessionLocal
from app.models.model import Post


@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_notification_email", lambda *args, **kwargs: True)


def _signup(client, email: str, *, admin: bool = False) -> tuple[str, str]:
    endpoint = "/auth/admin/signup" if admin else "/auth/signup"
    res = client.post(
        endpoint,
        json={
            "fullName": "Moderation User",
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


def test_report_post_and_admin_queue_and_review(client):
    reporter_token, _ = _signup(client, "moderation.reporter@test.com")
    author_token, _ = _signup(client, "moderation.author@test.com")
    admin_token, _ = _signup(client, "moderation.admin@test.com", admin=True)

    post_res = client.post(
        "/posts",
        headers=_bearer(author_token),
        json={"content": "post to report", "status": "published"},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["id"]

    report_res = client.patch(
        f"/posts/{post_id}/report",
        headers=_bearer(reporter_token),
        json={"reason": "spam"},
    )
    assert report_res.status_code == 200
    duplicate_report = client.patch(
        f"/posts/{post_id}/report",
        headers=_bearer(reporter_token),
        json={"reason": "spam"},
    )
    assert duplicate_report.status_code == 400
    assert "already reported this post" in duplicate_report.json()["message"].lower()

    queue_res = client.get("/admin/review/content?type=post", headers=_bearer(admin_token))
    assert queue_res.status_code == 200
    queue_items = queue_res.json()["data"]["items"]
    assert any(item["id"] == post_id and item["type"] == "post" for item in queue_items)

    action_res = client.post(
        f"/admin/review/content/{post_id}",
        headers=_bearer(admin_token),
        json={"type": "post", "action": "escalate"},
    )
    assert action_res.status_code == 200

    queue_after = client.get("/admin/review/content?moderationStatus=escalated", headers=_bearer(admin_token))
    assert queue_after.status_code == 200
    assert any(item["id"] == post_id for item in queue_after.json()["data"]["items"])


def test_report_comment_and_admin_delete(client):
    reporter_token, _ = _signup(client, "moderation.comment.reporter@test.com")
    author_token, _ = _signup(client, "moderation.comment.author@test.com")
    admin_token, _ = _signup(client, "moderation.comment.admin@test.com", admin=True)

    post_res = client.post(
        "/posts",
        headers=_bearer(author_token),
        json={"content": "post with comment", "status": "published"},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["id"]

    comment_res = client.post(
        f"/posts/{post_id}/comments",
        headers=_bearer(author_token),
        json={"content": "comment to report"},
    )
    assert comment_res.status_code == 201
    comment_id = comment_res.json()["data"]["id"]

    report_res = client.patch(
        f"/comments/{comment_id}/report",
        headers=_bearer(reporter_token),
        json={"reason": "harassment"},
    )
    assert report_res.status_code == 200

    queue_res = client.get("/admin/review/content?type=comment", headers=_bearer(admin_token))
    assert queue_res.status_code == 200
    assert any(item["id"] == comment_id and item["type"] == "comment" for item in queue_res.json()["data"]["items"])

    action_res = client.post(
        f"/admin/review/content/{comment_id}",
        headers=_bearer(admin_token),
        json={"type": "comment", "action": "delete"},
    )
    assert action_res.status_code == 200


def test_admin_delete_post_sets_archival_and_moderation_reasons(client):
    reporter_token, _ = _signup(client, "moderation.post.reporter2@test.com")
    author_token, _ = _signup(client, "moderation.post.author2@test.com")
    admin_token, _ = _signup(client, "moderation.post.admin2@test.com", admin=True)

    post_res = client.post(
        "/posts",
        headers=_bearer(author_token),
        json={"content": "post for admin delete", "status": "published"},
    )
    assert post_res.status_code == 201
    post_id = post_res.json()["data"]["id"]

    report_res = client.patch(
        f"/posts/{post_id}/report",
        headers=_bearer(reporter_token),
        json={"reason": "harassment", "description": "contains abuse"},
    )
    assert report_res.status_code == 200

    action_res = client.post(
        f"/admin/review/content/{post_id}",
        headers=_bearer(admin_token),
        json={"type": "post", "action": "delete"},
    )
    assert action_res.status_code == 200

    db = SessionLocal()
    try:
        post = db.query(Post).filter(Post.id == post_id).first()
        assert post is not None
        assert post.moderation_status == "Deleted by admin"
        assert post.moderation_reasons
        assert post.archived_at is not None
        assert post.deleted_at is not None
    finally:
        db.close()


def test_moderation_queue_requires_admin(client):
    user_token, _ = _signup(client, "moderation.nonadmin@test.com")
    res = client.get("/admin/review/content", headers=_bearer(user_token))
    assert res.status_code == 403
