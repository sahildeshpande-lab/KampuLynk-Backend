import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import EmailOTP, InvitationCode, LoginRateLimit, User, UserNotification, UserNotificationPreference, UserSession
from ..models.schemas import (
    ApiResponse,
    ForgotPasswordRequest,
    LoginRequest,
    OAuthRequest,
    RefreshRequest,
    ResendOTPRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyOTPRequest,
)
from ..services.activity_service import track_user_activity
from .shared import (
    _auth_payload,
    _create_otp,
    _create_session,
    _create_user_from_payload,
    _get_user_by_email,
    _hash_password,
    _password_needs_rehash,
    _otp_not_expired,
    _token,
    _verify_password,
    _calculate_completeness,
    api_response,
    _current_session,
)

AUTH_TAG = "1] Authentication"

router = APIRouter(tags=[AUTH_TAG])

LOGIN_MAX_ATTEMPTS = 5
LOGIN_BLOCK_MINUTES = 15


def _generate_otp_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _client_ip(request: Request) -> str | None:
    # best-effort (no proxy parsing here)
    return request.client.host if request.client else None


def _rate_limit_key(email: str) -> str:
    return email.strip().lower()


def _enforce_login_rate_limit(db: Session, email: str, ip: str | None) -> LoginRateLimit | None:
    now = datetime.now(timezone.utc)
    key = _rate_limit_key(email)
    record = (
        db.query(LoginRateLimit)
        .filter(LoginRateLimit.email == key, LoginRateLimit.ip == ip)
        .first()
    )
    if record and record.blocked_until and record.blocked_until.replace(tzinfo=timezone.utc) > now:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again after {record.blocked_until.isoformat()}",
        )
    return record


def _register_login_failure(db: Session, email: str, ip: str | None) -> None:
    now = datetime.now(timezone.utc)
    key = _rate_limit_key(email)
    record = (
        db.query(LoginRateLimit)
        .filter(LoginRateLimit.email == key, LoginRateLimit.ip == ip)
        .first()
    )
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


def _clear_login_rate_limit(db: Session, email: str, ip: str | None) -> None:
    key = _rate_limit_key(email)
    db.query(LoginRateLimit).filter(LoginRateLimit.email == key, LoginRateLimit.ip == ip).delete()
    db.commit()


def _send_otp(email: str, otp: str) -> bool:
    from app import main as main_module
    return main_module.send_otp_email(email, otp)


def _send_account_created(email: str, full_name: str | None = None) -> bool:
    from app import main as main_module
    return main_module.send_account_created_email(email, full_name)


def _send_password_reset(email: str, otp: str) -> bool:
    from app import main as main_module
    return main_module.send_otp_email(email, otp)


def _create_in_app_notification(
    db: Session,
    user: User,
    notification_type: str,
    title: str,
    body: str,
    delivery_status: dict,
) -> None:
    preferences = user.notification_preferences
    allow_in_app = True if not preferences else bool(preferences.in_app)
    if not allow_in_app:
        return

    notification = UserNotification(
        user_id=user.id,
        notification_type=notification_type,
        target_type="direct",
        topic=None,
        template_key=None,
        title=title,
        body=body,
        html_body=None,
        channels={"email": False, "inApp": True, "push": False},
        delivery_status=delivery_status,
    )
    db.add(notification)


def _authenticate_email_password(db: Session, email: str, password: str) -> User | None:
    user = _get_user_by_email(db, email)
    if not user or not _verify_password(password, user.password_hash):
        return None
    return user


def _upgrade_password_hash_if_needed(db: Session, user: User, password: str) -> None:
    if _password_needs_rehash(user.password_hash):
        user.password_hash = _hash_password(password)
        db.commit()


def _oauth2_token_payload(session: UserSession, user: User) -> dict:
    payload = _auth_payload(session, user)
    return {
        "access_token": payload["accessToken"],
        "token_type": "bearer",
        "refresh_token": payload["refreshToken"],
        "user": payload["user"],
    }


