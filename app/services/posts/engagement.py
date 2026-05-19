from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models.model import Comment, CommentReaction, Post, PostReaction, Repost, User, UserNotification
from ...models.schemas import (
    CommentCreateRequest,
    CommentReactionRequest,
    EngagementRequest,
    PostReactionCompatRequest,
    PostReactionRequest,
    RepostCreateRequest,
)
from .common import ensure_post_engagement_enabled, post_or_404
from .content import create_comment
from .serialization import comment_to_schema, post_reaction_summary

RECOGNITION_THRESHOLDS = (5, 10, 25, 50, 100)


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


def upsert_post_reaction(db: Session, current_user: User, post_id: str, payload: PostReactionRequest) -> dict:
    reaction_type = (payload.reactionType or "like").strip().lower().replace("_", " ")
    if reaction_type == "remove like":
        return delete_post_reaction(db, current_user, post_id)
    if reaction_type == "comment":
        existing_comment = (
            db.query(Comment)
            .filter(Comment.post_id == post_id, Comment.author_id == current_user.id, Comment.is_deleted.is_(False))
            .first()
        )
        if existing_comment:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already commented on this post")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use /posts/{postId}/comments to add comment")
    if reaction_type == "repost":
        existing_repost = db.query(Repost).filter(Repost.post_id == post_id, Repost.user_id == current_user.id).first()
        if existing_repost:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already reposted this post")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Use /posts/{postId}/repost to repost")

    post = post_or_404(db, post_id)
    ensure_post_engagement_enabled(post)
    reaction = db.query(PostReaction).filter(PostReaction.post_id == post_id, PostReaction.user_id == current_user.id).first()
    if not reaction:
        reaction = PostReaction(post_id=post_id, user_id=current_user.id, reaction_type=reaction_type)
        db.add(reaction)
        post.like_count = (post.like_count or 0) + 1
        _send_positive_recognition(db, post, _recognition_milestone(post.like_count or 0))
    else:
        if reaction.reaction_type == "like" and reaction_type == "like":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already liked this post")
        reaction.reaction_type = reaction_type
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


def upsert_comment_reaction(db: Session, current_user: User, comment_id: str, payload: CommentReactionRequest) -> dict:
    from .common import comment_or_404

    comment = comment_or_404(db, comment_id)
    reaction = db.query(CommentReaction).filter(CommentReaction.comment_id == comment_id, CommentReaction.user_id == current_user.id).first()
    if not reaction:
        reaction = CommentReaction(comment_id=comment_id, user_id=current_user.id, reaction_type=payload.reactionType)
        db.add(reaction)
        comment.like_count = (comment.like_count or 0) + 1
    else:
        reaction.reaction_type = payload.reactionType
    db.commit()
    return {"commentId": comment_id, "likeCount": comment.like_count}


def delete_comment_reaction(db: Session, current_user: User, comment_id: str) -> dict:
    from .common import comment_or_404

    comment = comment_or_404(db, comment_id)
    reaction = db.query(CommentReaction).filter(CommentReaction.comment_id == comment_id, CommentReaction.user_id == current_user.id).first()
    if reaction:
        db.delete(reaction)
        comment.like_count = max((comment.like_count or 1) - 1, 0)
        db.commit()
    return {"commentId": comment_id, "likeCount": comment.like_count}


def create_repost(db: Session, current_user: User, post_id: str, payload: RepostCreateRequest) -> Repost:
    post = post_or_404(db, post_id)
    ensure_post_engagement_enabled(post)
    repost = db.query(Repost).filter(Repost.post_id == post_id, Repost.user_id == current_user.id).first()
    if repost:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already reposted this post")
    repost = Repost(post_id=post_id, user_id=current_user.id, quote=payload.quote)
    db.add(repost)
    post.repost_count = (post.repost_count or 0) + 1
    _send_positive_recognition(db, post, _recognition_milestone((post.like_count or 0) + (post.repost_count or 0)))
    db.commit()
    db.refresh(repost)
    return repost


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
            CommentCreateRequest(content=payload.comment, parentCommentId=payload.parentCommentId, attachments=payload.attachments),
        )
        return {"commentId": comment.id, "depth": comment.depth}
    repost = create_repost(db, current_user, post_id, RepostCreateRequest(quote=payload.quote))
    return {"postId": post_id, "quote": repost.quote}


def reaction_compat(db: Session, current_user: User, post_id: str, payload: PostReactionCompatRequest) -> dict:
    reaction_type = (payload.reactionType or "like").strip().lower()
    if reaction_type == "comment":
        if not payload.comment:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="comment is required for reactionType=comment")
        comment = create_comment(
            db,
            current_user,
            post_id,
            CommentCreateRequest(
                content=payload.comment,
                parentCommentId=payload.parentCommentId,
                attachments=payload.attachments or [],
            ),
        )
        return {"action": "comment", "comment": comment_to_schema(comment, {})}
    if reaction_type == "repost":
        repost = create_repost(db, current_user, post_id, RepostCreateRequest(quote=payload.quote))
        return {"action": "repost", "repost": {"id": repost.id, "postId": post_id, "quote": repost.quote}}
    return {"action": "reaction", **upsert_post_reaction(db, current_user, post_id, PostReactionRequest(reactionType=reaction_type))}
