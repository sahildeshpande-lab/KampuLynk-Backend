import re
from datetime import datetime, timezone
from html import unescape
from typing import Any

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.model import (
    Comment,
    CommentReaction,
    ModerationQueueItem,
    PlatformConfig,
    Post,
    PostEditHistory,
    PostMedia,
    PostReaction,
    Repost,
    User,
    UserNotification,
)
from ..models.schemas import (
    CommentCreateRequest,
    CommentReactionRequest,
    EngagementRequest,
    PostAttachment,
    PostCreateRequest,
    PostReactionRequest,
    PostUpdateRequest,
    ReplyCreateRequest,
    RepostCreateRequest,
)

IMAGE_LIMIT = 5
IMAGE_MAX_BYTES = 500 * 1024
ALLOWED_ATTACHMENT_TYPES = {"image", "pdf", "word", "ppt", "audio"}
DEFAULT_COMMENT_MAX_DEPTH = 3
SPAM_KEYWORDS = {"buy followers", "free crypto", "click this scam", "visit shady link"}
PROFANITY_KEYWORDS = {"damn", "shit"}
RECOGNITION_THRESHOLDS = (5, 10, 25, 50, 100)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _payload_dict(value):
    return value.model_dump() if hasattr(value, "model_dump") else value


def clean_tags(values: list[str] | None) -> list[str]:
    cleaned = []
    for value in values or []:
        tag = value.strip().lstrip("#").lower()
        if tag and tag not in cleaned:
            cleaned.append(tag[:80])
    return cleaned


def clean_mentions(values: list[str] | None, content: str = "") -> list[str]:
    cleaned = []
    candidates = list(values or []) + re.findall(r"@([A-Za-z0-9_.-]{2,80})", content or "")
    for value in candidates:
        mention = value.strip().lstrip("@").lower()
        if mention and mention not in cleaned:
            cleaned.append(mention[:80])
    return cleaned


def extract_plain_text(content: str, rich_text_html: str | None, rich_text_json: dict[str, Any] | None) -> str:
    if content:
        return content.strip()
    if rich_text_html:
        text = re.sub(r"<[^>]+>", " ", rich_text_html)
        return re.sub(r"\s+", " ", unescape(text)).strip()[:5000]
    if rich_text_json:
        parts: list[str] = []

        def walk(value):
            if isinstance(value, dict):
                text = value.get("text")
                if isinstance(text, str):
                    parts.append(text)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(rich_text_json)
        return re.sub(r"\s+", " ", " ".join(parts)).strip()[:5000]
    return ""


def validate_media(attachments: list[PostAttachment] | None) -> list[dict]:
    image_count = sum(1 for item in attachments or [] if item.type == "image")
    if image_count > IMAGE_LIMIT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A post can include up to 5 images")

    payload = []
    for item in attachments or []:
        if item.type not in ALLOWED_ATTACHMENT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported attachment type")
        if item.type == "image" and item.sizeBytes and item.sizeBytes > IMAGE_MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Images must be compressed to 500KB or less")
        payload.append(item.model_dump())
    return payload


def scan_content(text: str) -> tuple[str, list[str]]:
    lowered = (text or "").lower()
    reasons = []
    if any(keyword in lowered for keyword in SPAM_KEYWORDS):
        reasons.append("spam")
    if any(keyword in lowered for keyword in PROFANITY_KEYWORDS):
        reasons.append("profanity")
    status_value = "rejected" if reasons else "approved"
    return (status_value, reasons)


def _resolve_post_status(status_value: str | None) -> str:
    return "published" if status_value == "published" else "draft"


def _publish_gate(status_value: str, moderation_status: str, moderation_reasons: list[str]) -> None:
    if status_value == "published" and moderation_status != "approved":
        reason_text = ", ".join(moderation_reasons) if moderation_reasons else "moderation"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Post blocked by content safety checks: {reason_text}",
        )


def _recognition_milestone(current_like_count: int) -> int | None:
    matched = [value for value in RECOGNITION_THRESHOLDS if value <= current_like_count]
    return matched[-1] if matched else None


