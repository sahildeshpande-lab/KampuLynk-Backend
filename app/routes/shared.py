import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
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
from ..services import invitation_service

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
password_hash = PasswordHash.recommended()


def api_response(message: str, data=None, ok: bool = True) -> dict:
    return {"status": ok, "message": message, "data": data}


def _hash_password(password: str) -> str:
    return password_hash.hash(password)


def _verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        return password_hash.verify(password, stored_hash)
    except Exception:
        return False


def _password_needs_rehash(stored_hash: str | None) -> bool:
    if not stored_hash:
        return True
    if not hasattr(password_hash, "check_needs_rehash"):
        return False
    try:
        return password_hash.check_needs_rehash(stored_hash)
    except Exception:
        return True


def _token() -> str:
    return secrets.token_urlsafe(32)


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "dev-secret-change-me-32-bytes-minimum"


def _jwt_algorithm() -> str:
    algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip().upper()
    supported = {"HS256", "HS384", "HS512"}
    if algorithm not in supported:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unsupported JWT_ALGORITHM '{algorithm}'. Supported values: {', '.join(sorted(supported))}",
        )
    return algorithm


def _jwt_expire_minutes() -> int:
    try:
        return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    except ValueError:
        return 60


def _jwt_encode(payload: dict) -> str:
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def _jwt_decode(token: str) -> dict:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

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
        profile_visibility=getattr(payload, "profileVisibility", "private"),
        consent_given=payload.consentGiven,
        reference_code=payload.invitationCode,
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
    invite_code = (user.invitation_code or "").strip().upper() or None
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
        "referenceCode": user.reference_code,
        "invitationCode": invite_code,
        "invitationDeepLinkUrl": invitation_service.invitation_deep_link_url(invite_code) if invite_code else None,
        "invitationWebUrl": invitation_service.invitation_web_url(invite_code) if invite_code else None,
        "onlinePresence": user.online_presence,
        "welcomeMessage": user.welcome_message,
        "postsCount": user.posts_count,
        "connectionsCount": user.connections_count,
        "createdAt": user.created_at,
        "updatedAt": user.updated_at,
        "is_onboarding": not user.is_email_verified,
        "connectedUserIds": user.connected_user_ids or [],
        "followingUserIds": user.following_user_ids or [],
        "blockedUserIds": user.blocked_user_ids or [],
        "reportedUserIds": user.reported_user_ids or [],
        "lynkupRequestUserIds": user.connection_request_user_ids or [],
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


def _credentials_exception(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user_optional(
    access_token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    if not access_token:
        return None
    payload = _jwt_decode(access_token)
    session_id = payload.get("sid")
    if not session_id:
        return None
    session = db.query(UserSession).filter(UserSession.id == session_id, UserSession.is_active.is_(True)).first()
    if not session or not session.user or not session.user.is_active:
        return None
    return session.user


def _is_connected(user: User, other_user_id: str) -> bool:
    connected_ids = user.connected_user_ids or []
    return other_user_id in connected_ids


def _get_user_by_email(db: Session, email: str) -> User | None:
    normalized_email = email.strip().lower()
    return db.query(User).filter(func.lower(func.trim(User.email)) == normalized_email).first()


def _get_user_or_404(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def _current_session(
    access_token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserSession:
    if not access_token:
        raise _credentials_exception("Missing bearer token")
    payload = _jwt_decode(access_token)
    session_id = payload.get("sid")
    if not session_id:
        raise _credentials_exception("Invalid session")
    session = db.query(UserSession).filter(UserSession.id == session_id, UserSession.is_active.is_(True)).first()
    if not session or not session.user or not session.user.is_active:
        raise _credentials_exception("Invalid session")
    return session


def get_current_user(session: UserSession = Depends(_current_session)) -> User:
    return session.user


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role not in {"superadmin", "moderator", "viewer"}:
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
        "referenceCode": "reference_code",
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
    ttl_minutes = _jwt_expire_minutes()
    now = datetime.now(timezone.utc)
    access_token = _jwt_encode(
        {
            "sub": user.id,
            "sid": session.id,
            "role": user.role,
            "iat": now,
            "exp": now + timedelta(minutes=ttl_minutes),
        }
    )
    return {
        "accessToken": access_token,
        "refreshToken": session.refresh_token,
        "is_onboarding": not user.is_email_verified,
        "user": _user_to_schema(user),
    }


def _otp_not_expired(otp: EmailOTP) -> bool:
    created_at = otp.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) <= created_at + timedelta(minutes=10)
