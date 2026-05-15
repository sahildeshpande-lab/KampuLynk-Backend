import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
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
    posts = relationship("Post", back_populates="author", cascade="all, delete-orphan", foreign_keys="Post.author_id")


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
    rich_text_json = Column(JSON, nullable=True)
    rich_text_html = Column(Text, nullable=True)
    attachments = Column(JSON, default=list, nullable=False)
    link_preview = Column(JSON, nullable=True)
    hashtags = Column(JSON, default=list, nullable=False)
    mentions = Column(JSON, default=list, nullable=False)
    topic_tags = Column(JSON, default=list, nullable=False)
    status = Column(String(30), default="published", nullable=False, index=True)
    moderation_status = Column(String(30), default="approved", nullable=False, index=True)
    moderation_reasons = Column(JSON, default=list, nullable=False)
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


class PostDraft(Base):
    __tablename__ = "post_drafts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    body = Column(String(5000), default="", nullable=False)
    content_format = Column(String(30), default="plain_text", nullable=False)
    rich_text_json = Column(JSON, nullable=True)
    rich_text_html = Column(Text, nullable=True)
    attachments = Column(JSON, default=list, nullable=False)
    link_preview = Column(JSON, nullable=True)
    hashtags = Column(JSON, default=list, nullable=False)
    topic_tags = Column(JSON, default=list, nullable=False)
    autosave_interval_seconds = Column(Integer, default=30, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    author = relationship("User")


class PostMedia(Base):
    __tablename__ = "post_media"
    __table_args__ = (Index("ix_post_media_post_position", "post_id", "position"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    media_type = Column(String(30), nullable=False, index=True)
    url = Column(String(1000), nullable=False)
    name = Column(String(255), nullable=True)
    content_type = Column(String(150), nullable=True)
    size_bytes = Column(Integer, nullable=True)
    media_metadata = Column(JSON, default=dict, nullable=False)
    position = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    post = relationship("Post", back_populates="media")


class PostReaction(Base):
    __tablename__ = "post_reactions"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_reaction_user"),
        Index("ix_post_reactions_post_type", "post_id", "reaction_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reaction_type = Column(String(40), default="like", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    post = relationship("Post", back_populates="reactions")
    user = relationship("User")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_post_created_at", "post_id", "created_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    author_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_comment_id = Column(String(36), ForeignKey("comments.id", ondelete="CASCADE"), nullable=True, index=True)
    body = Column(String(2000), nullable=False)
    depth = Column(Integer, default=1, nullable=False, index=True)
    attachments = Column(JSON, default=list, nullable=False)
    moderation_status = Column(String(30), default="approved", nullable=False, index=True)
    moderation_reasons = Column(JSON, default=list, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    reply_count = Column(Integer, default=0, nullable=False)
    like_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    post = relationship("Post", back_populates="comments")
    author = relationship("User")
    parent = relationship("Comment", remote_side=[id], back_populates="replies")
    replies = relationship("Comment", back_populates="parent", cascade="all, delete-orphan")
    reactions = relationship("CommentReaction", back_populates="comment", cascade="all, delete-orphan")


class CommentReaction(Base):
    __tablename__ = "comment_reactions"
    __table_args__ = (
        UniqueConstraint("comment_id", "user_id", name="uq_comment_reaction_user"),
        Index("ix_comment_reactions_comment_type", "comment_id", "reaction_type"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    comment_id = Column(String(36), ForeignKey("comments.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reaction_type = Column(String(40), default="like", nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    comment = relationship("Comment", back_populates="reactions")
    user = relationship("User")


class PostEditHistory(Base):
    __tablename__ = "post_edit_history"
    __table_args__ = (Index("ix_post_edit_history_post_created_at", "post_id", "created_at"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    editor_user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    snapshot = Column(JSON, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    post = relationship("Post", back_populates="edit_snapshots")
    editor = relationship("User")


class Repost(Base):
    __tablename__ = "reposts"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_repost_user_post"),
        Index("ix_reposts_user_created_at", "user_id", "created_at"),
    )

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    post_id = Column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quote = Column(String(1000), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    post = relationship("Post", back_populates="reposts")
    user = relationship("User")


class PlatformConfig(Base):
    __tablename__ = "platform_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    key = Column(String(150), unique=True, nullable=False, index=True)
    value = Column(JSON, default=dict, nullable=False)
    description = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


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


PostEngagement = PostReaction
PostComment = Comment
