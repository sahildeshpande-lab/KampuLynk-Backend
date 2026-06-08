import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship

from ...db.db import Base


class DailyAnalytics(Base):
    __tablename__ = "daily_analytics"
    __table_args__ = (
        UniqueConstraint("date", name="uq_daily_analytics_date"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    date = Column(Date, nullable=False, index=True)
    dau = Column(Integer, default=0, nullable=False)
    new_users = Column(Integer, default=0, nullable=False)
    total_users = Column(Integer, default=0, nullable=False)
    total_posts = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
