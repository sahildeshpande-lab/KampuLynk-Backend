import pytest
import time

from app import main
from app.db.db import SessionLocal
from app.models.model import PlatformConfig, SpamKeyword, UserNotification


@pytest.fixture(autouse=True)
def mock_emails(monkeypatch):
    monkeypatch.setattr(main, "send_otp_email", lambda email, otp: True)
    monkeypatch.setattr(main, "send_account_created_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_password_changed_email", lambda email, name: True)
    monkeypatch.setattr(main, "send_notification_email", lambda *args, **kwargs: True)


def _signup(client, email="post.user@university.edu"):
    response = client.post(
        "/auth/signup",
        json={
            "fullName": "Post User",
            "email": email,
            "password": "StrongPass123",
            "consentGiven": True,
            "university": "MIT",
            "major": "CS",
            "educationLevel": "bachelors",
        },
    )
    assert response.status_code == 201
    token = response.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_create_feed_engage_and_repost(client):
    headers = _signup(client)
    post = client.post(
        "/posts",
        headers=headers,
        json={
            "content": "Research group meetup at 5",
            "status": "published",
            "engagementEnabled": True,
            "hashtags": ["#Research"],
            "topicTags": ["AI"],
            "attachments": [
                {
                    "type": "image",
                    "url": "https://images.unsplash.com/photo-1498050108023-c5249f4df085",
                    "name": "cloud-ai-setup.jpg",
                    "sizeBytes": 312456,
                    "metadata": {"source": "Unsplash"},
                }
            ],
        },
    )
    assert post.status_code == 201
    post_id = post.json()["data"]["id"]

    feed = client.get("/feed?limit=10")
    assert feed.status_code == 200
    assert any(item["id"] == post_id for item in feed.json()["data"]["items"])

    reaction = client.post(f"/posts/{post_id}/reactions", headers=headers, json={"reactionType": "celebrate"})
    assert reaction.status_code == 200
    assert reaction.json()["data"]["likeCount"] == 1

    post_after_reaction = client.get(f"/posts/{post_id}")
    assert post_after_reaction.status_code == 200
    assert len(post_after_reaction.json()["data"]["userEngagements"]) == 1
    assert post_after_reaction.json()["data"]["userEngagements"][0]["reaction"] == "celebrate"

    repost = client.post(f"/posts/{post_id}/repost", headers=headers, json={"quote": "Worth joining"})
    assert repost.status_code == 201
    assert repost.json()["data"]["postId"] == post_id


def test_media_inside_create_and_draft_status(client):
    headers = _signup(client, "draft.user@university.edu")
    draft = client.post(
        "/posts",
        headers=headers,
        json={
            "content": "Autosaved draft in create API",
            "status": "draft",
            "engagementEnabled": True,
            "attachments": [
                {
                    "type": "pdf",
                    "url": "https://s3.example.com/posts/syllabus.pdf",
                    "name": "syllabus.pdf",
                    "contentType": "application/pdf",
                    "sizeBytes": 1000,
                    "metadata": {"source": "s3"},
                }
            ],
        },
    )
    assert draft.status_code == 201
    assert draft.json()["data"]["status"] == "draft"


def test_comments_are_limited_to_three_levels(client):
    headers = _signup(client, "comments.user@university.edu")
    post_id = client.post("/posts", headers=headers, json={"content": "Thread seed"}).json()["data"]["id"]

    level_1 = client.post(f"/posts/{post_id}/comments", headers=headers, json={"content": "one"}).json()["data"]["id"]
    level_2 = client.post(f"/comments/{level_1}/replies", headers=headers, json={"content": "two"}).json()["data"]["id"]
    level_3 = client.post(f"/comments/{level_2}/replies", headers=headers, json={"content": "three"}).json()["data"]["id"]
    too_deep = client.post(f"/comments/{level_3}/replies", headers=headers, json={"content": "four"})

    assert too_deep.status_code == 400
    fetched = client.get(f"/posts/{post_id}")
    assert fetched.json()["data"]["comments"][0]["replies"][0]["replies"][0]["depth"] == 3