def _send_positive_recognition(db: Session, post: Post, milestone: int) -> None:
    if milestone is None:
        return
    event_key = f"post_like_milestone_{post.id}_{milestone}"
    exists = db.query(UserNotification).filter(
        UserNotification.user_id == post.author_id,
        UserNotification.notification_type == "engagement_milestone",
        UserNotification.template_key == event_key,
    ).first()
    if exists:
        return
    db.add(
        UserNotification(
            user_id=post.author_id,
            notification_type="engagement_milestone",
            target_type="direct",
            template_key=event_key,
            title="Your post is getting recognized",
            body=f"Your post reached {milestone} reactions, keep it up.",
            channels={"email": False, "inApp": True, "push": False},
            delivery_status={"status": "created", "milestone": milestone},
        )
    )


def queue_moderation(
    db: Session,
    content_type: str,
    content_id: str,
    reasons: list[str],
    reporter_user_id: str | None = None,
) -> None:
    if not reasons and reporter_user_id is None:
        return
    exists = db.query(ModerationQueueItem).filter(
        ModerationQueueItem.content_type == content_type,
        ModerationQueueItem.content_id == content_id,
        ModerationQueueItem.status == "pending",
    ).first()
    if exists:
        return
    db.add(
        ModerationQueueItem(
            content_type=content_type,
            content_id=content_id,
            reporter_user_id=reporter_user_id,
            reasons=reasons,
        )
    )


def get_comment_max_depth(db: Session) -> int:
    config = db.query(PlatformConfig).filter(PlatformConfig.key == "comment.maxDepth").first()
    if not config:
        config = PlatformConfig(
            key="comment.maxDepth",
            value={"value": DEFAULT_COMMENT_MAX_DEPTH},
            description="Maximum allowed nested comment depth.",
        )
        db.add(config)
        db.flush()
    value = config.value or {}
    try:
        return max(1, int(value.get("value", DEFAULT_COMMENT_MAX_DEPTH)))
    except (TypeError, ValueError):
        return DEFAULT_COMMENT_MAX_DEPTH


def post_or_404(db: Session, post_id: str) -> Post:
    post = db.query(Post).filter(
        Post.id == post_id,
        Post.status != "archived",
        Post.deleted_at.is_(None),
    ).first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def comment_or_404(db: Session, comment_id: str) -> Comment:
    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.is_deleted.is_(False)).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


def ensure_post_engagement_enabled(post: Post) -> None:
    if not post.engagement_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engagement is disabled for this post")


def ensure_post_write_access(post: Post, user: User) -> None:
    if post.author_id != user.id and user.role not in {"superadmin", "moderator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or admin can modify this post")


def _media_items_from_payload(payload: PostCreateRequest | PostUpdateRequest) -> list[dict]:
    media = getattr(payload, "media", None)
    attachments = getattr(payload, "attachments", None)
    return validate_media(media if media else attachments)


def _replace_post_media(post: Post, media_items: list[dict]) -> None:
    post.media.clear()
    for index, item in enumerate(media_items):
        post.media.append(
            PostMedia(
                media_type=item["type"],
                url=item["url"],
                name=item.get("name"),
                content_type=item.get("contentType"),
                size_bytes=item.get("sizeBytes"),
                media_metadata=item.get("metadata") or {},
                position=index,
            )
        )
    post.attachments = media_items


