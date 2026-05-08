from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db.db import get_db
from ..models.model import EmailOTP, User, UserNotification, UserNotificationPreference, UserSession
from ..models.schemas import ApiResponse, LoginRequest, OAuthRequest, RefreshRequest, ResendOTPRequest, SignupRequest, VerifyOTPRequest
from .shared import (
    _auth_payload,
    _create_otp,
    _create_session,
    _create_user_from_payload,
    _get_user_by_email,
    _hash_password,
    _otp_not_expired,
    _token,
    _calculate_completeness,
    api_response,
    _current_session,
)

AUTH_TAG = "1] Authentication"

router = APIRouter(tags=[AUTH_TAG])


def _send_otp(email: str, otp: str) -> bool:
    from app import main as main_module
    return main_module.send_otp_email(email, otp)


def _send_account_created(email: str, full_name: str | None = None) -> bool:
    from app import main as main_module
    return main_module.send_account_created_email(email, full_name)


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


@router.post("/auth/signup", response_model=ApiResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    if _get_user_by_email(db, payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = _create_user_from_payload(payload)
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


@router.post("/auth/login", response_model=ApiResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = _get_user_by_email(db, payload.email)
    if not user or user.password_hash != _hash_password(payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is inactive")
    session = _create_session(db, user)
    return api_response("Login successful", _auth_payload(session, user))


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
    return api_response(f"{provider.title()} login successful", _auth_payload(session, user))


@router.post("/auth/refresh", response_model=ApiResponse)
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


@router.post("/auth/logout", response_model=ApiResponse)
def logout(session: UserSession = Depends(_current_session), db: Session = Depends(get_db)):
    session.is_active = False
    db.commit()
    return api_response("Logged out")

