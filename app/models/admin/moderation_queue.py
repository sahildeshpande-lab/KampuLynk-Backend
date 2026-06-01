import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class ModerationQueueItem(Base):
    __tablename__ = "moderation_queue"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    content_type = Column(String(30), nullable=False, index=True)
    content_id = Column(String(36), nullable=False, index=True)
    reporter_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(String(30), default="pending", nullable=False, index=True)
    reasons = Column(JSON, default=list, nullable=False)
    admin_action = Column(String(30), nullable=True)
    admin_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    admin_note = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
