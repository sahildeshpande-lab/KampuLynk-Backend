import pytest

from app import main


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
            "firstName": "Post", "lastName": "User",
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
            "contentFormat": "rich_text",
            "richTextHtml": "<p>Research group meetup at 5</p>",
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

    feed = client.get("/posts?page=1&pageSize=10&hashtag=research")
    assert feed.status_code == 200
    assert feed.json()["data"]["items"][0]["id"] == post_id

    reaction = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "like", "reaction": "celebrate", "isLiked": True},
    )
    assert reaction.status_code == 200
    assert reaction.json()["data"]["likeCount"] == 1

    post_after_reaction = client.get(f"/posts/{post_id}")
    assert post_after_reaction.status_code == 200
    assert len(post_after_reaction.json()["data"]["userEngagements"]) == 1
    assert post_after_reaction.json()["data"]["userEngagements"][0]["reaction"] == "celebrate"

    repost = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "repost", "quote": "Worth joining"},
    )
    assert repost.status_code == 200
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

    level_1 = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "comment", "comment": "one"},
    ).json()["data"]["commentId"]
    level_2 = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "comment", "comment": "two", "parentCommentId": level_1},
    ).json()["data"]["commentId"]
    level_3 = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "comment", "comment": "three", "parentCommentId": level_2},
    ).json()["data"]["commentId"]
    too_deep = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "comment", "comment": "four", "parentCommentId": level_3},
    )

    assert too_deep.status_code == 400
    fetched = client.get(f"/posts/{post_id}")
    assert fetched.json()["data"]["comments"][0]["replies"][0]["replies"][0]["depth"] == 3


def test_post_is_not_flagged_without_content_filters(client):
    user_headers = _signup(client, "moderated.user@university.edu")
    post = client.post("/posts", headers=user_headers, json={"content": "damn this post is rude"})
    assert post.status_code == 201
    assert post.json()["data"]["moderationStatus"] == "approved"


def test_engagement_endpoint_supports_comment_and_repost(client):
    headers = _signup(client, "engagements.user@university.edu")
    post_id = client.post(
        "/posts",
        headers=headers,
        json={"content": "Unified engagement endpoint"},
    ).json()["data"]["id"]

    comment = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "comment", "comment": "Looks great"},
    )
    assert comment.status_code == 200
    assert comment.json()["data"]["depth"] == 1

    repost = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "repost", "quote": "Sharing this"},
    )
    assert repost.status_code == 200
    assert repost.json()["data"]["postId"] == post_id


def test_engagement_blocked_when_disabled(client):
    headers = _signup(client, "engagement-disabled.user@university.edu")
    post_id = client.post(
        "/posts",
        headers=headers,
        json={"content": "No engagement allowed", "engagementEnabled": False, "status": "published"},
    ).json()["data"]["id"]

    like = client.post(
        f"/posts/{post_id}/engagements",
        headers=headers,
        json={"action": "like", "reaction": "like", "isLiked": True},
    )
    assert like.status_code == 403