@router.post("/auth/signup", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    normalized_code = None
    if payload.invitationCode:
        normalized_code = payload.invitationCode.strip().upper()
        code = (
            db.query(InvitationCode)
            .filter(InvitationCode.code == normalized_code, InvitationCode.is_active.is_(True))
            .first()
        )
        if not code:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid invitation code")
    user = _create_user_from_payload(payload)
    if normalized_code:
        user.reference_code = normalized_code
    db.add(user)
    db.commit()
    db.refresh(user)
    otp = _create_otp(db, user)
    sent = _send_otp(user.email, otp.code)
    _create_in_app_notification(
        db,
        user,
        "resend-otp",
        "OTP sent",
        "We sent a one-time password to your email for verification.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    session = _create_session(db, user)
    return api_response("Signup successful", _auth_payload(session, user))


@router.post("/auth/verify-otp", response_model=ApiResponse)
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
    if not _otp_not_expired(otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    otp.is_used = True
    user.is_email_verified = True
    db.commit()
    sent = _send_account_created(user.email, user.full_name)
    _create_in_app_notification(
        db,
        user,
        "user-creation",
        "Account created",
        "Your account has been created successfully and your email is now verified.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    return api_response("Email verified", {"email": user.email})


@router.post("/auth/resend-otp", response_model=ApiResponse)
def resend_otp(payload: ResendOTPRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = _create_otp(db, user)
    sent = _send_otp(user.email, otp.code)
    _create_in_app_notification(
        db,
        user,
        "resend-otp",
        "OTP resent",
        "We resent a one-time password to your email.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    return api_response("OTP sent", {"email": user.email})


@router.post("/auth/forgot-password", response_model=ApiResponse)
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    # Do not leak existence
    if not user or not user.is_active or user.login_type != "email":
        return api_response("If the account exists, an OTP was sent", {"email": payload.email})

    otp = EmailOTP(user_id=user.id, code=_generate_otp_code(), purpose="password_reset")
    db.add(otp)
    db.commit()
    db.refresh(otp)
    sent = _send_password_reset(user.email, otp.code)
    _create_in_app_notification(
        db,
        user,
        "password-reset",
        "Password reset OTP",
        "We sent a one-time password to reset your password.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    return api_response("If the account exists, an OTP was sent", {"email": payload.email})


@router.post("/auth/reset-password", response_model=ApiResponse)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = (
        db.query(EmailOTP)
        .filter(
            EmailOTP.user_id == user.id,
            EmailOTP.code == payload.otp,
            EmailOTP.purpose == "password_reset",
            EmailOTP.is_used.is_(False),
        )
        .order_by(EmailOTP.created_at.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    if not _otp_not_expired(otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    otp.is_used = True
    user.password_hash = _hash_password(payload.newPassword)
    db.commit()
    return api_response("Password reset successful", {"email": user.email})

@router.post("/auth/login", response_model=ApiResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)
    _enforce_login_rate_limit(db, payload.email, ip)
    user = _authenticate_email_password(db, payload.email, payload.password)
    if not user:
        _register_login_failure(db, payload.email, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    _upgrade_password_hash_if_needed(db, user, payload.password)
    _clear_login_rate_limit(db, payload.email, ip)
    session = _create_session(db, user)
    track_user_activity(db, user, "login", {"loginType": user.login_type})
    return api_response("Login successful", _auth_payload(session, user))


@router.post("/auth/token")
def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    email = form_data.username
    ip = _client_ip(request)
    _enforce_login_rate_limit(db, email, ip)
    user = _authenticate_email_password(db, email, form_data.password)
    if not user:
        _register_login_failure(db, email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    _upgrade_password_hash_if_needed(db, user, form_data.password)
    _clear_login_rate_limit(db, email, ip)
    session = _create_session(db, user)
    track_user_activity(db, user, "login", {"loginType": user.login_type})
    return _oauth2_token_payload(session, user)


@router.post("/auth/social", response_model=ApiResponse)
def social_login(payload: OAuthRequest, db: Session = Depends(get_db)):
    provider = payload.provider
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
    track_user_activity(db, user, "login", {"loginType": user.login_type})
    return api_response(f"{provider.title()} login successful", _auth_payload(session, user))


@router.post("/auth/refresh", response_model=ApiResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    session = db.query(UserSession).filter(
        UserSession.refresh_token == payload.refreshToken,
        UserSession.is_active.is_(True),
    ).first()
    if not session or not session.user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    session.refresh_token = _token()
    db.commit()
    db.refresh(session)
    return api_response("Token refreshed", _auth_payload(session, session.user))


@router.post("/auth/logout", response_model=ApiResponse)
def logout(session: UserSession = Depends(_current_session), db: Session = Depends(get_db)):
    session.is_active = False
    db.commit()
    return api_response("Logged out")
