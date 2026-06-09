import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable

import jwt
from fastapi import HTTPException, Request, status
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from pwdlib import PasswordHash
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..models.model import EmailOTP, LoginRateLimit, User, UserAcademicInterest, UserSession
from ..models.schemas import AdminUserCreate, SignupRequest, UserUpdate
from . import invitation_service

password_hash = PasswordHash.recommended()

LOGIN_MAX_ATTEMPTS = 5
LOGIN_BLOCK_MINUTES = 15

def hash_password(password: str) -> str: return password_hash.hash(password)

def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        return password_hash.verify(password, stored_hash)
    except Exception:
        return False


def password_needs_rehash(stored_hash: str | None) -> bool:
    if not stored_hash:
        return True
    if not hasattr(password_hash, "check_needs_rehash"):
        return False
    try:
        return password_hash.check_needs_rehash(stored_hash)
    except Exception:
        return True


def token() -> str: return secrets.token_urlsafe(32)

def jwt_secret() -> str: return os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY") or "dev-secret-change-me-32-bytes-minimum"


def jwt_algorithm() -> str:
    algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip().upper()
    supported = {"HS256", "HS384", "HS512"}
    if algorithm not in supported:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unsupported JWT_ALGORITHM '{algorithm}'. Supported values: {', '.join(sorted(supported))}",
        )
    return algorithm


def jwt_expire_minutes() -> int:
    try:
        return int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    except ValueError:
        return 60


def jwt_encode(payload: dict) -> str: return jwt.encode(payload, jwt_secret(), algorithm=jwt_algorithm())

def jwt_decode(token_value: str) -> dict:
    try:
        return jwt.decode(token_value, jwt_secret(), algorithms=[jwt_algorithm()])
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token has expired. Please refresh your token")
    except InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def generate_otp_code() -> str: return f"{secrets.randbelow(1_000_000):06d}"

def otp_not_expired(otp: EmailOTP) -> bool:
    if otp.is_expire:
        return False
    created_at = otp.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > created_at + timedelta(minutes=10):
        otp.is_expire = True
        return False
    return True


def credentials_exception(detail: str = "Could not validate credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def current_user_from_token(db: Session, access_token: str | None) -> User | None:
    if not access_token:
        return None
    payload = jwt_decode(access_token)
    session_id = payload.get("sid")
    if not session_id:
        return None
    session = db.query(UserSession).filter(UserSession.id == session_id, UserSession.is_active.is_(True)).first()
    if not session or not session.user or session.user.is_delete:
        return None
    return session.user


def current_session_from_token(db: Session, access_token: str | None) -> UserSession:
    if not access_token:
        raise credentials_exception("Missing bearer token")
    payload = jwt_decode(access_token)
    session_id = payload.get("sid")
    if not session_id:
        raise credentials_exception("Invalid session")
    session = db.query(UserSession).filter(UserSession.id == session_id, UserSession.is_active.is_(True)).first()
    if not session or not session.user or session.user.is_delete:
        raise credentials_exception("Invalid session")
    return session


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def enforce_login_rate_limit(db: Session, email: str, ip: str | None) -> LoginRateLimit | None:
    now = datetime.now(timezone.utc)
    key = email.strip().lower()
    record = db.query(LoginRateLimit).filter(LoginRateLimit.email == key, LoginRateLimit.ip == ip).first()
    if record and record.blocked_until and record.blocked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again after {record.blocked_until.isoformat()}",
        )
    return record


def register_login_failure(db: Session, email: str, ip: str | None) -> None:
    now = datetime.now(timezone.utc)
    key = email.strip().lower()
    record = db.query(LoginRateLimit).filter(LoginRateLimit.email == key, LoginRateLimit.ip == ip).first()
    if not record:
        record = LoginRateLimit(email=key, ip=ip, failed_count=0, first_failed_at=now)
        db.add(record)
        db.flush()

    if not record.first_failed_at:
        record.first_failed_at = now
        record.failed_count = 0

    record.failed_count = int(record.failed_count or 0) + 1
    if record.failed_count >= LOGIN_MAX_ATTEMPTS:
        record.blocked_until = now + timedelta(minutes=LOGIN_BLOCK_MINUTES)
        record.failed_count = 0
        record.first_failed_at = None
    db.commit()


def clear_login_rate_limit(db: Session, email: str, ip: str | None) -> None:
    key = email.strip().lower()
    db.query(LoginRateLimit).filter(LoginRateLimit.email == key, LoginRateLimit.ip == ip).delete()
    db.commit()


def payload_dict(value): return value.model_dump() if hasattr(value, "model_dump") else value


def create_user_from_payload(payload: SignupRequest | AdminUserCreate, role: str = "user") -> User:
    user = User(
        first_name=payload.firstName,
        last_name=payload.lastName,
        email=payload.email,
        password_hash=hash_password(payload.password),
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
        is_delete=getattr(payload, "isDelete", False),
    )
    user.academic_interests = [
        UserAcademicInterest(interest=interest) for interest in getattr(payload, "academicInterests", [])
    ]
    preferences = payload_dict(getattr(payload, "notificationPreferences", None)) or {
        "email": True,
        "push": True,
        "inApp": True,
    }
    user.notification_preferences = preferences
    user.completeness_score = calculate_completeness(user)
    return user


def calculate_completeness(user: User) -> int:
    interests = [item.interest for item in user.academic_interests]
    profile_fields: Iterable[object] = (
        user.first_name,
        user.last_name,
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
    return round((completed / 12) * 100)


def academic_interests(user: User) -> list[str]: return [item.interest for item in user.academic_interests]


def notification_preferences(user: User) -> dict[str, bool]:
    preferences = user.notification_preferences
    return {"email": True, "push": True, "inApp": True} if not preferences else preferences


def user_to_schema(user: User) -> dict:
    invite_code = (user.invitation_code or "").strip().upper() or None
    return {
        "id": user.id,
        "firstName": user.first_name,
        "lastName": user.last_name,
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
        "academicInterests": academic_interests(user),
        "graduationDate": user.graduation_date,
        "location": user.location,
        "profileVisibility": user.profile_visibility,
        "completenessScore": user.completeness_score,
        "notificationPreferences": notification_preferences(user),
        "isEmailVerified": user.is_email_verified,
        "isDelete": user.is_delete,
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


def public_user(user: User) -> dict:
    if user.profile_visibility == "private": raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Profile is private")
    return {
        "id": user.id,
        "firstName": user.first_name,
        "lastName": user.last_name,
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


def is_connected(user: User, other_user_id: str) -> bool: return other_user_id in (user.connected_user_ids or [])


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(func.lower(func.trim(User.email)) == email.strip().lower()).first()


def get_user_or_404(db: Session, user_id: str) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def apply_user_update(user: User, payload: UserUpdate) -> User:
    field_map = {
        "firstName": "first_name",
        "lastName": "last_name",
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
            preferences = payload_dict(value)
            user.notification_preferences = preferences
            continue
        setattr(user, field_map[public_name], payload_dict(value))
    user.completeness_score = calculate_completeness(user)
    return user


def auth_payload(session: UserSession, user: User) -> dict:
    ttl_minutes = jwt_expire_minutes()
    now = datetime.now(timezone.utc)
    access_token = jwt_encode(
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
        "user": user_to_schema(user),
    }
