import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class PostDraft(Base):
    __tablename__ = "post_drafts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(String(5000), default="", nullable=False)
    content_format = Column(String(30), default="plain_text", nullable=False)
    attachments = Column(JSON, default=list, nullable=False)
    link_preview = Column(JSON, nullable=True)
    hashtags = Column(JSON, default=list, nullable=False)
    topic_tags = Column(JSON, default=list, nullable=False)
    autosave_interval_seconds = Column(Integer, default=30, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    author = relationship("User")
