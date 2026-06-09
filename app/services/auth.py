from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from ..models.model import EmailOTP, InvitationCode, User, UserNotification, UserSession
from ..models.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    OAuthRequest,
    RefreshRequest,
    ResendOTPRequest,
    ResetPasswordRequest,
    SignupRequest,
    VerifyOTPRequest,
)
from .activity_service import track_user_activity
from .auth_utils import (
    academic_interests,
    apply_user_update,
    auth_payload,
    calculate_completeness,
    clear_login_rate_limit,
    client_ip,
    create_user_from_payload,
    credentials_exception,
    current_session_from_token,
    current_user_from_token,
    enforce_login_rate_limit,
    generate_otp_code,
    get_user_by_email,
    get_user_or_404,
    hash_password,
    is_connected,
    jwt_algorithm,
    jwt_decode,
    jwt_encode,
    jwt_expire_minutes,
    jwt_secret,
    notification_preferences,
    otp_not_expired,
    password_needs_rehash,
    payload_dict,
    public_user,
    register_login_failure,
    token,
    user_to_schema,
    verify_password,
)
from .push_dispatcher import dispatch_queued_push_notifications


def create_otp(db: Session, user: User) -> EmailOTP:
    otp = EmailOTP(user_id=user.id, code=generate_otp_code())
    db.add(otp)
    db.commit()
    db.refresh(otp)
    return otp


def create_session(db: Session, user: User) -> UserSession:
    session = UserSession(user_id=user.id, access_token=token(), refresh_token=token())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def send_otp(email: str, otp: str) -> bool:
    from app import main as main_module
    try:
        return main_module.send_otp_email(email, otp, otp_purpose="email_verification")
    except TypeError:
        return main_module.send_otp_email(email, otp)


def send_account_created(email: str, first_name: str | None = None, last_name: str | None = None) -> bool:
    from app import main as main_module
    full_name = f"{first_name} {last_name}" if first_name and last_name else (first_name or last_name or None)
    return main_module.send_account_created_email(email, full_name)


def send_password_reset(email: str, otp: str) -> bool:
    from app import main as main_module
    try:
        return main_module.send_otp_email(email, otp, otp_purpose="password_reset")
    except TypeError:
        return main_module.send_otp_email(email, otp)


def create_in_app_notification(
    db: Session,
    user: User,
    notification_type: str,
    title: str,
    body: str,
    delivery_status: dict,
) -> UserNotification | None:
    preferences = user.notification_preferences
    allow_in_app = True if not preferences else bool(preferences.get("inApp", True))
    allow_push = True if not preferences else bool(preferences.get("push", True))
    if not allow_in_app and not allow_push:
        return None

    effective_delivery_status = dict(delivery_status)
    effective_delivery_status["inApp"] = "created" if allow_in_app else "skipped"
    effective_delivery_status["push"] = "queued" if allow_push else "skipped"
    notification = UserNotification(
        user_id=user.id,
        notification_type=notification_type,
        target_type="direct",
        topic=None,
        template_key=None,
        title=title,
        body=body,
        html_body=None,
        channels={"email": False, "inApp": allow_in_app, "push": allow_push},
        delivery_status=effective_delivery_status,
    )
    db.add(notification)
    return notification


def dispatch_created_push_notification(db: Session, notification: UserNotification | None) -> None:
    if not notification or not (notification.channels or {}).get("push"):
        return
    db.refresh(notification)
    dispatch_queued_push_notifications(db, [notification.id])


