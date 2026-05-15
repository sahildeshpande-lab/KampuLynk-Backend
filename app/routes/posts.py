from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import ModerationQueueItem, Post, PostComment, PostEngagement, Repost, User
from ..models.schemas import (
    ApiResponse,
    EngagementRequest,
    PostCreateRequest,
)
from .shared import api_response, get_current_user

POST_TAG = "7] Posts"

router = APIRouter(tags=[POST_TAG])

IMAGE_LIMIT = 5
IMAGE_MAX_BYTES = 500 * 1024
ALLOWED_ATTACHMENT_TYPES = {"image", "pdf", "word", "ppt", "audio"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_tags(values: list[str]) -> list[str]:
    cleaned = []
    for value in values:
        tag = value.strip().lstrip("#").lower()
        if tag and tag not in cleaned:
            cleaned.append(tag[:80])
    return cleaned


def _validate_attachments(attachments: list[PostAttachment]) -> list[dict]:
    image_count = sum(1 for item in attachments if item.type == "image")
    if image_count > IMAGE_LIMIT:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="A post can include up to 5 images")

    payload = []
    for item in attachments:
        if item.type not in ALLOWED_ATTACHMENT_TYPES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported attachment type")
        if item.type == "image" and item.sizeBytes and item.sizeBytes > IMAGE_MAX_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Images must be compressed to 500KB or less")
        payload.append(item.model_dump())
    return payload


def _scan_content(text: str) -> tuple[str, list[str]]:
    return ("approved", [])


def _user_engagements(db: Session, post_id: str) -> list[dict]:
    rows = (
        db.query(PostEngagement)
        .filter(PostEngagement.post_id == post_id, PostEngagement.is_liked.is_(True))
        .order_by(PostEngagement.created_at.desc())
        .all()
    )
    return [
        {
            "userId": row.user_id,
            "reaction": row.reaction or "like",
            "isLiked": row.is_liked,
            "createdAt": row.created_at,
            "updatedAt": row.updated_at,
        }
        for row in rows
    ]


def _queue_moderation(db: Session, content_type: str, content_id: str, reasons: list[str], reporter_user_id: str | None = None) -> None:
    if db.query(ModerationQueueItem).filter(
        ModerationQueueItem.content_type == content_type,
        ModerationQueueItem.content_id == content_id,
        ModerationQueueItem.status == "pending",
    ).first():
        return
    db.add(
        ModerationQueueItem(
            content_type=content_type,
            content_id=content_id,
            reporter_user_id=reporter_user_id,
            reasons=reasons,
        )
    )


def _post_or_404(db: Session, post_id: str) -> Post:
    post = db.query(Post).filter(Post.id == post_id, Post.status != "archived").first()
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return post


def _comment_or_404(db: Session, comment_id: str) -> PostComment:
    comment = db.query(PostComment).filter(PostComment.id == comment_id, PostComment.is_deleted.is_(False)).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")
    return comment


def _engagement_summary(db: Session, post_id: str) -> dict:
    rows = (
        db.query(PostEngagement.reaction, func.count(PostEngagement.id))
        .filter(PostEngagement.post_id == post_id, PostEngagement.is_liked.is_(True))
        .group_by(PostEngagement.reaction)
        .all()
    )
    reactions = {reaction or "like": count for reaction, count in rows}
    return {"likeCount": sum(reactions.values()), "reactions": reactions}


def _comment_to_schema(comment: PostComment, children_by_parent: dict[str, list[PostComment]]) -> dict:
    return {
        "id": comment.id,
        "postId": comment.post_id,
        "authorId": comment.author_id,
        "parentCommentId": comment.parent_comment_id,
        "body": comment.body,
        "depth": comment.depth,
        "attachments": comment.attachments or [],
        "moderationStatus": comment.moderation_status,
        "moderationReasons": comment.moderation_reasons or [],
        "createdAt": comment.created_at,
        "updatedAt": comment.updated_at,
        "replies": [_comment_to_schema(child, children_by_parent) for child in children_by_parent.get(comment.id, [])],
    }


def _comments_tree(db: Session, post_id: str) -> list[dict]:
    comments = (
        db.query(PostComment)
        .filter(PostComment.post_id == post_id, PostComment.is_deleted.is_(False))
        .order_by(PostComment.created_at.asc())
        .all()
    )
    children_by_parent: dict[str, list[PostComment]] = {}
    roots = []
    for comment in comments:
        if comment.parent_comment_id:
            children_by_parent.setdefault(comment.parent_comment_id, []).append(comment)
        else:
            roots.append(comment)
    return [_comment_to_schema(comment, children_by_parent) for comment in roots]


def _post_to_schema(db: Session, post: Post, include_comments: bool = False) -> dict:
    data = {
        "id": post.id,
        "authorId": post.author_id,
        "body": post.body,
        "content": post.body,
        "engagementEnabled": post.engagement_enabled,
        "contentFormat": post.content_format,
        "richTextJson": post.rich_text_json,
        "richTextHtml": post.rich_text_html,
        "attachments": post.attachments or [],
        "linkPreview": post.link_preview,
        "hashtags": post.hashtags or [],
        "topicTags": post.topic_tags or [],
        "status": post.status,
        "moderationStatus": post.moderation_status,
        "moderationReasons": post.moderation_reasons or [],
        "editHistory": post.edit_history or [],
        "rescanRequested": post.rescan_requested,
        "commentCount": db.query(PostComment).filter(PostComment.post_id == post.id, PostComment.is_deleted.is_(False)).count(),
        "repostCount": db.query(Repost).filter(Repost.post_id == post.id).count(),
        "createdAt": post.created_at,
        "lastModifiedAt": post.updated_at,
        "userEngagements": _user_engagements(db, post.id),
        **_engagement_summary(db, post.id),
    }
    if include_comments:
        data["comments"] = _comments_tree(db, post.id)
    return data