def test_post_is_blocked_when_spam_or_profanity_detected(client):
    user_headers = _signup(client, "moderated.user@university.edu")
    post = client.post("/posts", headers=user_headers, json={"content": "damn this post is rude", "status": "published"})
    assert post.status_code == 400
    assert "blocked by content safety checks" in post.json()["message"]


def test_autosave_draft_and_publish_flow(client):
    headers = _signup(client, "autosave.user@university.edu")
    draft = client.post(
        "/posts",
        headers=headers,
        json={
            "content": "WIP draft post",
            "status": "draft",
        },
    )
    assert draft.status_code == 201
    assert draft.json()["data"]["status"] == "draft"
    post_id = draft.json()["data"]["id"]

    published = client.patch(
        f"/posts/{post_id}",
        headers=headers,
        json={"status": "published", "content": "Final clean content"},
    )
    assert published.status_code == 200
    assert published.json()["data"]["status"] == "published"


def test_manual_rescan_flow(client):
    headers = _signup(client, "rescan.user@university.edu")
    created = client.post(
        "/posts",
        headers=headers,
        json={"content": "draft with damn keyword", "status": "draft"},
    )
    assert created.status_code == 201
    post_id = created.json()["data"]["id"]
    rescanned = client.patch(
        f"/posts/{post_id}",
        headers=headers,
        json={"content": "clean content now"},
    )
    assert rescanned.status_code == 200
    rescan_now = client.post(f"/posts/{post_id}/rescan", headers=headers)
    assert rescan_now.status_code == 200
    assert rescan_now.json()["data"]["rescanRequested"] is False


def test_engagement_endpoint_supports_comment_and_repost(client):
    headers = _signup(client, "engagements.user@university.edu")
    post_id = client.post(
        "/posts",
        headers=headers,
        json={"content": "Unified engagement endpoint"},
    ).json()["data"]["id"]

    comment = client.post(f"/posts/{post_id}/comments", headers=headers, json={"content": "Looks great"})
    assert comment.status_code == 201
    assert comment.json()["data"]["depth"] == 1

    repost = client.post(f"/posts/{post_id}/repost", headers=headers, json={"quote": "Sharing this"})
    assert repost.status_code == 201
    assert repost.json()["data"]["postId"] == post_id


def test_reaction_compat_supports_comment_action(client):
    headers = _signup(client, "reaction.compat.user@university.edu")
    post_id = client.post("/posts", headers=headers, json={"content": "Compat reaction post"}).json()["data"]["id"]
    res = client.post(
        f"/posts/{post_id}/reaction",
        headers=headers,
        json={"reactionType": "comment", "comment": "Compat comment"},
    )
    assert res.status_code == 200
    assert res.json()["data"]["action"] == "comment"
    assert res.json()["data"]["comment"]["postId"] == post_id


def test_engagement_blocked_when_disabled(client):
    headers = _signup(client, "engagement-disabled.user@university.edu")
    post_id = client.post(
        "/posts",
        headers=headers,
        json={"content": "No engagement allowed", "engagementEnabled": False, "status": "published"},
    ).json()["data"]["id"]

    like = client.post(f"/posts/{post_id}/reactions", headers=headers, json={"reactionType": "like"})
    assert like.status_code == 403


def test_rich_text_post_feed_edit_and_soft_delete(client):
    headers = _signup(client, "rich.feed.user@university.edu")
    created = client.post(
        "/posts",
        headers=headers,
        json={
            "content": "Hello LynkUp @mentor #Launch",
            "status": "published",
            "visibility": "connections_only",
            "hashtags": ["#Launch"],
            "mentions": ["mentor"],
            "media": [
                {
                    "type": "pdf",
                    "url": "https://storage.example.com/post/brief.pdf",
                    "name": "brief.pdf",
                    "contentType": "application/pdf",
                    "sizeBytes": 2048,
                }
            ],
        },
    )
    assert created.status_code == 201
    post_id = created.json()["data"]["id"]
    assert created.json()["data"]["plainText"] == "Hello LynkUp @mentor #Launch"
    assert created.json()["data"]["visibility"] == "connections_only"
    assert created.json()["data"]["media"][0]["type"] == "pdf"

    feed = client.get("/feed?limit=10")
    assert feed.status_code == 200
    assert any(item["id"] == post_id for item in feed.json()["data"]["items"])
    assert "nextCursor" in feed.json()["data"]["pagination"]

    edited = client.patch(
        f"/posts/{post_id}",
        headers=headers,
        json={
            "content": "Edited launch note",
            "visibility": "public",
            "hashtags": ["Launch", "Edited"],
        },
    )
    assert edited.status_code == 200
    assert edited.json()["data"]["rescanRequested"] is True
    assert edited.json()["data"]["editHistorySnapshots"]
    assert edited.json()["data"]["hashtags"] == ["launch", "edited"]

    deleted = client.delete(f"/posts/{post_id}", headers=headers)
    assert deleted.status_code == 200
    missing = client.get(f"/posts/{post_id}")
    assert missing.status_code == 404


