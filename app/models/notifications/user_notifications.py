import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class UserNotification(Base):
    __tablename__ = "user_notifications"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    notification_type = Column(String(80), default="send", nullable=False, index=True)
    target_type = Column(String(30), default="direct", nullable=False, index=True)
    topic = Column(String(150), nullable=True, index=True)
    template_key = Column(String(80), nullable=True, index=True)
    title = Column(String(150), nullable=False)
    body = Column(String(1000), nullable=False)
    html_body = Column(String, nullable=True)
    channels = Column(JSON, default=lambda: {"email": False, "inApp": True, "push": False}, nullable=False)
    delivery_status = Column(JSON, default=dict, nullable=False)
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="notifications")