def _apply_content(post: Post, payload: PostCreateRequest | PostUpdateRequest, partial: bool = False) -> None:
    content_format = payload.contentFormat if payload.contentFormat is not None else post.content_format
    rich_text_json = payload.richTextJson if payload.richTextJson is not None else (post.rich_text_json if partial else None)
    rich_text_html = payload.richTextHtml if payload.richTextHtml is not None else (post.rich_text_html if partial else None)
    content = payload.content if payload.content is not None else (post.body if partial else "")
    plain_text = extract_plain_text(content or "", rich_text_html, rich_text_json)
    if not plain_text and getattr(payload, "status", post.status) == "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post content is required")

    post.body = content or plain_text
    post.plain_text = plain_text
    post.content_format = content_format or "plain_text"
    post.rich_text_json = rich_text_json
    post.rich_text_html = rich_text_html

    if payload.linkPreview is not None:
        post.link_preview = payload.linkPreview.model_dump()
    elif not partial:
        post.link_preview = None

    if payload.hashtags is not None:
        post.hashtags = clean_tags(payload.hashtags)
    elif not partial:
        post.hashtags = clean_tags(re.findall(r"#([A-Za-z0-9_-]{1,80})", plain_text))

    if payload.mentions is not None:
        post.mentions = clean_mentions(payload.mentions, plain_text)
    elif not partial:
        post.mentions = clean_mentions([], plain_text)

    if payload.topicTags is not None:
        post.topic_tags = clean_tags(payload.topicTags)
    elif not partial:
        post.topic_tags = []

    if getattr(payload, "attachments", None) is not None or getattr(payload, "media", None) is not None or not partial:
        _replace_post_media(post, _media_items_from_payload(payload))


def create_post(db: Session, current_user: User, payload: PostCreateRequest) -> Post:
    resolved_status = _resolve_post_status(payload.status)
    post = Post(
        author_id=current_user.id,
        status=resolved_status,
        visibility=payload.visibility,
        engagement_enabled=payload.engagementEnabled,
    )
    _apply_content(post, payload)
    post.moderation_status, post.moderation_reasons = scan_content(post.plain_text)
    _publish_gate(resolved_status, post.moderation_status, post.moderation_reasons or [])
    post.rescan_requested = resolved_status != "published"
    db.add(post)
    if resolved_status == "published":
        current_user.posts_count = (current_user.posts_count or 0) + 1
    db.flush()
    queue_moderation(db, "post", post.id, post.moderation_reasons or [])
    db.commit()
    db.refresh(post)
    return post


def update_post(db: Session, current_user: User, post_id: str, payload: PostUpdateRequest) -> Post:
    post = post_or_404(db, post_id)
    ensure_post_write_access(post, current_user)
    snapshot = jsonable_encoder(post_to_schema(db, post, include_comments=False, include_history=False))
    db.add(PostEditHistory(post_id=post.id, editor_user_id=current_user.id, snapshot=snapshot))
    legacy_history = list(post.edit_history or [])
    legacy_history.append({"editedAt": _now().isoformat(), "editorUserId": current_user.id, "snapshot": snapshot})
    post.edit_history = legacy_history

    previous_status = post.status
    if payload.visibility is not None:
        post.visibility = payload.visibility
    if payload.engagementEnabled is not None:
        post.engagement_enabled = payload.engagementEnabled
    if payload.status is not None:
        post.status = _resolve_post_status(payload.status)
    _apply_content(post, payload, partial=True)
    post.moderation_status, post.moderation_reasons = scan_content(post.plain_text)
    _publish_gate(post.status, post.moderation_status, post.moderation_reasons or [])
    post.rescan_requested = True
    if previous_status != "published" and post.status == "published":
        current_user.posts_count = (current_user.posts_count or 0) + 1
    if previous_status == "published" and post.status != "published":
        current_user.posts_count = max((current_user.posts_count or 1) - 1, 0)
    queue_moderation(db, "post", post.id, post.moderation_reasons or [])
    db.commit()
    db.refresh(post)
    return post


def delete_post(db: Session, current_user: User, post_id: str) -> None:
    post = post_or_404(db, post_id)
    ensure_post_write_access(post, current_user)
    post.status = "archived"
    post.archived_at = _now()
    post.deleted_at = _now()
    if post.author_id == current_user.id:
        current_user.posts_count = max((current_user.posts_count or 1) - 1, 0)
    db.commit()