def test_feed_cursor_uses_created_at_without_offset(client):
    headers = _signup(client, "cursor.user@university.edu")
    first = client.post("/posts", headers=headers, json={"content": "older cursor post", "status": "published"})
    assert first.status_code == 201
    time.sleep(1.1)
    second = client.post("/posts", headers=headers, json={"content": "newer cursor post", "status": "published"})
    assert second.status_code == 201

    page_one = client.get("/feed?limit=1")
    assert page_one.status_code == 200
    data = page_one.json()["data"]
    assert data["items"][0]["id"] == second.json()["data"]["id"]
    assert data["pagination"]["hasMore"] is True

    page_two = client.get(f"/feed?limit=20&cursor={data['pagination']['nextCursor']}")
    assert page_two.status_code == 200
    assert any(item["id"] == first.json()["data"]["id"] for item in page_two.json()["data"]["items"])


def test_canonical_reactions_comments_replies_and_repost_counters(client):
    headers = _signup(client, "canonical.engagement.user@university.edu")
    post_id = client.post("/posts", headers=headers, json={"content": "Canonical endpoints"}).json()["data"]["id"]

    liked = client.post(f"/posts/{post_id}/reactions", headers=headers, json={"reactionType": "like"})
    assert liked.status_code == 200
    assert liked.json()["data"]["likeCount"] == 1
    liked_again = client.post(f"/posts/{post_id}/reactions", headers=headers, json={"reactionType": "like"})
    assert liked_again.status_code == 200
    assert liked_again.json()["data"]["likeCount"] == 1
    unliked = client.delete(f"/posts/{post_id}/reactions", headers=headers)
    assert unliked.json()["data"]["likeCount"] == 0

    comment = client.post(
        f"/posts/{post_id}/comments",
        headers=headers,
        json={"content": "Root comment"},
    )
    assert comment.status_code == 201
    comment_id = comment.json()["data"]["id"]

    reply = client.post(
        f"/comments/{comment_id}/replies",
        headers=headers,
        json={"content": "Nested reply"},
    )
    assert reply.status_code == 201

    repost = client.post(f"/posts/{post_id}/repost", headers=headers, json={"quote": "Sharing"})
    assert repost.status_code == 201
    repost_again = client.post(f"/posts/{post_id}/repost", headers=headers, json={"quote": "Updated share"})
    assert repost_again.status_code == 201

    fetched = client.get(f"/posts/{post_id}")
    assert fetched.json()["data"]["commentCount"] == 2
    assert fetched.json()["data"]["comments"][0]["replyCount"] == 1
    assert fetched.json()["data"]["comments"][0]["likeCount"] == 0
    assert fetched.json()["data"]["repostCount"] == 2


def test_positive_messaging_on_post_recognition(client):
    author_headers = _signup(client, "recognition.author@university.edu")
    post_id = client.post("/posts", headers=author_headers, json={"content": "recognition target"}).json()["data"]["id"]
    for index in range(5):
        liker_headers = _signup(client, f"recognition.liker{index}@university.edu")
        reacted = client.post(f"/posts/{post_id}/reactions", headers=liker_headers, json={"reactionType": "love"})
        assert reacted.status_code == 200

    db = SessionLocal()
    try:
        post = client.get(f"/posts/{post_id}").json()["data"]
        assert post["likeCount"] == 5
        notifications = db.query(UserNotification).filter(
            UserNotification.user_id == post["authorId"],
            UserNotification.notification_type == "engagement_milestone",
        ).all()
        assert len(notifications) == 1
        assert "keep it up" in notifications[0].body.lower()
    finally:
        db.close()


