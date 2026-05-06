import hashlib
import os
import secrets
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from starlette.staticfiles import StaticFiles

from .db.db import engine, get_db, migrate_legacy_users_table
from .models.model import (
    Base,
    EmailOTP,
    User,
    UserAcademicInterest,
    UserNotification,
    UserNotificationPreference,
    UserSession,
)
from .models.schemas import (
    AdminUserCreate,
    ApiResponse,
    ChangePasswordRequest,
    LoginRequest,
    OAuthRequest,
    RefreshRequest,
    ResendOTPRequest,
    SendNotificationRequest,
    SignupRequest,
    UserUpdate,
    VerifyOTPRequest,
)
from .services.email_service import (
    send_account_created_email,
    send_notification_email,
    send_otp_email,
    send_password_changed_email,
)

migrate_legacy_users_table()
Base.metadata.create_all(bind=engine)

AUTH_TAG = "1] Authentication"
USER_TAG = "2] User Management"
NOTIFICATION_TAG = "3] Notifications"
ADMIN_TAG = "4] Admin — User Management"

app = FastAPI(
    title="KampuLynk User Management API",
    version="1.0.0",
    openapi_tags=[
        {
            "name": AUTH_TAG,
            "description": "Signup, verification, social login, session refresh, and logout.",
        },
        {
            "name": USER_TAG,
            "description": "Authenticated user profile, password, export, delete, and public profile APIs.",
        },
        {
            "name": NOTIFICATION_TAG,
            "description": "Admin notification sending and authenticated user in-app notification APIs.",
        },
        {
            "name": ADMIN_TAG,
            "description": "Admin-only authentication and user management APIs.",
        },
    ],
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "templates" / "static"), name="static")


@app.exception_handler(HTTPException)
def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": False, "message": str(exc.detail), "data": None},
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"status": False, "message": "Validation error", "data": {"errors": exc.errors()}},
    )


def api_response(message: str, data=None, ok: bool = True) -> dict:
    return {"status": ok, "message": message, "data": data}


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _token() -> str:
    return secrets.token_urlsafe(32)


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


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


def _payload_dict(value):
    return value.model_dump() if hasattr(value, "model_dump") else value


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