def list_feed(db: Session, cursor: datetime | None = None, limit: int = 20) -> dict:
    query = db.query(Post).filter(
        Post.status == "published",
        Post.deleted_at.is_(None),
        Post.moderation_status != "deleted",
    )
    if cursor:
        query = query.filter(Post.created_at < cursor)
    rows = query.order_by(Post.created_at.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = items[-1].created_at.isoformat() if has_more and items else None
    return {
        "items": [post_to_schema(db, post) for post in items],
        "pagination": {"limit": limit, "nextCursor": next_cursor, "hasMore": has_more},
    }


def list_posts_compat(
    db: Session,
    page: int,
    page_size: int,
    author_id: str | None = None,
    hashtag: str | None = None,
) -> dict:
    query = db.query(Post).filter(Post.status == "published", Post.deleted_at.is_(None), Post.moderation_status != "deleted")
    if author_id:
        query = query.filter(Post.author_id == author_id)
    posts = query.order_by(Post.created_at.desc()).limit(page_size).all()
    items = [post_to_schema(db, post) for post in posts]
    if hashtag:
        tag = hashtag.strip().lstrip("#").lower()
        items = [item for item in items if tag in item["hashtags"]]
    return {
        "items": items,
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "totalRecords": len(items),
            "totalPages": 1 if items else 0,
        },
    }


def upsert_post_reaction(db: Session, current_user: User, post_id: str, payload: PostReactionRequest) -> dict:
    post = post_or_404(db, post_id)
    ensure_post_engagement_enabled(post)
    reaction = db.query(PostReaction).filter(PostReaction.post_id == post_id, PostReaction.user_id == current_user.id).first()
    if not reaction:
        reaction = PostReaction(post_id=post_id, user_id=current_user.id, reaction_type=payload.reactionType)
        db.add(reaction)
        post.like_count = (post.like_count or 0) + 1
        _send_positive_recognition(db, post, _recognition_milestone(post.like_count or 0))
    else:
        reaction.reaction_type = payload.reactionType
    db.commit()
    return post_reaction_summary(db, post_id)


def delete_post_reaction(db: Session, current_user: User, post_id: str) -> dict:
    post = post_or_404(db, post_id)
    reaction = db.query(PostReaction).filter(PostReaction.post_id == post_id, PostReaction.user_id == current_user.id).first()
    if reaction:
        db.delete(reaction)
        post.like_count = max((post.like_count or 1) - 1, 0)
        db.commit()
    return post_reaction_summary(db, post_id)


def create_comment(db: Session, current_user: User, post_id: str, payload: CommentCreateRequest) -> Comment:
    post = post_or_404(db, post_id)
    return _create_comment(db, current_user, post, payload.content, payload.attachments, payload.parentCommentId)


def create_reply(db: Session, current_user: User, comment_id: str, payload: ReplyCreateRequest) -> Comment:
    parent = comment_or_404(db, comment_id)
    post = post_or_404(db, parent.post_id)
    return _create_comment(db, current_user, post, payload.content, payload.attachments, parent.id)


def _create_comment(
    db: Session,
    current_user: User,
    post: Post,
    content: str,
    attachments: list[PostAttachment],
    parent_comment_id: str | None,
) -> Comment:
    ensure_post_engagement_enabled(post)
    parent = None
    depth = 1
    if parent_comment_id:
        parent = comment_or_404(db, parent_comment_id)
        if parent.post_id != post.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent comment belongs to another post")
        depth = parent.depth + 1
    max_depth = get_comment_max_depth(db)
    if depth > max_depth:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Comments support up to {max_depth} levels")

    moderation_status, reasons = scan_content(content)
    comment = Comment(
        post_id=post.id,
        author_id=current_user.id,
        parent_comment_id=parent.id if parent else None,
        body=content,
        depth=depth,
        attachments=validate_media(attachments),
        moderation_status=moderation_status,
        moderation_reasons=reasons,
    )
    db.add(comment)
    post.comment_count = (post.comment_count or 0) + 1
    if parent:
        parent.reply_count = (parent.reply_count or 0) + 1
    db.flush()
    queue_moderation(db, "comment", comment.id, reasons)
    db.commit()
    db.refresh(comment)
    return comment


def upsert_comment_reaction(db: Session, current_user: User, comment_id: str, payload: CommentReactionRequest) -> dict:
    comment = comment_or_404(db, comment_id)
    reaction = db.query(CommentReaction).filter(
        CommentReaction.comment_id == comment_id,
        CommentReaction.user_id == current_user.id,
    ).first()
    if not reaction:
        reaction = CommentReaction(comment_id=comment_id, user_id=current_user.id, reaction_type=payload.reactionType)
        db.add(reaction)
        comment.like_count = (comment.like_count or 0) + 1
    else:
        reaction.reaction_type = payload.reactionType
    db.commit()
    return {"commentId": comment_id, "likeCount": comment.like_count}


