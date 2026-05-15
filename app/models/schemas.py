from datetime import datetime
from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["user", "superadmin", "moderator", "viewer"]
LoginType = Literal["email", "google", "apple"]
SocialProvider = Literal["google", "apple"]
EducationLevel = Literal["bachelors", "masters", "phd", "postdoctoral", "professional"]
ProfileVisibility = Literal["public", "connections_only", "private"]
NotificationTargetType = Literal["direct", "topic", "broadcast"]
PostContentFormat = Literal["plain_text", "rich_text"]
PostVisibility = Literal["public", "connections_only", "private"]
AttachmentType = Literal["image", "pdf", "word", "ppt", "audio"]
EngagementReaction = Literal["like", "love", "celebrate", "insightful", "curious", "support"]
ReactionType = Literal["like", "love", "celebrate", "insightful", "curious", "support"]
ModerationAction = Literal["reinstate", "delete", "escalate"]
PostStatus = Literal["draft", "published"]
EngagementAction = Literal["like", "comment", "repost"]
ReportReason = Literal[
    "spam", "harassment", "hate_speech", "misinformation",
    "violence", "nudity", "copyright", "other"
]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
EMAIL_EXAMPLE = "john@university.edu"
PROFILE_PHOTO_EXAMPLE = "https://kampulynk-user-media.s3.amazonaws.com/users/sample/profile.png"
BANNER_PHOTO_EXAMPLE = "https://kampulynk-user-media.s3.amazonaws.com/users/sample/banner.png"


def email_field():
    return Field(pattern=EMAIL_PATTERN, examples=[EMAIL_EXAMPLE])


class CamelModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=None)


class NotificationPreferences(CamelModel):
    email: bool = True
    push: bool = True
    inApp: bool = True


class NotificationChannels(CamelModel):
    email: bool = True
    inApp: bool = True
    push: bool = False


class NotificationTemplate(CamelModel):
    id: str | None = Field(
        default=None,
        max_length=80,
        validation_alias=AliasChoices("id", "key"),
        serialization_alias="id",
    )
    subject: str = Field(min_length=1, max_length=150)
    title: str = Field(min_length=1, max_length=150)
    body: str = Field(min_length=1, max_length=1000)
    htmlBody: str | None = None


class NotificationTypeCreate(CamelModel):
    type: str = Field(min_length=1, max_length=80, examples=["send"])
    name: str = Field(min_length=1, max_length=150, examples=["Send Notification"])
    description: str | None = Field(default=None, max_length=500)
    isActive: bool = True


class SendNotificationRequest(CamelModel):
    type: str = Field(default="send", min_length=1, max_length=80, examples=["send"])
    targetType: NotificationTargetType = "direct"
    topic: str | None = Field(default=None, max_length=150, examples=["computer-science"])
    userIds: list[str] = Field(default_factory=list)
    template: NotificationTemplate
    channels: NotificationChannels = Field(default_factory=NotificationChannels)

    @model_validator(mode="after")
    def validate_target(self) -> "SendNotificationRequest":
        if self.targetType == "direct" and not self.userIds:
            raise ValueError("userIds are required for direct notifications")
        if self.targetType == "topic" and not self.topic:
            raise ValueError("topic is required for topic notifications")
        return self


class UserBase(CamelModel):
    fullName: str = Field(min_length=1, max_length=150)
    email: str = email_field()
    role: Role = "user"
    loginType: LoginType = "email"
    profilePhotoUrl: str | None = Field(default=None, examples=[PROFILE_PHOTO_EXAMPLE])
    bannerPhotoUrl: str | None = Field(default=None, examples=[BANNER_PHOTO_EXAMPLE])
    university: str | None = None
    major: str | None = None
    minor: str | None = None
    educationLevel: EducationLevel | None = None
    bio: str | None = Field(default=None, max_length=500)
    academicInterests: list[str] = Field(default_factory=list)
    graduationDate: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    location: str | None = None
    profileVisibility: ProfileVisibility = "private"
    completenessScore: int = Field(default=0, ge=0, le=100)
    notificationPreferences: NotificationPreferences = Field(default_factory=NotificationPreferences)
    isEmailVerified: bool = False
    isActive: bool = True
    consentGiven: bool = False
    referenceCode: str | None = None
    invitationCode: str | None = None
    onlinePresence: bool = False
    welcomeMessage: str | None = None

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

class UserCreate(UserBase):
    password: str = Field(min_length=8)


class AdminUserCreate(UserCreate):
    isEmailVerified: bool = True
    isActive: bool = True


