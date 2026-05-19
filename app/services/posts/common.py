import os
import re
from datetime import datetime, timezone
from html import unescape
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...config import load_env_files
from ...models.model import Comment, ModerationQueueItem, PlatformConfig, Post, PostMedia, User
from ...models.schemas import PostAttachment, PostCreateRequest, PostUpdateRequest

load_env_files()

IMAGE_LIMIT = 5
IMAGE_MAX_BYTES = 500 * 1024
ALLOWED_ATTACHMENT_TYPES = {"image", "pdf", "word", "ppt", "audio"}
DEFAULT_COMMENT_MAX_DEPTH = max(1, int(os.getenv("DEFAULT_COMMENT_MAX_DEPTH", "3")))
SPAM_KEYWORDS = {"buy followers", "free crypto", "click this scam", "visit shady link"}
PROFANITY_KEYWORDS = {"damn", "free", "money", "spam"}
DEFAULT_BLOCKLIST_TERMS = sorted(SPAM_KEYWORDS | PROFANITY_KEYWORDS)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


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


def _normalize_scan_text(text: str) -> tuple[str, str]:
    lowered = (text or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered), re.sub(r"[^a-z0-9]+", "", lowered)


def _normalize_blocklist_term(value: str) -> tuple[str, str]:
    lowered = (value or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip(), re.sub(r"[^a-z0-9]+", "", lowered)


def _configured_blocklist(db: Session) -> list[str]:
    config = db.query(PlatformConfig).filter(PlatformConfig.key == "moderation.blocklist").first()
    if not config or not isinstance(config.value, dict):
        return DEFAULT_BLOCKLIST_TERMS
    terms = config.value.get("terms")
    if not isinstance(terms, list):
        return DEFAULT_BLOCKLIST_TERMS
    cleaned = []
    for term in terms:
        if isinstance(term, str):
            normalized = term.strip().lower()
            if normalized and normalized not in cleaned:
                cleaned.append(normalized)
    return cleaned or DEFAULT_BLOCKLIST_TERMS


def scan_content(db: Session, text: str) -> tuple[str, list[str]]:
    _, compact_stream = _normalize_scan_text(text)
    word_stream, _ = _normalize_scan_text(text)
    reasons = []
    blocked_terms = []
    for term in _configured_blocklist(db):
        spaced_term, compact_term = _normalize_blocklist_term(term)
        if (spaced_term and spaced_term in word_stream) or (compact_term and compact_term in compact_stream):
            blocked_terms.append(term)
    if blocked_terms:
        reasons.append("blocklist")
    if any(keyword in compact_stream for keyword in [re.sub(r"[^a-z0-9]+", "", term) for term in SPAM_KEYWORDS]):
        reasons.append("spam")
    if any(keyword in compact_stream for keyword in [re.sub(r"[^a-z0-9]+", "", term) for term in PROFANITY_KEYWORDS]):
        reasons.append("profanity")
    return ("rejected" if reasons else "approved", reasons)


def resolve_post_status(status_value: str | None) -> str:
    return "published" if status_value == "published" else "draft"


def publish_gate(status_value: str, moderation_status: str, moderation_reasons: list[str]) -> None:
    if status_value == "published" and moderation_status != "approved":
        reason_text = ", ".join(moderation_reasons) if moderation_reasons else "moderation"
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Post blocked by content safety checks: {reason_text}")


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
    if not exists:
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
    try:
        return max(1, int((config.value or {}).get("value", DEFAULT_COMMENT_MAX_DEPTH)))
    except (TypeError, ValueError):
        return DEFAULT_COMMENT_MAX_DEPTH


def post_or_404(db: Session, post_id: str) -> Post:
    post = db.query(Post).filter(Post.id == post_id, Post.status != "archived", Post.deleted_at.is_(None)).first()
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


def media_items_from_payload(payload: PostCreateRequest | PostUpdateRequest) -> list[dict]:
    media = getattr(payload, "media", None)
    attachments = getattr(payload, "attachments", None)
    return validate_media(media if media else attachments)


def replace_post_media(post: Post, media_items: list[dict]) -> None:
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