def delete_comment_reaction(db: Session, current_user: User, comment_id: str) -> dict:
    comment = comment_or_404(db, comment_id)
    reaction = db.query(CommentReaction).filter(
        CommentReaction.comment_id == comment_id,
        CommentReaction.user_id == current_user.id,
    ).first()
    if reaction:
        db.delete(reaction)
        comment.like_count = max((comment.like_count or 1) - 1, 0)
        db.commit()
    return {"commentId": comment_id, "likeCount": comment.like_count}


def update_comment(db: Session, current_user: User, post_id: str, comment_id: str, content: str) -> Comment:
    post_or_404(db, post_id)
    comment = comment_or_404(db, comment_id)
    if comment.post_id != post_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment does not belong to this post")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can edit this comment")
    comment.body = content
    comment.moderation_status, comment.moderation_reasons = scan_content(content)
    queue_moderation(db, "comment", comment.id, comment.moderation_reasons or [])
    db.commit()
    db.refresh(comment)
    return comment


def delete_comment(db: Session, current_user: User, post_id: str, comment_id: str) -> None:
    post = post_or_404(db, post_id)
    comment = comment_or_404(db, comment_id)
    if comment.post_id != post_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment does not belong to this post")
    if comment.author_id != current_user.id and current_user.role not in {"superadmin", "moderator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or admin can delete this comment")
    comment.is_deleted = True
    post.comment_count = max((post.comment_count or 1) - 1, 0)
    if comment.parent:
        comment.parent.reply_count = max((comment.parent.reply_count or 1) - 1, 0)
    db.commit()


def create_repost(db: Session, current_user: User, post_id: str, payload: RepostCreateRequest) -> Repost:
    post = post_or_404(db, post_id)
    ensure_post_engagement_enabled(post)
    repost = db.query(Repost).filter(Repost.post_id == post_id, Repost.user_id == current_user.id).first()
    if repost:
        repost.quote = payload.quote
    else:
        repost = Repost(post_id=post_id, user_id=current_user.id, quote=payload.quote)
        db.add(repost)
        post.repost_count = (post.repost_count or 0) + 1
        _send_positive_recognition(db, post, _recognition_milestone((post.like_count or 0) + (post.repost_count or 0)))
    db.commit()
    db.refresh(repost)
    return repost


def report_post(db: Session, current_user: User, post_id: str, reasons: list[str]) -> None:
    post = post_or_404(db, post_id)
    if post.author_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot report your own post")
    post.is_flagged = True
    post.report_count = int(post.report_count or 0) + 1
    post.moderation_status = "pending"
    queue_moderation(db, "post", post.id, reasons, reporter_user_id=current_user.id)
    db.commit()


def report_comment(db: Session, current_user: User, comment_id: str, reasons: list[str]) -> None:
    comment = comment_or_404(db, comment_id)
    if comment.author_id == current_user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You cannot report your own comment")
    comment.is_flagged = True
    comment.report_count = int(comment.report_count or 0) + 1
    comment.moderation_status = "pending"
    queue_moderation(db, "comment", comment.id, reasons, reporter_user_id=current_user.id)
    db.commit()


