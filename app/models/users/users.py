import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from ...db.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    first_name = Column(String(75), nullable=False)
    last_name = Column(String(75), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(30), default="user", nullable=False, index=True)
    registration_type = Column(String(30), default="email", nullable=False)
    profile_photo_url = Column(String(1000), nullable=True)
    banner_photo_url = Column(String(1000), nullable=True)
    university = Column(String(255), nullable=True, index=True)
    major = Column(String(150), nullable=True, index=True)
    minor = Column(String(150), nullable=True, index=True)
    education_level = Column(String(50), nullable=True, index=True)
    bio = Column(String(500), nullable=True)

    graduation_date = Column(String(7), nullable=True)
    location = Column(String(255), nullable=True)
    country = Column(String(120), nullable=True, index=True)
    profile_visibility = Column(String(30), default="private", nullable=False)
    completeness_score = Column(Integer, default=0, nullable=False)
    notification_preferences = Column(
        JSON,
        default=lambda: {"email": True, "push": True, "inApp": True},
        nullable=False,
    )
    is_email_verified = Column(Boolean, default=False, nullable=False)
    email_verified_at = Column(DateTime(timezone=True), nullable=True)
    is_delete = Column(Boolean, default=False, nullable=False)
    consent_given = Column(Boolean, default=False, nullable=False)
    reference_code = Column(String(32), nullable=True, index=True)
    invitation_code = Column(String(32), nullable=True, index=True)
    online_presence = Column(Boolean, default=False, nullable=False)
    welcome_message = Column(String(255), nullable=True)
    is_onboarding = Column(Boolean, default=True, nullable=False)
    connections_count = Column(Integer, default=0, nullable=False)
    posts_count = Column(Integer, default=0, nullable=False)
    blocked_user_ids = Column(JSON, default=list, nullable=False)
    reported_user_ids = Column(JSON, default=list, nullable=False)
    following_user_ids = Column(JSON, default=list, nullable=False)
    connection_request_user_ids = Column(JSON, default=list, nullable=False)
    connected_user_ids = Column(JSON, default=list, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    sessions = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    otps = relationship("EmailOTP", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("UserNotification", back_populates="user", cascade="all, delete-orphan")
    devices = relationship("UserDevice", back_populates="user", cascade="all, delete-orphan")
    academic_interests = Column(JSON, default=list, nullable=False)
    invitation_codes = relationship(
        "InvitationCode",
        back_populates="originator",
        foreign_keys="InvitationCode.originator_user_id",
        cascade="all, delete-orphan",
    )
    sent_invitations = relationship(
        "Invitation",
        back_populates="originator",
        foreign_keys="Invitation.originator_user_id",
        cascade="all, delete-orphan",
    )
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan", foreign_keys="Post.author_id")



