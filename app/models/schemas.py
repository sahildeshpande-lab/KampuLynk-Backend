from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["user", "admin"]
LoginType = Literal["email", "google", "apple"]
EducationLevel = Literal["bachelors", "masters", "phd", "postdoctoral", "professional"]
ProfileVisibility = Literal["public", "connections_only", "private"]
EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
EMAIL_EXAMPLE = "john@university.edu"


def email_field():
    return Field(pattern=EMAIL_PATTERN, examples=[EMAIL_EXAMPLE])


class CamelModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True, alias_generator=None)


class NotificationPreferences(CamelModel):
    email: bool = True
    push: bool = True
    inApp: bool = True


class UserBase(CamelModel):
    fullName: str = Field(min_length=1, max_length=150)
    email: str = email_field()
    role: Role = "user"
    loginType: LoginType = "email"
    profilePhotoUrl: str | None = None
    bannerPhotoUrl: str | None = None
    university: str | None = None
    major: str | None = None
    minor: str | None = None
    educationLevel: EducationLevel | None = None
    bio: str | None = Field(default=None, max_length=500)
    academicInterests: list[str] = Field(default_factory=list)
    graduationDate: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    location: str | None = None
    profileVisibility: ProfileVisibility = "public"
    completenessScore: int = Field(default=0, ge=0, le=100)
    notificationPreferences: NotificationPreferences = Field(default_factory=NotificationPreferences)
    isEmailVerified: bool = False
    isActive: bool = True
    consentGiven: bool = False
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
    idToken: str = Field(min_length=1)
    email: str = email_field()
    fullName: str | None = None
    profilePhotoUrl: str | None = None

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


class ChangePasswordRequest(CamelModel):
    currentPassword: str = Field(min_length=8)
    newPassword: str = Field(min_length=8)


class UserUpdate(CamelModel):
    fullName: str | None = Field(default=None, min_length=1, max_length=150)
    profilePhotoUrl: str | None = None
    bannerPhotoUrl: str | None = None
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
    invitationCode: str | None = None
    onlinePresence: bool | None = None
    welcomeMessage: str | None = None


class User(CamelModel):
    id: str
    fullName: str
    email: str = Field(examples=[EMAIL_EXAMPLE])
    role: Role
    loginType: LoginType
    profilePhotoUrl: str | None
    bannerPhotoUrl: str | None
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
    invitationCode: str | None
    onlinePresence: bool
    welcomeMessage: str | None
    postsCount: int
    connectionsCount: int
    createdAt: datetime
    updatedAt: datetime


class PublicUser(CamelModel):
    id: str
    fullName: str
    profilePhotoUrl: str | None
    university: str | None
    major: str | None
    educationLevel: EducationLevel | None
    bio: str | None
    postsCount: int
    connectionsCount: int
    completenessScore: int
    profileVisibility: ProfileVisibility


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