class SignupRequest(CamelModel):
    fullName: str = Field(min_length=1, max_length=150)
    email: str = email_field()
    password: str = Field(min_length=8)
    university: str | None = None
    major: str | None = None
    minor: str | None = None
    educationLevel: EducationLevel | None = None
    invitationCode: str | None = None
    consentGiven: bool = True

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

class OAuthRequest(CamelModel):
    provider: SocialProvider = Field(examples=["google"])
    idToken: str = Field(min_length=1)
    email: str = email_field()
    fullName: str | None = None
    profilePhotoUrl: str | None = Field(default=None, examples=[PROFILE_PHOTO_EXAMPLE])

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class LoginRequest(CamelModel):
    email: str = email_field()
    password: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class VerifyOTPRequest(CamelModel):
    email: str = email_field()
    otp: str = Field(min_length=4, max_length=12)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class ResendOTPRequest(CamelModel):
    email: str = email_field()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class RefreshRequest(CamelModel):
    refreshToken: str


class ForgotPasswordRequest(CamelModel):
    email: str = email_field()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class ResetPasswordRequest(CamelModel):
    email: str = email_field()
    otp: str = Field(min_length=4, max_length=12)
    newPassword: str = Field(min_length=8)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class ChangePasswordRequest(CamelModel):
    currentPassword: str = Field(min_length=8)
    newPassword: str = Field(min_length=8)

    @model_validator(mode="after")
    def passwords_must_differ(self) -> "ChangePasswordRequest":
        if self.currentPassword == self.newPassword:
            raise ValueError("New password must be different from current password")
        return self


class UserUpdate(CamelModel):
    fullName: str | None = Field(default=None, min_length=1, max_length=150)
    profilePhotoUrl: str | None = Field(default=None, examples=[PROFILE_PHOTO_EXAMPLE])
    bannerPhotoUrl: str | None = Field(default=None, examples=[BANNER_PHOTO_EXAMPLE])
    university: str | None = None
    major: str | None = None
    minor: str | None = None
    educationLevel: EducationLevel | None = None
    bio: str | None = Field(default=None, max_length=500)
    academicInterests: list[str] | None = None
    graduationDate: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    location: str | None = None
    profileVisibility: ProfileVisibility | None = None
    notificationPreferences: NotificationPreferences | None = None
    consentGiven: bool | None = None
    referenceCode: str | None = None
    onlinePresence: bool | None = None
    welcomeMessage: str | None = None


class ProfileVisibilityUpdate(CamelModel):
    profileVisibility: ProfileVisibility


class User(CamelModel):
    id: str
    fullName: str
    email: str = Field(examples=[EMAIL_EXAMPLE])
    role: Role
    loginType: LoginType
    profilePhotoUrl: str | None = Field(examples=[PROFILE_PHOTO_EXAMPLE])
    bannerPhotoUrl: str | None = Field(examples=[BANNER_PHOTO_EXAMPLE])
    university: str | None
    major: str | None
    minor: str | None
    educationLevel: EducationLevel | None
    bio: str | None
    academicInterests: list[str]
    graduationDate: str | None
    location: str | None
    profileVisibility: ProfileVisibility
    completenessScore: int
    notificationPreferences: dict[str, bool]
    isEmailVerified: bool
    isActive: bool
    consentGiven: bool
    referenceCode: str | None
    invitationCode: str | None
    invitationDeepLinkUrl: str | None = None
    invitationWebUrl: str | None = None
    onlinePresence: bool
    welcomeMessage: str | None
    postsCount: int
    connectionsCount: int
    createdAt: datetime
    updatedAt: datetime
    isOnboarding: int = 1


class PublicUser(CamelModel):
    id: str
    fullName: str
    profilePhotoUrl: str | None = Field(examples=[PROFILE_PHOTO_EXAMPLE])
    university: str | None
    major: str | None
    educationLevel: EducationLevel | None
    bio: str | None
    postsCount: int
    connectionsCount: int
    completenessScore: int
    profileVisibility: ProfileVisibility


class Notification(CamelModel):
    id: str
    userId: str
    type: str
    targetType: str
    topic: str | None
    templateKey: str | None
    title: str
    body: str
    channels: dict[str, bool]
    deliveryStatus: dict[str, Any]
    isRead: bool
    createdAt: datetime
    readAt: datetime | None


class AuthResponse(CamelModel):
    accessToken: str
    refreshToken: str
    user: User


class MessageResponse(CamelModel):
    status: bool
    message: str
    data: dict[str, Any] | None = None


class ApiResponse(CamelModel):
    status: bool
    message: str
    data: Any | None = None