def authenticate_email_password(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def upgrade_password_hash_if_needed(db: Session, user: User, password: str) -> None:
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
        db.commit()


def oauth2_token_payload(session: UserSession, user: User) -> dict:
    payload = auth_payload(session, user)
    return {
        "access_token": payload["accessToken"],
        "token_type": "bearer",
        "refresh_token": payload["refreshToken"],
        "user": payload["user"],
    }


def signup_user(db: Session, payload: SignupRequest) -> dict:
    if get_user_by_email(db, payload.email):
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
    user = create_user_from_payload(payload)
    if normalized_code:
        user.reference_code = normalized_code
    db.add(user)
    db.commit()
    db.refresh(user)
    otp = create_otp(db, user)
    sent = send_otp(user.email, otp.code)
    notification = create_in_app_notification(
        db,
        user,
        "resend-otp",
        "OTP sent",
        "We sent a one-time password to your email for verification.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    dispatch_created_push_notification(db, notification)
    session = create_session(db, user)
    return {**auth_payload(session, user), "emailSent": sent}


def verify_user_otp(db: Session, payload: VerifyOTPRequest) -> dict:
    user = get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = db.query(EmailOTP).filter(
        EmailOTP.user_id == user.id,
        EmailOTP.code == payload.otp,
        EmailOTP.is_used.is_(False),
        EmailOTP.is_expire.is_(False),
    ).order_by(EmailOTP.created_at.desc()).first()
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    if not otp_not_expired(otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    otp.is_used = True
    user.is_email_verified = True
    db.commit()
    sent = send_account_created(user.email, user.first_name, user.last_name)
    notification = create_in_app_notification(
        db,
        user,
        "user-creation",
        "Account created",
        "Your account has been created successfully and your email is now verified.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    dispatch_created_push_notification(db, notification)
    return {"email": user.email, "emailSent": sent}


def resend_user_otp(db: Session, payload: ResendOTPRequest) -> dict:
    user = get_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = create_otp(db, user)
    sent = send_otp(user.email, otp.code)
    notification = create_in_app_notification(
        db,
        user,
        "resend-otp",
        "OTP resent",
        "We resent a one-time password to your email.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    dispatch_created_push_notification(db, notification)
    return {"email": user.email, "emailSent": sent}


def forgot_user_password(db: Session, payload: ForgotPasswordRequest) -> dict:
    user = get_user_by_email(db, payload.email)
    if not user or user.is_delete or user.login_type != "email":
        return {"email": payload.email}

    otp = EmailOTP(user_id=user.id, code=generate_otp_code(), purpose="password_reset")
    db.add(otp)
    db.commit()
    db.refresh(otp)
    sent = send_password_reset(user.email, otp.code)
    notification = create_in_app_notification(
        db,
        user,
        "password-reset",
        "Password reset OTP",
        "We sent a one-time password to reset your password.",
        {"email": "sent" if sent else "failed", "inApp": "created", "push": "skipped"},
    )
    db.commit()
    dispatch_created_push_notification(db, notification)
    return {"email": payload.email, "emailSent": sent}


def reset_user_password(db: Session, payload: ResetPasswordRequest) -> dict:
    user = get_user_by_email(db, payload.email)
    if not user or user.is_delete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    otp = (
        db.query(EmailOTP)
        .filter(
            EmailOTP.user_id == user.id,
            EmailOTP.code == payload.otp,
            EmailOTP.purpose == "password_reset",
            EmailOTP.is_used.is_(False),
            EmailOTP.is_expire.is_(False),
        )
        .order_by(EmailOTP.created_at.desc())
        .first()
    )
    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")
    if not otp_not_expired(otp):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    otp.is_used = True
    user.password_hash = hash_password(payload.newPassword)
    db.commit()
    return {"email": user.email}


def login_user(db: Session, payload: LoginRequest, request: Request) -> dict:
    ip = client_ip(request)
    enforce_login_rate_limit(db, payload.email, ip)
    user = authenticate_email_password(db, payload.email, payload.password)
    if not user:
        register_login_failure(db, payload.email, ip)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if user.is_delete:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is deleted")
    upgrade_password_hash_if_needed(db, user, payload.password)
    clear_login_rate_limit(db, payload.email, ip)
    session = create_session(db, user)
    track_user_activity(db, user, "login", {"loginType": user.login_type})
    return auth_payload(session, user)


def login_for_access_token(db: Session, email: str, password: str, request: Request) -> dict:
    ip = client_ip(request)
    enforce_login_rate_limit(db, email, ip)
    user = authenticate_email_password(db, email, password)
    if not user:
        register_login_failure(db, email, ip)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if user.is_delete:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is deleted")
    upgrade_password_hash_if_needed(db, user, password)
    clear_login_rate_limit(db, email, ip)
    session = create_session(db, user)
    track_user_activity(db, user, "login", {"loginType": user.login_type})
    return oauth2_token_payload(session, user)


def social_login_user(db: Session, payload: OAuthRequest) -> dict:
    provider = payload.provider
    user = get_user_by_email(db, payload.email)
    if not user:
        user = User(
            first_name=payload.firstName or payload.email.split("@")[0],
            last_name=payload.lastName or "",
            email=payload.email,
            login_type=provider,
            profile_photo_url=payload.profilePhotoUrl,
            is_email_verified=True,
            consent_given=True,
        )
        user.notification_preferences = {"email": True, "push": True, "inApp": True}
        user.completeness_score = calculate_completeness(user)
        db.add(user)
        db.commit()
        db.refresh(user)
    session = create_session(db, user)
    track_user_activity(db, user, "login", {"loginType": user.login_type})
    return auth_payload(session, user)


def refresh_auth_session(db: Session, payload: RefreshRequest) -> dict:
    session = db.query(UserSession).filter(
        UserSession.refresh_token == payload.refreshToken,
        UserSession.is_active.is_(True),
    ).first()
    if not session or not session.user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    session.refresh_token = token()
    db.commit()
    db.refresh(session)
    return auth_payload(session, session.user)


def logout_session(db: Session, session: UserSession) -> None:
    session.is_active = False
    db.commit()
