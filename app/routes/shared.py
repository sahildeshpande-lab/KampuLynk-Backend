import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import (
    EmailOTP,
    User,
    UserAcademicInterest,
    UserNotificationPreference,
    UserSession,
)
from ..models.schemas import AdminUserCreate, SignupRequest, UserUpdate


def api_response(message: str, data=None, ok: bool = True) -> dict:
    return {"status": ok, "message": message, "data": data}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _token() -> str:
    return secrets.token_urlsafe(32)


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _payload_dict(value):
    return value.model_dump() if hasattr(value, "model_dump") else value


def _create_otp(db: Session, user: User) -> EmailOTP:
    otp = EmailOTP(user_id=user.id, code=_generate_otp_code())
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def _create_session(db: Session, user: User) -> UserSession:
    session = UserSession(user_id=user.id, access_token=_token(), refresh_token=_token())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _create_user_from_payload(payload: SignupRequest | AdminUserCreate, role: str = "user") -> User:
    user = User(
        full_name=payload.fullName,
        email=payload.email,
        password_hash=_hash_password(payload.password),
        role=role,
        login_type=getattr(payload, "loginType", "email"),
        profile_photo_url=getattr(payload, "profilePhotoUrl", None),
        banner_photo_url=getattr(payload, "bannerPhotoUrl", None),
        university=payload.university,
        major=payload.major,
        minor=payload.minor,
        education_level=payload.educationLevel,
        bio=getattr(payload, "bio", None),
        graduation_date=getattr(payload, "graduationDate", None),
        location=getattr(payload, "location", None),
        profile_visibility=getattr(payload, "profileVisibility", "public"),
        consent_given=payload.consentGiven,
        invitation_code=payload.invitationCode,
        online_presence=getattr(payload, "onlinePresence", False),
        welcome_message=getattr(payload, "welcomeMessage", None),
        is_email_verified=getattr(payload, "isEmailVerified", False),
        is_active=getattr(payload, "isActive", True),
    )
    user.academic_interests = [
        UserAcademicInterest(interest=interest) for interest in getattr(payload, "academicInterests", [])
    ]
    preferences = _payload_dict(getattr(payload, "notificationPreferences", None)) or {
        "email": True,
        "push": True,
        "inApp": True,
    }
    user.notification_preferences = UserNotificationPreference(
        email=preferences["email"],
        push=preferences["push"],
        in_app=preferences["inApp"],
    )
    user.completeness_score = _calculate_completeness(user)
    return user


def _calculate_completeness(user: User) -> int:
    interests = [item.interest for item in user.academic_interests]
    profile_fields: Iterable[object] = (
        user.full_name,
        user.email,
        user.profile_photo_url,
        user.university,
        user.major,
        user.education_level,
        user.bio,
        interests,
        user.graduation_date,
        user.location,
        user.consent_given,
    )
    completed = sum(1 for value in profile_fields if bool(value))
    return round((completed / 11) * 100)


def _academic_interests(user: User) -> list[str]:
    return [item.interest for item in user.academic_interests]


def _notification_preferences(user: User) -> dict[str, bool]:
    preferences = user.notification_preferences
    if not preferences:
        return {"email": True, "push": True, "inApp": True}
    return {"email": preferences.email, "push": preferences.push, "inApp": preferences.in_app}


def _user_to_schema(user: User) -> dict:
    return {
        "id": user.id,
        "fullName": user.full_name,
        "email": user.email,
        "role": user.role,
        "loginType": user.login_type,
        "profilePhotoUrl": user.profile_photo_url,
        "bannerPhotoUrl": user.banner_photo_url,
        "university": user.university,
        "major": user.major,
        "minor": user.minor,
        "educationLevel": user.education_level,
        "bio": user.bio,
        "academicInterests": _academic_interests(user),
        "graduationDate": user.graduation_date,
        "location": user.location,
        "profileVisibility": user.profile_visibility,
        "completenessScore": user.completeness_score,
        "notificationPreferences": _notification_preferences(user),
        "isEmailVerified": user.is_email_verified,
        "isActive": user.is_active,
        "consentGiven": user.consent_given,
        "invitationCode": user.invitation_code,
        "onlinePresence": user.online_presence,
        "welcomeMessage": user.welcome_message,
        "postsCount": user.posts_count,
        "connectionsCount": user.connections_count,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
    }


def _public_user(user: User) -> dict:
    if user.profile_visibility == "private":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Profile is private")
    return {
        "id": user.id,
        "fullName": user.full_name,
        "profilePhotoUrl": user.profile_photo_url,
        "university": user.university,
        "major": user.major,
        "educationLevel": user.education_level,
        "bio": user.bio if user.profile_visibility == "public" else None,
        "postsCount": user.posts_count,
        "connectionsCount": user.connections_count,
        "completenessScore": user.completeness_score,
        "profileVisibility": user.profile_visibility,
    }


def _get_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = email.strip().lower()
    return db.query(User).filter(func.lower(func.trim(User.email)) == normalized_email).first()


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _current_session(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> UserSession:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    session = db.query(UserSession).filter(
        UserSession.access_token == token,
        UserSession.is_active.is_(True),
    ).first()
    if not session or not session.user or not session.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return session


def get_current_user(session: UserSession = Depends(_current_session)) -> User:
    return session.user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def _apply_user_update(user: User, payload: UserUpdate) -> User:
    field_map = {
        "fullName": "full_name",
        "profilePhotoUrl": "profile_photo_url",
        "bannerPhotoUrl": "banner_photo_url",
        "university": "university",
        "major": "major",
        "minor": "minor",
        "educationLevel": "education_level",
        "bio": "bio",
        "graduationDate": "graduation_date",
        "location": "location",
        "profileVisibility": "profile_visibility",
        "consentGiven": "consent_given",
        "invitationCode": "invitation_code",
        "onlinePresence": "online_presence",
        "welcomeMessage": "welcome_message",
    }
    changes = payload.model_dump(exclude_unset=True)
    for public_name, value in changes.items():
        if public_name == "academicInterests":
            user.academic_interests = [UserAcademicInterest(interest=interest) for interest in value]
            continue
        if public_name == "notificationPreferences":
            preferences = _payload_dict(value)
            if not user.notification_preferences:
                user.notification_preferences = UserNotificationPreference()
            user.notification_preferences.email = preferences["email"]
            user.notification_preferences.push = preferences["push"]
            user.notification_preferences.in_app = preferences["inApp"]
            continue
        setattr(user, field_map[public_name], _payload_dict(value))
    user.completeness_score = _calculate_completeness(user)
    return user


def _auth_payload(session: UserSession, user: User) -> dict:
    return {"accessToken": session.access_token, "refreshToken": session.refresh_token, "user": _user_to_schema(user)}


def _otp_not_expired(otp: EmailOTP) -> bool:
    created_at = otp.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) <= created_at + timedelta(minutes=10)