def _apply_post_content(post: Post, payload: PostCreateRequest) -> None:
    post.body = payload.content
    post.content_format = payload.contentFormat
    post.rich_text_json = payload.richTextJson
    post.rich_text_html = payload.richTextHtml
    post.attachments = _validate_attachments(payload.attachments)
    post.link_preview = payload.linkPreview.model_dump() if payload.linkPreview else None
    post.hashtags = _clean_tags(payload.hashtags)
    post.topic_tags = _clean_tags(payload.topicTags)


@router.get("/posts", response_model=ApiResponse)
def list_posts(
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
    authorId: str | None = Query(default=None),
    hashtag: str | None = Query(default=None),
):
    query = db.query(Post).filter(Post.status == "published", Post.moderation_status != "deleted")
    if authorId:
        query = query.filter(Post.author_id == authorId)
    total = query.count()
    posts = query.order_by(Post.created_at.desc()).offset((page - 1) * pageSize).limit(pageSize).all()
    items = [_post_to_schema(db, post) for post in posts]
    if hashtag:
        tag = hashtag.strip().lstrip("#").lower()
        items = [item for item in items if tag in item["hashtags"]]
        total = len(items)
    return api_response(
        "Posts fetched" if items else "Data not found",
        {
            "items": items,
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "totalRecords": total,
                "totalPages": (total + pageSize - 1) // pageSize if total else 0,
            },
        },
    )


@router.post("/posts", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def create_post(payload: PostCreateRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    moderation_status, reasons = _scan_content(payload.content)
    post = Post(
        author_id=current_user.id,
        status=payload.status,
        engagement_enabled=payload.engagementEnabled,
        moderation_status=moderation_status,
        moderation_reasons=reasons,
    )
    _apply_post_content(post, payload)
    db.add(post)
    if payload.status == "published":
        current_user.posts_count = (current_user.posts_count or 0) + 1
    db.flush()
    if reasons:
        _queue_moderation(db, "post", post.id, reasons)
    db.commit()
    db.refresh(post)
    return api_response("Post created", _post_to_schema(db, post))


@router.get("/posts/{postId}", response_model=ApiResponse)
def get_post(postId: str, db: Session = Depends(get_db)):
    post = _post_or_404(db, postId)
    return api_response("Post fetched", _post_to_schema(db, post, include_comments=True))


@router.delete("/posts/{postId}", response_model=ApiResponse)
def archive_post(postId: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _post_or_404(db, postId)
    if post.author_id != current_user.id and current_user.role not in {"superadmin", "moderator"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the author or admin can archive this post")
    post.status = "archived"
    post.archived_at = _now()
    if post.author_id == current_user.id:
        current_user.posts_count = max((current_user.posts_count or 1) - 1, 0)
    db.commit()
    return api_response("Post archived")


@router.post("/posts/{postId}/engagements", response_model=ApiResponse)
def upsert_engagement(
    postId: str,
    payload: EngagementRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    post = _post_or_404(db, postId)
    if not post.engagement_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Engagement is disabled for this post")

    if payload.action == "like":
        engagement = db.query(PostEngagement).filter(PostEngagement.post_id == postId, PostEngagement.user_id == current_user.id).first()
        if not engagement:
            engagement = PostEngagement(post_id=postId, user_id=current_user.id)
            db.add(engagement)
        engagement.reaction = payload.reaction
        engagement.is_liked = payload.isLiked
        db.commit()
        return api_response("Engagement updated", _engagement_summary(db, postId))

    if payload.action == "comment":
        if not payload.comment:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="comment is required for comment action")
        parent = None
        depth = 1
        if payload.parentCommentId:
            parent = _comment_or_404(db, payload.parentCommentId)
            if parent.post_id != postId:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parent comment belongs to another post")
            depth = parent.depth + 1
        if depth > 3:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Comments support up to 3 levels")
        moderation_status, reasons = _scan_content(payload.comment)
        comment = PostComment(
            post_id=postId,
            author_id=current_user.id,
            parent_comment_id=parent.id if parent else None,
            body=payload.comment,
            depth=depth,
            attachments=_validate_attachments(payload.attachments),
            moderation_status=moderation_status,
            moderation_reasons=reasons,
        )
        db.add(comment)
        db.flush()
        if reasons:
            _queue_moderation(db, "comment", comment.id, reasons)
        db.commit()
        return api_response("Comment created", {"commentId": comment.id, "depth": comment.depth})

    repost = db.query(Repost).filter(Repost.post_id == postId, Repost.user_id == current_user.id).first()
    if repost:
        repost.quote = payload.quote
        message = "Repost updated"
    else:
        repost = Repost(post_id=postId, user_id=current_user.id, quote=payload.quote)
        db.add(repost)
        message = "Post reposted"
    db.commit()
    return api_response(message, {"postId": postId, "quote": repost.quote})