def test_comment_depth_uses_platform_config(client):
    headers = _signup(client, "depth.config.user@university.edu")
    db = SessionLocal()
    try:
        config = db.query(PlatformConfig).filter(PlatformConfig.key == "comment.maxDepth").first()
        config.value = {"value": 2}
        db.commit()
    finally:
        db.close()

    try:
        post_id = client.post("/posts", headers=headers, json={"content": "Depth config"}).json()["data"]["id"]
        root_id = client.post(
            f"/posts/{post_id}/comments",
            headers=headers,
            json={"content": "one"},
        ).json()["data"]["id"]
        reply_id = client.post(
            f"/comments/{root_id}/replies",
            headers=headers,
            json={"content": "two"},
        ).json()["data"]["id"]
        too_deep = client.post(
            f"/comments/{reply_id}/replies",
            headers=headers,
            json={"content": "three"},
        )
        assert too_deep.status_code == 400
        assert "2 levels" in too_deep.json()["message"]
    finally:
        db = SessionLocal()
        try:
            config = db.query(PlatformConfig).filter(PlatformConfig.key == "comment.maxDepth").first()
            config.value = {"value": 3}
            db.commit()
        finally:
            db.close()


def test_configurable_blocklist_blocks_post_publish(client):
    headers = _signup(client, "blocklist.config.user@university.edu")
    db = SessionLocal()
    try:
        db.add(SpamKeyword(keyword="forbidden phrase", keyword_type="spam", is_active=True))
        db.commit()
    finally:
        db.close()

    blocked = client.post(
        "/posts",
        headers=headers,
        json={"content": "This includes a forbidden phrase in content", "status": "published"},
    )
    assert blocked.status_code == 400
    assert "blocked by content safety checks" in blocked.json()["message"]


def test_comment_scan_detects_bypass_pattern(client):
    headers = _signup(client, "bypass.scan.user@university.edu")
    db = SessionLocal()
    try:
        db.add(SpamKeyword(keyword="shit", keyword_type="profanity", is_active=True))
        db.commit()
    finally:
        db.close()
    post_id = client.post("/posts", headers=headers, json={"content": "seed post"}).json()["data"]["id"]

    comment = client.post(
        f"/posts/{post_id}/comments",
        headers=headers,
        json={"content": "s.h.i.t pattern should be flagged"},
    )
    assert comment.status_code == 201
    assert "blocklist" in comment.json()["data"]["moderationReasons"]


def test_top_level_comment_accepts_placeholder_parent_id(client):
    headers = _signup(client, "placeholder.parent.user@university.edu")
    post_id = client.post("/posts", headers=headers, json={"content": "Parent placeholder"}).json()["data"]["id"]
    comment = client.post(
        f"/posts/{post_id}/comments",
        headers=headers,
        json={"content": "Top-level comment", "parentCommentId": "string"},
    )
    assert comment.status_code == 201
    assert comment.json()["data"]["depth"] == 1


def test_archived_post_can_be_edited_and_republished(client):
    headers = _signup(client, "archived.edit.user@university.edu")
    post_id = client.post("/posts", headers=headers, json={"content": "to archive"}).json()["data"]["id"]

    deleted = client.delete(f"/posts/{post_id}", headers=headers)
    assert deleted.status_code == 200

    # Archived posts should not accept engagement/report actions while archived.
    like_while_archived = client.post(f"/posts/{post_id}/reactions", headers=headers, json={"reactionType": "like"})
    assert like_while_archived.status_code == 404
    report_while_archived = client.patch(f"/posts/{post_id}/report", headers=headers, json={"reason": "spam"})
    assert report_while_archived.status_code == 404

    # Author can still edit and move post back to active state.
    restored = client.patch(
        f"/posts/{post_id}",
        headers=headers,
        json={"content": "edited after archive", "status": "published"},
    )
    assert restored.status_code == 200
    assert restored.json()["data"]["status"] == "published"
    assert restored.json()["data"]["archivedAt"] is None
    assert restored.json()["data"]["deletedAt"] is None

    fetched = client.get(f"/posts/{post_id}")
    assert fetched.status_code == 200
