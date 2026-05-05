import hashlib
import secrets
from typing import Iterable

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from .models.model import (
    Base,
    EmailOTP,
    User,
    UserAcademicInterest,
    UserNotificationPreference,
    UserSession,
)
from .models.schemas import (
    AuthResponse,
    ChangePasswordRequest,
    LoginRequest,
    MessageResponse,
    OAuthRequest,
    PublicUser,
    RefreshRequest,
    ResendOTPRequest,
    SignupRequest,
    User as UserSchema,
    UserUpdate,
    VerifyOTPRequest,
)
from .db.db import engine, get_db

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="KampuLynk User Management API",
    version="1.0.0",
    openapi_tags=[
        {
            "name": "1] Authentication",
            "description": "Signup, verification, social login, session refresh, and logout.",
        },
        {
            "name": "2] User Management",
            "description": "Authenticated user profile, password, export, delete, and public profile APIs.",
        },
        {
            "name": "3] Admin — User Management",
            "description": "Admin-only user listing and user detail APIs.",
        },
    ],
)


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _token() -> str:
    return secrets.token_urlsafe(32)


def _create_otp(db: Session, user: User) -> EmailOTP:
    otp = EmailOTP(user_id=user.id, code="123456")
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
    return db.query(User).filter(User.email == email.lower()).first()


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
            preferences = value.model_dump() if hasattr(value, "model_dump") else value
            if not user.notification_preferences:
                user.notification_preferences = UserNotificationPreference()
            user.notification_preferences.email = preferences["email"]
            user.notification_preferences.push = preferences["push"]
            user.notification_preferences.in_app = preferences["inApp"]
            continue
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        setattr(user, field_map[public_name], value)
    user.completeness_score = _calculate_completeness(user)
    return user


@app.get("/")
def read_root() -> dict[str, str]:
    return {"status": "KampuLynk User Management API"}


@app.post(
    "/auth/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["1] Authentication"],
)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        full_name=payload.fullName,
        email=payload.email,
        password_hash=_hash_password(payload.password),
        login_type="email",
        university=payload.university,
        major=payload.major,
        minor=payload.minor,
        education_level=payload.educationLevel,
        invitation_code=payload.invitationCode,
        consent_given=payload.consentGiven,
    )
    user.notification_preferences = UserNotificationPreference(email=True, push=True, in_app=True)
    user.completeness_score = _calculate_completeness(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    _create_otp(db, user)
    session = _create_session(db, user)
    return {"accessToken": session.access_token, "refreshToken": session.refresh_token, "user": _user_to_schema(user)}


@app.post("/auth/verify-otp", response_model=MessageResponse, tags=["1] Authentication"])
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
    otp.is_used = True
    user.is_email_verified = True
    db.commit()
    return {"message": "Email verified", "data": {"email": user.email}}


@app.post("/auth/resend-otp", response_model=MessageResponse, tags=["1] Authentication"])
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = _create_otp(db, user)
    return {"message": "OTP sent", "data": {"email": user.email, "otp": otp.code}}


@app.post("/auth/login", response_model=AuthResponse, tags=["1] Authentication"])
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    session = _create_session(db, user)
    return {"accessToken": session.access_token, "refreshToken": session.refresh_token, "user": _user_to_schema(user)}


@app.post(
    "/auth/admin/signup",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["3] Admin — User Management"],
)
def admin_signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(
        full_name=payload.fullName,
        email=payload.email,
        password_hash=_hash_password(payload.password),
        role="admin",
        login_type="email",
        university=payload.university,
        major=payload.major,
        minor=payload.minor,
        education_level=payload.educationLevel,
        invitation_code=payload.invitationCode,
        consent_given=payload.consentGiven,
        is_email_verified=True,
    )
    user.notification_preferences = UserNotificationPreference(email=True, push=True, in_app=True)
    user.completeness_score = _calculate_completeness(user)
    db.add(user)
    db.commit()
    db.refresh(user)
    session = _create_session(db, user)
    return {"accessToken": session.access_token, "refreshToken": session.refresh_token, "user": _user_to_schema(user)}


@app.post("/auth/admin/signin", response_model=AuthResponse, tags=["3] Admin — User Management"])
def admin_signin(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    session = _create_session(db, user)
    return {"accessToken": session.access_token, "refreshToken": session.refresh_token, "user": _user_to_schema(user)}


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
    return {"accessToken": session.access_token, "refreshToken": session.refresh_token, "user": _user_to_schema(user)}


@app.post("/auth/google", response_model=AuthResponse, tags=["1] Authentication"])
def google_login(payload: OAuthRequest, db: Session = Depends(get_db)):
    return _oauth_login(payload, "google", db)


@app.post("/auth/apple", response_model=AuthResponse, tags=["1] Authentication"])
def apple_login(payload: OAuthRequest, db: Session = Depends(get_db)):
    return _oauth_login(payload, "apple", db)


@app.post("/auth/refresh", response_model=AuthResponse, tags=["1] Authentication"])
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
    return {"accessToken": session.access_token, "refreshToken": session.refresh_token, "user": _user_to_schema(session.user)}


@app.post("/auth/logout", response_model=MessageResponse, tags=["1] Authentication"])
def logout(session: UserSession = Depends(_current_session), db: Session = Depends(get_db)):
    session.is_active = False
    db.commit()
    return {"message": "Logged out", "data": None}


@app.get("/users/me", response_model=UserSchema, tags=["2] User Management"])
def get_me(current_user: User = Depends(get_current_user)):
    return _user_to_schema(current_user)


@app.put("/users/me", response_model=UserSchema, tags=["2] User Management"])
def update_me(payload: UserUpdate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _apply_user_update(current_user, payload)
    db.commit()
    db.refresh(current_user)
    return _user_to_schema(current_user)


@app.post("/users/me/change-password", response_model=MessageResponse, tags=["2] User Management"])
def change_password(
    payload: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.login_type != "email" or current_user.password_hash != _hash_password(payload.currentPassword):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")
    current_user.password_hash = _hash_password(payload.newPassword)
    db.commit()
    return {"message": "Password changed", "data": None}


@app.delete("/users/me", status_code=status.HTTP_204_NO_CONTENT, tags=["2] User Management"])
def delete_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.is_active = False
    db.query(UserSession).filter(UserSession.user_id == current_user.id).update({"is_active": False})
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/users/me/export", response_model=UserSchema, tags=["2] User Management"])
def export_me(current_user: User = Depends(get_current_user)):
    return _user_to_schema(current_user)


@app.get("/users/{userId}", response_model=PublicUser, tags=["2] User Management"])
def get_public_user(userId: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == userId, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _public_user(user)


@app.get("/users/", response_model=list[UserSchema], tags=["3] Admin — User Management"])
def admin_list_users(
    _: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=50, le=100),
):
    users = db.query(User).order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    return [_user_to_schema(user) for user in users]


@app.get("/users/admin/{userId}", response_model=UserSchema, tags=["3] Admin — User Management"])
def admin_get_user(userId: str, _: User = Depends(get_admin_user), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == userId).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return _user_to_schema(user)