def list_moderation_queue(
    db: Session,
    content_type: str | None = None,
    moderation_status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = db.query(ModerationQueueItem)
    if content_type:
        query = query.filter(ModerationQueueItem.content_type == content_type)
    items = query.order_by(ModerationQueueItem.created_at.desc()).all()

    rows: list[dict] = []
    for item in items:
        if item.content_type == "post":
            post = db.query(Post).filter(Post.id == item.content_id).first()
            if not post:
                continue
            if not post.is_flagged:
                continue
            if moderation_status and post.moderation_status != moderation_status:
                continue
            rows.append(
                {
                    "id": post.id,
                    "type": "post",
                    "content": post.body,
                    "reportCount": int(post.report_count or 0),
                    "moderationStatus": post.moderation_status,
                    "createdAt": post.created_at,
                }
            )
            continue
        if item.content_type == "comment":
            comment = db.query(Comment).filter(Comment.id == item.content_id).first()
            if not comment:
                continue
            if not comment.is_flagged:
                continue
            if moderation_status and comment.moderation_status != moderation_status:
                continue
            rows.append(
                {
                    "id": comment.id,
                    "type": "comment",
                    "content": comment.body,
                    "reportCount": int(comment.report_count or 0),
                    "moderationStatus": comment.moderation_status,
                    "createdAt": comment.created_at,
                }
            )

    total = len(rows)
    offset = (page - 1) * page_size
    return {
        "items": rows[offset: offset + page_size],
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "totalRecords": total,
            "totalPages": (total + page_size - 1) // page_size if total else 0,
        },
    }


def review_moderated_content(
    db: Session,
    admin_user: User,
    content_id: str,
    content_type: str,
    action: str,
    note: str | None = None,
) -> None:
    queue_item = (
        db.query(ModerationQueueItem)
        .filter(
            ModerationQueueItem.content_type == content_type,
            ModerationQueueItem.content_id == content_id,
            ModerationQueueItem.status == "pending",
        )
        .order_by(ModerationQueueItem.created_at.desc())
        .first()
    )

    if content_type == "post":
        post = db.query(Post).filter(Post.id == content_id).first()
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        if action == "reinstate":
            post.is_flagged = False
            post.moderation_status = "reviewed"
        elif action == "delete":
            post.moderation_status = "deleted"
            if not post.deleted_at:
                post.deleted_at = _now()
            post.is_flagged = False
        elif action == "escalate":
            post.moderation_status = "escalated"
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
    elif content_type == "comment":
        comment = db.query(Comment).filter(Comment.id == content_id).first()
        if not comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
        if action == "reinstate":
            comment.is_flagged = False
            comment.moderation_status = "reviewed"
        elif action == "delete":
            comment.is_deleted = True
            comment.moderation_status = "deleted"
            comment.is_flagged = False
        elif action == "escalate":
            comment.moderation_status = "escalated"
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid action")
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid content type")

    if queue_item:
        queue_item.status = "reviewed"
        queue_item.admin_action = action
        queue_item.admin_user_id = admin_user.id
        queue_item.admin_note = note
        queue_item.resolved_at = _now()
    db.commit()


def post_reaction_summary(db: Session, post_id: str) -> dict:
    rows = (
        db.query(PostReaction.reaction_type, func.count(PostReaction.id))
        .filter(PostReaction.post_id == post_id)
        .group_by(PostReaction.reaction_type)
        .all()
    )
    reactions = {reaction or "like": count for reaction, count in rows}
    return {"likeCount": sum(reactions.values()), "reactions": reactions}


def user_reactions(db: Session, post_id: str) -> list[dict]:
    rows = db.query(PostReaction).filter(PostReaction.post_id == post_id).order_by(PostReaction.created_at.desc()).all()
    return [
        {
            "userId": row.user_id,
            "reaction": row.reaction_type,
            "reactionType": row.reaction_type,
            "isLiked": row.reaction_type == "like",
            "createdAt": row.created_at,
            "updatedAt": row.updated_at,
        }
        for row in rows
    ]


def media_to_schema(post: Post) -> list[dict]:
    if post.media:
        return [
            {
                "id": item.id,
                "type": item.media_type,
                "url": item.url,
                "name": item.name,
                "contentType": item.content_type,
                "sizeBytes": item.size_bytes,
                "metadata": item.media_metadata or {},
                "position": item.position,
            }
            for item in post.media
        ]
    return post.attachments or []


def comment_to_schema(comment: Comment, children_by_parent: dict[str, list[Comment]]) -> dict:
    return {
        "id": comment.id,
        "postId": comment.post_id,
        "authorId": comment.author_id,
        "parentCommentId": comment.parent_comment_id,
        "body": comment.body,
        "content": comment.body,
        "depth": comment.depth,
        "replyCount": comment.reply_count or 0,
        "likeCount": comment.like_count or 0,
        "attachments": comment.attachments or [],
        "moderationStatus": comment.moderation_status,
        "moderationReasons": comment.moderation_reasons or [],
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
        "replies": [comment_to_schema(child, children_by_parent) for child in children_by_parent.get(comment.id, [])],
    }


