import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, func
from sqlalchemy.orm import relationship

from ..db.db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=True)
    role = Column(String(30), default="user", nullable=False, index=True)
    login_type = Column(String(30), default="email", nullable=False)
    profile_photo_url = Column(String(1000), nullable=True)
    banner_photo_url = Column(String(1000), nullable=True)
    university = Column(String(255), nullable=True, index=True)
    major = Column(String(150), nullable=True, index=True)
    minor = Column(String(150), nullable=True, index=True)
    education_level = Column(String(50), nullable=True, index=True)
    bio = Column(String(500), nullable=True)
    legacy_academic_interests = Column("academic_interests", JSON, default=list, nullable=False)
    graduation_date = Column(String(7), nullable=True)
    location = Column(String(255), nullable=True)
    profile_visibility = Column(String(30), default="private", nullable=False)
    completeness_score = Column(Integer, default=0, nullable=False)
    legacy_notification_preferences = Column(
        "notification_preferences",
        JSON,
        default=lambda: {"email": True, "push": True, "inApp": True},
        nullable=False,
    )
    is_email_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    consent_given = Column(Boolean, default=False, nullable=False)
    reference_code = Column(String(32), nullable=True, index=True)
    invitation_code = Column(String(32), nullable=True, index=True)
    online_presence = Column(Boolean, default=False, nullable=False)
    welcome_message = Column(String(255), nullable=True)
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
    academic_interests = relationship(
        "UserAcademicInterest",
        back_populates="user",
        cascade="all, delete-orphan",
        order_by="UserAcademicInterest.created_at",
    )
    notification_preferences = relationship(
        "UserNotificationPreference",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
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


class UserAcademicInterest(Base):
    __tablename__ = "user_academic_interests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    interest = Column(String(150), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="academic_interests")


class UserNotificationPreference(Base):
    __tablename__ = "user_notification_preferences"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    email = Column(Boolean, default=True, nullable=False)
    push = Column(Boolean, default=True, nullable=False)
    in_app = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="notification_preferences")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    access_token = Column(String(255), unique=True, nullable=False, index=True)
    refresh_token = Column(String(255), unique=True, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user = relationship("User", back_populates="sessions")


class LoginRateLimit(Base):
    __tablename__ = "login_rate_limits"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), nullable=False, index=True)
    ip = Column(String(64), nullable=True, index=True)
    failed_count = Column(Integer, default=0, nullable=False)
    first_failed_at = Column(DateTime(timezone=True), nullable=True)
    blocked_until = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

class EmailOTP(Base):
    __tablename__ = "email_otps"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(12), nullable=False)
    purpose = Column(String(30), default="email_verification", nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="otps")


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


class NotificationType(Base):
    __tablename__ = "notification_types"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key = Column(String(80), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    template_name = Column(String(120), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class InvitationCode(Base):
    __tablename__ = "invitation_codes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    code = Column(String(32), unique=True, nullable=False, index=True)
    originator_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    deactivated_at = Column(DateTime(timezone=True), nullable=True)
    deactivated_by_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    deactivation_reason = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    originator = relationship("User", back_populates="invitation_codes", foreign_keys=[originator_user_id])
    deactivated_by = relationship("User", foreign_keys=[deactivated_by_user_id])
    invitations = relationship("Invitation", back_populates="invitation_code", cascade="all, delete-orphan")


class Invitation(Base):
    __tablename__ = "invitations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    invitation_code_id = Column(
        String(36),
        ForeignKey("invitation_codes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    originator_user_id = Column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    invited_email = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    invitation_code = relationship("InvitationCode", back_populates="invitations")
    originator = relationship("User", back_populates="sent_invitations", foreign_keys=[originator_user_id])