def _notification_to_schema(notification: UserNotification) -> dict:
    return {
        "id": notification.id,
        "userId": notification.user_id,
        "templateKey": notification.template_key,
        "title": notification.title,
        "body": notification.body,
        "channels": notification.channels,
        "deliveryStatus": notification.delivery_status,
        "isRead": notification.is_read,
        "createdAt": notification.created_at,
        "readAt": notification.read_at,
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


def _send_user_notification(db: Session, user: User, payload: SendNotificationRequest) -> UserNotification:
    preferences = _notification_preferences(user)
    requested_channels = payload.channels.model_dump()
    effective_channels = {
        "email": requested_channels["email"] and preferences["email"],
        "inApp": requested_channels["inApp"] and preferences["inApp"],
        "push": requested_channels["push"] and preferences["push"],
    }
    delivery_status = {
        "email": "skipped",
        "inApp": "created" if effective_channels["inApp"] else "skipped",
        "push": "queued" if effective_channels["push"] else "skipped",
    }

    if effective_channels["email"]:
        sent = send_notification_email(
            user.email,
            payload.template.subject,
            payload.template.title,
            payload.template.body,
            payload.template.htmlBody,
        )
        delivery_status["email"] = "sent" if sent else "failed"

    notification = UserNotification(
        user_id=user.id,
        template_key=payload.template.key,
        title=payload.template.title,
        body=payload.template.body,
        html_body=payload.template.htmlBody,
        channels=effective_channels,
        delivery_status=delivery_status,
    )
    db.add(notification)
    return notification


@app.get("/", response_model=ApiResponse)
def read_root():
    return api_response("KampuLynk User Management API is running")


@app.post("/auth/signup", response_model=ApiResponse, status_code=status.HTTP_201_CREATED, tags=[AUTH_TAG])
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = _create_user_from_payload(payload)
    db.add(user)
    db.commit()
    db.refresh(user)
    otp = _create_otp(db, user)
    send_otp_email(user.email, otp.code)
    session = _create_session(db, user)
    return api_response("Signup successful", _auth_payload(session, user))


@app.post("/auth/verify-otp", response_model=ApiResponse, tags=[AUTH_TAG])
def verify_otp(payload: VerifyOTPRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = db.query(EmailOTP).filter(
        EmailOTP.user_id == user.id,
        EmailOTP.code == payload.otp,
        EmailOTP.is_used.is_(False),
    ).order_by(EmailOTP.created_at.desc()).first()
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    created_at = otp.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > created_at + timedelta(minutes=10):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    otp.is_used = True
    user.is_email_verified = True
    db.commit()
    send_account_created_email(user.email, user.full_name)
    return api_response("Email verified", {"email": user.email})


@app.post("/auth/resend-otp", response_model=ApiResponse, tags=[AUTH_TAG])
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = _create_otp(db, user)
    send_otp_email(user.email, otp.code)
    return api_response("OTP sent", {"email": user.email})


@app.post("/auth/login", response_model=ApiResponse, tags=[AUTH_TAG])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    session = _create_session(db, user)
    return api_response("Login successful", _auth_payload(session, user))


@app.post("/auth/social", response_model=ApiResponse, tags=[AUTH_TAG])
def social_login(payload: OAuthRequest, db: Session = Depends(get_db)):
    return _oauth_login(payload, payload.provider, db)


def _oauth_login(payload: OAuthRequest, provider: str, db: Session) -> dict:
    user = _get_user_by_email(db, payload.email)
    if not user:
        user = User(
            full_name=payload.fullName or payload.email.split("@")[0],
            email=payload.email,
            login_type=provider,
            profile_photo_url=payload.profilePhotoUrl,
            is_email_verified=True,
            consent_given=True,
        )
        user.notification_preferences = UserNotificationPreference(email=True, push=True, in_app=True)
        user.completeness_score = _calculate_completeness(user)
        db.add(user)
        db.commit()
        db.refresh(user)
    session = _create_session(db, user)
    return api_response(f"{provider.title()} login successful", _auth_payload(session, user))


@app.post("/auth/refresh", response_model=ApiResponse, tags=[AUTH_TAG])
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    session = db.query(UserSession).filter(
        UserSession.refresh_token == payload.refreshToken,
        UserSession.is_active.is_(True),
    ).first()
    if not session or not session.user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    session.access_token = _token()
    session.refresh_token = _token()
    db.commit()
    db.refresh(session)
    return api_response("Token refreshed", _auth_payload(session, session.user))


@app.post("/auth/logout", response_model=ApiResponse, tags=[AUTH_TAG])
def logout(session: UserSession = Depends(_current_session), db: Session = Depends(get_db)):
    session.is_active = False
    db.commit()
    return api_response("Logged out")


@app.get("/users/me", response_model=ApiResponse, tags=[USER_TAG])
def get_me(current_user: User = Depends(get_current_user)):
    return api_response("Current user fetched", _user_to_schema(current_user))


@app.patch("/users/me", response_model=ApiResponse, tags=[USER_TAG])
def update_me(payload: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _apply_user_update(current_user, payload)
    db.commit()
    db.refresh(current_user)
    return api_response("Current user updated", _user_to_schema(current_user))


@app.post("/users/me/change-password", response_model=ApiResponse, tags=[USER_TAG])
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.login_type != "email" or current_user.password_hash != _hash_password(payload.currentPassword):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")
    current_user.password_hash = _hash_password(payload.newPassword)
    db.commit()
    send_password_changed_email(current_user.email, current_user.full_name)
    return api_response("Password changed")


@app.delete("/users/me", response_model=ApiResponse, tags=[USER_TAG])
def delete_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.is_active = False
    db.query(UserSession).filter(UserSession.user_id == current_user.id).update({"is_active": False})
    db.commit()
    return api_response("Current user deleted")


@app.get("/users/me/export", response_model=ApiResponse, tags=[USER_TAG])
def export_me(current_user: User = Depends(get_current_user)):
    return api_response("Current user exported", _user_to_schema(current_user))


@app.get("/users/{userId}", response_model=ApiResponse, tags=[USER_TAG])
def get_public_user(userId: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == userId, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return api_response("Public user fetched", _public_user(user))


@app.post("/notifications", response_model=ApiResponse, status_code=status.HTTP_201_CREATED, tags=[NOTIFICATION_TAG])
def send_notification(
    payload: SendNotificationRequest,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    unique_user_ids = list(dict.fromkeys(payload.userIds))
    users = db.query(User).filter(User.id.in_(unique_user_ids), User.is_active.is_(True)).all()
    found_user_ids = {user.id for user in users}
    missing_user_ids = [user_id for user_id in unique_user_ids if user_id not in found_user_ids]

    if not users:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active users found")

    notifications = [_send_user_notification(db, user, payload) for user in users]
    db.commit()
    for notification in notifications:
        db.refresh(notification)

    return api_response(
        "Notification processed",
        {
            "items": [_notification_to_schema(notification) for notification in notifications],
            "summary": {
                "requested": len(unique_user_ids),
                "processed": len(notifications),
                "missingOrInactiveUserIds": missing_user_ids,
            },
        },
    )


@app.get("/notifications/me", response_model=ApiResponse, tags=[NOTIFICATION_TAG])
def list_my_notifications(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    unreadOnly: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
):
    query = db.query(UserNotification).filter(
        UserNotification.user_id == current_user.id,
        UserNotification.channels["inApp"].as_boolean().is_(True),
    )
    if unreadOnly:
        query = query.filter(UserNotification.is_read.is_(False))

    total = query.count()
    notifications = (
        query.order_by(UserNotification.created_at.desc())
        .offset((page - 1) * pageSize)
        .limit(pageSize)
        .all()
    )

    return api_response(
        "Notifications fetched",
        {
            "items": [_notification_to_schema(notification) for notification in notifications],
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "totalRecords": total,
                "totalPages": (total + pageSize - 1) // pageSize if total else 0,
            },
        },
    )


@app.patch("/notifications/{notificationId}/read", response_model=ApiResponse, tags=[NOTIFICATION_TAG])
def mark_notification_read(
    notificationId: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    notification = db.query(UserNotification).filter(
        UserNotification.id == notificationId,
        UserNotification.user_id == current_user.id,
    ).first()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    notification.is_read = True
    notification.read_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(notification)
    return api_response("Notification marked as read", _notification_to_schema(notification))


@app.post("/auth/admin/signup", response_model=ApiResponse, status_code=status.HTTP_201_CREATED, tags=[ADMIN_TAG])
def admin_signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = _create_user_from_payload(payload, role="admin")
    user.is_email_verified = True
    db.add(user)
    db.commit()
    db.refresh(user)
    session = _create_session(db, user)
    return api_response("Admin signup successful", _auth_payload(session, user))


@app.post("/auth/admin/signin", response_model=ApiResponse, tags=[ADMIN_TAG])
def admin_signin(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    session = _create_session(db, user)
    return api_response("Admin signin successful", _auth_payload(session, user))


@app.get("/users/", response_model=ApiResponse, tags=[ADMIN_TAG])
def admin_list_users(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=100),
):
    offset = (page - 1) * pageSize
    total = db.query(User).count()
    users = db.query(User).order_by(User.created_at.desc()).offset(offset).limit(pageSize).all()
    if not users:
        return api_response(
            "Data not found",
            {
                "items": [],
                "pagination": {
                    "page": page,
                    "pageSize": pageSize,
                    "totalRecords": total,
                    "totalPages": (total + pageSize - 1) // pageSize if total else 0,
                },
            },
        )
    return api_response(
        "Users fetched",
        {
            "items": [_user_to_schema(user) for user in users],
            "pagination": {
                "page": page,
                "pageSize": pageSize,
                "totalRecords": total,
                "totalPages": (total + pageSize - 1) // pageSize,
            },
        },
    )


@app.post("/users/admin", response_model=ApiResponse, status_code=status.HTTP_201_CREATED, tags=[ADMIN_TAG])
def admin_create_user(
    payload: AdminUserCreate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = _create_user_from_payload(payload, role=payload.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return api_response("User created by admin", _user_to_schema(user))


@app.get("/users/admin/{userId}", response_model=ApiResponse, tags=[ADMIN_TAG])
def admin_get_user(userId: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, userId)
    return api_response("User fetched by admin", _user_to_schema(user))


@app.patch("/users/admin/{userId}", response_model=ApiResponse, tags=[ADMIN_TAG])
def admin_update_user(
    userId: str,
    payload: UserUpdate,
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    user = _get_user_or_404(db, userId)
    _apply_user_update(user, payload)
    db.commit()
    db.refresh(user)
    return api_response("User updated by admin", _user_to_schema(user))


@app.delete("/users/admin/{userId}", response_model=ApiResponse, tags=[ADMIN_TAG])
def admin_delete_user(userId: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = _get_user_or_404(db, userId)
    user.is_active = False
    db.query(UserSession).filter(UserSession.user_id == user.id).update({"is_active": False})
    db.commit()
    return api_response("User deleted by admin")
