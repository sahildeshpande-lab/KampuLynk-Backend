import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        Index("ix_posts_author_created_at", "author_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(String(5000), nullable=False)
    plain_text = Column(String(5000), nullable=False, default="")
    visibility = Column(String(30), default="public", nullable=False, index=True)
    engagement_enabled = Column(Boolean, default=True, nullable=False)
    content_format = Column(String(30), default="plain_text", nullable=False)
    attachments = Column(JSON, default=list, nullable=False)
    link_preview = Column(JSON, nullable=True)
    hashtags = Column(JSON, default=list, nullable=False)
    mentions = Column(JSON, default=list, nullable=False)
    topic_tags = Column(JSON, default=list, nullable=False)
    status = Column(String(30), default="draft", nullable=False, index=True)
    moderation_status = Column(String(30), default="in queue", nullable=False, index=True)
    moderation_reasons = Column(JSON, default=list, nullable=False)
    is_flagged = Column(Boolean, default=False, nullable=False, index=True)
    report_count = Column(Integer, default=0, nullable=False)
    edit_history = Column(JSON, default=list, nullable=False)
    rescan_requested = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    like_count = Column(Integer, default=0, nullable=False)
    comment_count = Column(Integer, default=0, nullable=False)
    repost_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    author = relationship("User", back_populates="posts", foreign_keys=[author_id])
    media = relationship("PostMedia", back_populates="post", cascade="all, delete-orphan", order_by="PostMedia.position")
    reactions = relationship("PostReaction", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="post", cascade="all, delete-orphan")
    edit_snapshots = relationship("PostEditHistory", back_populates="post", cascade="all, delete-orphan")
    reposts = relationship("Repost", back_populates="post", cascade="all, delete-orphan")
