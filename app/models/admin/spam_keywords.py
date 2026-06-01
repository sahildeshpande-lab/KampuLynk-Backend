import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class SpamKeyword(Base):
    __tablename__ = "spam_keywords"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    keyword = Column(String(255), unique=True, nullable=False, index=True)
    keyword_type = Column(String(30), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    updated_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