class InvitationSendRequest(CamelModel):
    email: str = email_field()

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class InvitationSendResult(CamelModel):
    code: str
    deepLinkUrl: str | None = None
    webUrl: str | None = None
    remainingToday: int
    limitPerDay: int = 50


class InvitationValidateResult(CamelModel):
    isValid: bool
    code: str
    originatorUserId: str | None = None
    originatorName: str | None = None


class InvitationCodeAdminItem(CamelModel):
    id: str
    code: str
    originatorUserId: str
    originatorEmail: str | None = None
    isActive: bool
    createdAt: datetime
    deactivatedAt: datetime | None = None
    deactivatedByUserId: str | None = None
    deactivationReason: str | None = None


class InvitationCodeDeactivateRequest(CamelModel):
    reason: str | None = Field(default=None, max_length=255)


class AdminInvitationCodeCreateRequest(CamelModel):
    originatorUserId: str = Field(min_length=1)


class PostAttachment(CamelModel):
    type: AttachmentType
    url: str = Field(min_length=1, max_length=1000)
    name: str | None = Field(default=None, max_length=255)
    contentType: str | None = Field(default=None, max_length=150)
    sizeBytes: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LinkPreview(CamelModel):
    url: str = Field(min_length=1, max_length=1000)
    title: str | None = Field(default=None, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    imageUrl: str | None = Field(default=None, max_length=1000)


class PostCreateRequest(CamelModel):
    content: str = Field(default="", max_length=5000)
    status: PostStatus = "published"
    visibility: PostVisibility = "public"
    engagementEnabled: bool = True
    contentFormat: PostContentFormat = "plain_text"
    richTextJson: dict[str, Any] | None = None
    richTextHtml: str | None = Field(default=None, max_length=20000)
    attachments: list[PostAttachment] = Field(
        default_factory=list,
        max_length=15,
        description="Legacy alias for media. Prefer media.",
    )
    media: list[PostAttachment] = Field(
        default_factory=list,
        max_length=15,
        description="Canonical post media field.",
    )
    hashtags: list[str] = Field(default_factory=list, max_length=20)
    mentions: list[str] = Field(default_factory=list, max_length=20)
    topicTags: list[str] = Field(default_factory=list, max_length=10)
    linkPreview: LinkPreview | None = None


class PostUpdateRequest(CamelModel):
    content: str | None = Field(default=None, max_length=5000)
    status: PostStatus | None = None
    visibility: PostVisibility | None = None
    engagementEnabled: bool | None = None
    contentFormat: PostContentFormat | None = None
    richTextJson: dict[str, Any] | None = None
    richTextHtml: str | None = Field(default=None, max_length=20000)
    attachments: list[PostAttachment] | None = Field(
        default=None,
        max_length=15,
        description="Legacy alias for media. Prefer media.",
    )
    media: list[PostAttachment] | None = Field(
        default=None,
        max_length=15,
        description="Canonical post media field.",
    )
    hashtags: list[str] | None = Field(default=None, max_length=20)
    mentions: list[str] | None = Field(default=None, max_length=20)
    topicTags: list[str] | None = Field(default=None, max_length=10)
    linkPreview: LinkPreview | None = None


class PostReactionRequest(CamelModel):
    reactionType: ReactionType = "like"


class CommentReactionRequest(CamelModel):
    reactionType: ReactionType = "like"


class EngagementRequest(CamelModel):
    action: EngagementAction
    reaction: EngagementReaction | None = "like"
    isLiked: bool = True
    comment: str | None = Field(default=None, max_length=2000)
    parentCommentId: str | None = None
    attachments: list[PostAttachment] = Field(default_factory=list, max_length=5)
    quote: str | None = Field(default=None, max_length=1000)


class ReportPostRequest(CamelModel):
    reason: ReportReason
    description: str | None = Field(default=None, max_length=1000)


class CommentCreateRequest(CamelModel):
    content: str = Field(min_length=1, max_length=2000)
    parentCommentId: str | None = None
    attachments: list[PostAttachment] = Field(default_factory=list, max_length=5)


class ReplyCreateRequest(CamelModel):
    content: str = Field(min_length=1, max_length=2000)
    attachments: list[PostAttachment] = Field(default_factory=list, max_length=5)


class CommentUpdateRequest(CamelModel):
    content: str = Field(min_length=1, max_length=2000)


class RepostCreateRequest(CamelModel):
    quote: str | None = Field(default=None, max_length=1000)


class ReportContentRequest(CamelModel):
    reasons: list[str] = Field(default_factory=list, max_length=10)


class ModerationActionRequest(CamelModel):
    action: ModerationAction
    note: str | None = Field(default=None, max_length=500)
