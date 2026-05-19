from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models.model import Comment, ModerationQueueItem, Post, User
from .common import comment_or_404, ensure_post_write_access, now_utc, post_or_404, publish_gate, queue_moderation, scan_content


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
            if post and post.is_flagged and (not moderation_status or post.moderation_status == moderation_status):
                rows.append({"id": post.id, "type": "post", "content": post.body, "reportCount": int(post.report_count or 0), "moderationStatus": post.moderation_status, "createdAt": post.created_at})
            continue
        if item.content_type == "comment":
            comment = db.query(Comment).filter(Comment.id == item.content_id).first()
            if comment and comment.is_flagged and (not moderation_status or comment.moderation_status == moderation_status):
                rows.append({"id": comment.id, "type": "comment", "content": comment.body, "reportCount": int(comment.report_count or 0), "moderationStatus": comment.moderation_status, "createdAt": comment.created_at})
    total = len(rows)
    offset = (page - 1) * page_size
    return {"items": rows[offset: offset + page_size], "pagination": {"page": page, "pageSize": page_size, "totalRecords": total, "totalPages": (total + page_size - 1) // page_size if total else 0}}


def review_moderated_content(db: Session, admin_user: User, content_id: str, content_type: str, action: str, note: str | None = None) -> None:
    queue_item = (
        db.query(ModerationQueueItem)
        .filter(ModerationQueueItem.content_type == content_type, ModerationQueueItem.content_id == content_id, ModerationQueueItem.status == "pending")
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
                post.deleted_at = now_utc()
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
        queue_item.resolved_at = now_utc()
    db.commit()


def manual_rescan_post(db: Session, current_user: User, post_id: str) -> Post:
    post = post_or_404(db, post_id)
    ensure_post_write_access(post, current_user)
    moderation_status, reasons = scan_content(db, post.plain_text)
    post.moderation_status = moderation_status
    post.moderation_reasons = reasons
    post.rescan_requested = False
    publish_gate(post.status, moderation_status, reasons or [])
    queue_moderation(db, "post", post.id, reasons or [])
    db.commit()
    db.refresh(post)
    return post
