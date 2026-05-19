from sqlalchemy import func
from sqlalchemy.orm import Session

from ...models.model import Comment, Post, PostEditHistory, PostReaction


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