def comments_tree(db: Session, post_id: str) -> list[dict]:
    comments = (
        db.query(Comment)
        .filter(Comment.post_id == post_id, Comment.is_deleted.is_(False))
        .order_by(Comment.created_at.asc())
        .all()
    )
    children_by_parent: dict[str, list[Comment]] = {}
    roots = []
    for comment in comments:
        if comment.parent_comment_id:
            children_by_parent.setdefault(comment.parent_comment_id, []).append(comment)
        else:
            roots.append(comment)
    return [comment_to_schema(comment, children_by_parent) for comment in roots]


def post_to_schema(db: Session, post: Post, include_comments: bool = False, include_history: bool = True) -> dict:
    data = {
        "id": post.id,
        "authorId": post.author_id,
        "body": post.body,
        "content": post.body,
        "plainText": post.plain_text,
        "visibility": post.visibility,
        "engagementEnabled": post.engagement_enabled,
        "contentFormat": post.content_format,
        "richTextJson": post.rich_text_json,
        "richTextHtml": post.rich_text_html,
        "attachments": media_to_schema(post),
        "media": media_to_schema(post),
        "linkPreview": post.link_preview,
        "hashtags": post.hashtags or [],
        "mentions": post.mentions or [],
        "topicTags": post.topic_tags or [],
        "status": post.status,
        "moderationStatus": post.moderation_status,
        "moderationReasons": post.moderation_reasons or [],
        "editHistory": post.edit_history or [],
        "rescanRequested": post.rescan_requested,
        "safetyScan": {
            "status": post.moderation_status,
            "reasons": post.moderation_reasons or [],
            "manualRescanAvailable": True,
        },
        "likeCount": post.like_count or 0,
        "commentCount": post.comment_count or 0,
        "repostCount": post.repost_count or 0,
        "createdAt": post.created_at,
        "lastModifiedAt": post.updated_at,
        "updatedAt": post.updated_at,
        "deletedAt": post.deleted_at,
        "userEngagements": user_reactions(db, post.id),
        **post_reaction_summary(db, post.id),
    }
    if include_history:
        data["editHistorySnapshots"] = [
            {"id": row.id, "editorUserId": row.editor_user_id, "snapshot": row.snapshot, "createdAt": row.created_at}
            for row in db.query(PostEditHistory).filter(PostEditHistory.post_id == post.id).order_by(PostEditHistory.created_at.desc()).all()
        ]
    if include_comments:
        data["comments"] = comments_tree(db, post.id)
    return data


def engagement_compat(db: Session, current_user: User, post_id: str, payload: EngagementRequest) -> dict:
    if payload.action == "like":
        if payload.isLiked:
            request = PostReactionRequest(reactionType=payload.reaction or "like")
            return upsert_post_reaction(db, current_user, post_id, request)
        return delete_post_reaction(db, current_user, post_id)
    if payload.action == "comment":
        if not payload.comment:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="comment is required for comment action")
        comment = create_comment(
            db,
            current_user,
            post_id,
            CommentCreateRequest(
                content=payload.comment,
                parentCommentId=payload.parentCommentId,
                attachments=payload.attachments,
            ),
        )
        return {"commentId": comment.id, "depth": comment.depth}
    repost = create_repost(db, current_user, post_id, RepostCreateRequest(quote=payload.quote))
    return {"postId": post_id, "quote": repost.quote}


def manual_rescan_post(db: Session, current_user: User, post_id: str) -> Post:
    post = post_or_404(db, post_id)
    ensure_post_write_access(post, current_user)
    moderation_status, reasons = scan_content(post.plain_text)
    post.moderation_status = moderation_status
    post.moderation_reasons = reasons
    post.rescan_requested = False
    _publish_gate(post.status, moderation_status, reasons or [])
    queue_moderation(db, "post", post.id, reasons or [])
    db.commit()
    db.refresh(post)
    return post
