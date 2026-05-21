import re
from datetime import datetime

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from ...models.model import Comment, Post, PostEditHistory, User
from ...models.schemas import CommentCreateRequest, PostAttachment, PostCreateRequest, PostUpdateRequest, ReplyCreateRequest
from .common import (
    clean_mentions,
    clean_tags,
    comment_or_404,
    ensure_post_engagement_enabled,
    ensure_post_write_access,
    extract_plain_text,
    get_comment_max_depth,
    media_items_from_payload,
    now_utc,
    post_for_edit_or_404,
    post_or_404,
    publish_gate,
    queue_moderation,
    replace_post_media,
    resolve_post_status,
    scan_content,
    validate_media,
)
from .serialization import post_to_schema


def apply_content(post: Post, payload: PostCreateRequest | PostUpdateRequest, partial: bool = False) -> None:
    content_format = payload.contentFormat if payload.contentFormat is not None else post.content_format
    content = payload.content if payload.content is not None else (post.body if partial else "")
    plain_text = extract_plain_text(content or "")
    if not plain_text and getattr(payload, "status", post.status) == "published":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post content is required")

    post.body = content or plain_text
    post.plain_text = plain_text
    post.content_format = content_format or "plain_text"

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
        replace_post_media(post, media_items_from_payload(payload))


def create_post(db: Session, current_user: User, payload: PostCreateRequest) -> Post:
    resolved_status = resolve_post_status(payload.status)
    post = Post(
        author_id=current_user.id,
        status=resolved_status,
        visibility=payload.visibility,
        engagement_enabled=payload.engagementEnabled,
    )
    apply_content(post, payload)
    post.moderation_status, post.moderation_reasons = scan_content(db, post.plain_text)
    publish_gate(resolved_status, post.moderation_status, post.moderation_reasons or [])
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
    post = post_for_edit_or_404(db, post_id)
    ensure_post_write_access(post, current_user)
    snapshot = jsonable_encoder(post_to_schema(db, post, include_comments=False, include_history=False))
    db.add(PostEditHistory(post_id=post.id, editor_user_id=current_user.id, snapshot=snapshot))
    legacy_history = list(post.edit_history or [])
    legacy_history.append({"editedAt": now_utc().isoformat(), "editorUserId": current_user.id, "snapshot": snapshot})
    post.edit_history = legacy_history

    previous_status = post.status
    if payload.visibility is not None:
        post.visibility = payload.visibility
    if payload.engagementEnabled is not None:
        post.engagement_enabled = payload.engagementEnabled
    if payload.status is not None:
        post.status = resolve_post_status(payload.status)
        if post.status in {"draft", "published"}:
            post.archived_at = None
            post.deleted_at = None
    apply_content(post, payload, partial=True)
    post.moderation_status, post.moderation_reasons = scan_content(db, post.plain_text)
    publish_gate(post.status, post.moderation_status, post.moderation_reasons or [])
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
    post.archived_at = now_utc()
    post.deleted_at = now_utc()
    if post.author_id == current_user.id:
        current_user.posts_count = max((current_user.posts_count or 1) - 1, 0)
    db.commit()


def list_feed(db: Session, cursor: datetime | None = None, limit: int = 20) -> dict:
    query = db.query(Post).filter(Post.status == "published", Post.deleted_at.is_(None))
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


def list_posts_compat(db: Session, page: int, page_size: int, author_id: str | None = None, hashtag: str | None = None) -> dict:
    query = db.query(Post).filter(Post.status == "published", Post.deleted_at.is_(None))
    if author_id:
        query = query.filter(Post.author_id == author_id)
    posts = query.order_by(Post.created_at.desc()).limit(page_size).all()
    items = [post_to_schema(db, post) for post in posts]
    if hashtag:
        tag = hashtag.strip().lstrip("#").lower()
        items = [item for item in items if tag in item["hashtags"]]
    return {"items": items, "pagination": {"page": page, "pageSize": page_size, "totalRecords": len(items), "totalPages": 1 if items else 0}}


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
    normalized_parent_comment_id = parent_comment_id
    if isinstance(normalized_parent_comment_id, str):
        raw_parent = normalized_parent_comment_id.strip()
        if raw_parent.lower() in {"", "none", "null", "string"}:
            normalized_parent_comment_id = None
    parent = None
    depth = 1
    if normalized_parent_comment_id:
        parent = comment_or_404(db, normalized_parent_comment_id)
        if parent.post_id != post.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent comment belongs to another post")
        depth = parent.depth + 1
    max_depth = get_comment_max_depth(db)
    if depth > max_depth:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Comments support up to {max_depth} levels")

    moderation_status, reasons = scan_content(db, content)
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


def update_comment(db: Session, current_user: User, post_id: str, comment_id: str, content: str) -> Comment:
    post_or_404(db, post_id)
    comment = comment_or_404(db, comment_id)
    if comment.post_id != post_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comment does not belong to this post")
    if comment.author_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author can edit this comment")
    comment.body = content
    comment.moderation_status, comment.moderation_reasons = scan_content(db, content)
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
