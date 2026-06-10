import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class UserDevice(Base):
    __tablename__ = "user_devices"
    __table_args__ = (
        UniqueConstraint("device_token", name="uq_user_devices_device_token"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_token = Column(String(4096), nullable=False, index=True)
    platform = Column(String(30), nullable=False)
    device_name = Column(String(150), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)
    last_accessed_ip = Column(String(45), nullable=True)
    session_id = Column(String(36), ForeignKey('user_sessions.id', ondelete='SET NULL'), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    last_used_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="devices")
    session = relationship("UserSession", back_populates="devices")
